import csv
import tempfile
import unittest
from pathlib import Path

from wb_finance_analytics.finance import (
    ReportValidationError,
    analyze_report,
    load_report,
    money_to_kopecks,
    write_outputs,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEMO_REPORT = PROJECT_DIR / "data" / "demo" / "wb_finance_report.csv"


class FinanceAnalyticsTests(unittest.TestCase):
    def test_money_parser_uses_decimal_rounding(self):
        self.assertEqual(money_to_kopecks("10,235"), 1024)
        self.assertEqual(money_to_kopecks("-4.50"), -450)
        self.assertEqual(money_to_kopecks(""), 0)

    def test_demo_report_reconciles_and_flags_review_rows(self):
        result = analyze_report(load_report(DEMO_REPORT))
        summary = result["summary"][0]

        self.assertEqual(summary["row_count"], 8)
        self.assertEqual(summary["retail_amount_rub"], "24500.00")
        self.assertEqual(summary["reported_payout_rub"], "18900.00")
        self.assertEqual(summary["calculated_payout_rub"], "18925.00")
        self.assertEqual(summary["reconciliation_delta_rub"], "-25.00")
        self.assertEqual(summary["exception_count"], 3)

        reasons = {row["line_id"]: row["reason"] for row in result["exceptions"]}
        self.assertEqual(reasons["L005"], "PENALTY_PRESENT")
        self.assertEqual(reasons["L006"], "DEDUCTION_PRESENT")
        self.assertEqual(reasons["L008"], "PAYOUT_MISMATCH")

    def test_missing_required_column_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_DIR / "tests") as tmp:
            path = Path(tmp) / "broken.csv"
            with path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=["line_id", "sku"])
                writer.writeheader()
                writer.writerow({"line_id": "1", "sku": "A"})
            with self.assertRaises(ReportValidationError):
                load_report(path)

    def test_output_files_are_created(self):
        result = analyze_report(load_report(DEMO_REPORT))
        with tempfile.TemporaryDirectory(dir=PROJECT_DIR / "tests") as tmp:
            write_outputs(result, tmp)
            self.assertEqual(
                {path.name for path in Path(tmp).glob("*.csv")},
                {"summary.csv", "products.csv", "operations.csv", "exceptions.csv"},
            )


if __name__ == "__main__":
    unittest.main()

