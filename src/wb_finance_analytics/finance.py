from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


IDENTITY_COLUMNS = (
    "line_id",
    "report_date",
    "sku",
    "product",
    "operation_type",
    "quantity",
)

MONEY_COLUMNS = (
    "retail_amount_rub",
    "commission_rub",
    "logistics_rub",
    "storage_rub",
    "acceptance_rub",
    "penalty_rub",
    "deduction_rub",
    "adjustment_rub",
    "reported_payout_rub",
)

REQUIRED_COLUMNS = IDENTITY_COLUMNS + MONEY_COLUMNS

AGGREGATE_COLUMNS = (
    "quantity",
    *MONEY_COLUMNS,
    "calculated_payout_rub",
    "reconciliation_delta_rub",
)


class ReportValidationError(ValueError):
    """Raised when a normalized report cannot be analyzed safely."""


def money_to_kopecks(value: Any) -> int:
    """Convert a decimal amount to integer kopecks without binary floats."""
    if value is None or str(value).strip() == "":
        return 0
    text = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise ReportValidationError(f"Некорректное денежное значение: {value!r}") from exc
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def kopecks_to_text(value: int) -> str:
    return f"{Decimal(value) / Decimal(100):.2f}"


def _parse_quantity(value: Any, line_id: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ReportValidationError(
            f"Строка {line_id}: quantity должно быть целым числом"
        ) from exc


def load_report(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a normalized UTF-8 CSV report."""
    report_path = Path(path)
    with report_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = tuple(reader.fieldnames or ())
        missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
        if missing:
            raise ReportValidationError(
                "В отчёте отсутствуют обязательные колонки: " + ", ".join(missing)
            )

        rows: list[dict[str, Any]] = []
        seen_line_ids: set[str] = set()
        for source_row in reader:
            line_id = str(source_row["line_id"]).strip()
            if not line_id:
                raise ReportValidationError("Обнаружена строка без line_id")
            if line_id in seen_line_ids:
                raise ReportValidationError(f"Повторяющийся line_id: {line_id}")
            seen_line_ids.add(line_id)

            row: dict[str, Any] = {
                "line_id": line_id,
                "report_date": str(source_row["report_date"]).strip(),
                "sku": str(source_row["sku"]).strip(),
                "product": str(source_row["product"]).strip(),
                "operation_type": str(source_row["operation_type"]).strip().lower(),
                "quantity": _parse_quantity(source_row["quantity"], line_id),
            }
            if not row["sku"] or not row["product"] or not row["operation_type"]:
                raise ReportValidationError(
                    f"Строка {line_id}: sku, product и operation_type обязательны"
                )
            for column in MONEY_COLUMNS:
                row[column] = money_to_kopecks(source_row[column])
            rows.append(row)

    if not rows:
        raise ReportValidationError("Отчёт не содержит строк данных")
    return rows


def _calculated_payout(row: dict[str, Any]) -> int:
    return (
        row["retail_amount_rub"]
        - row["commission_rub"]
        - row["logistics_rub"]
        - row["storage_rub"]
        - row["acceptance_rub"]
        - row["penalty_rub"]
        - row["deduction_rub"]
        + row["adjustment_rub"]
    )


def _empty_totals() -> dict[str, int]:
    return {column: 0 for column in AGGREGATE_COLUMNS}


def _add_row(totals: dict[str, int], row: dict[str, Any]) -> None:
    totals["quantity"] += row["quantity"]
    for column in MONEY_COLUMNS:
        totals[column] += row[column]
    calculated = _calculated_payout(row)
    totals["calculated_payout_rub"] += calculated
    totals["reconciliation_delta_rub"] += row["reported_payout_rub"] - calculated


def _display_totals(totals: dict[str, int]) -> dict[str, Any]:
    result: dict[str, Any] = {"quantity": totals["quantity"]}
    for column in AGGREGATE_COLUMNS:
        if column != "quantity":
            result[column] = kopecks_to_text(totals[column])
    return result


def analyze_report(
    rows: Iterable[dict[str, Any]], tolerance_kopecks: int = 1
) -> dict[str, list[dict[str, Any]]]:
    """Aggregate report lines and return summaries plus review exceptions."""
    if tolerance_kopecks < 0:
        raise ValueError("tolerance_kopecks must be non-negative")

    total = _empty_totals()
    products: dict[tuple[str, str], dict[str, int]] = defaultdict(_empty_totals)
    operations: dict[str, dict[str, int]] = defaultdict(_empty_totals)
    exceptions: list[dict[str, Any]] = []
    row_count = 0

    for row in rows:
        row_count += 1
        calculated = _calculated_payout(row)
        delta = row["reported_payout_rub"] - calculated
        _add_row(total, row)
        _add_row(products[(row["sku"], row["product"])], row)
        _add_row(operations[row["operation_type"]], row)

        reasons: list[str] = []
        if abs(delta) > tolerance_kopecks:
            reasons.append("PAYOUT_MISMATCH")
        if row["penalty_rub"]:
            reasons.append("PENALTY_PRESENT")
        if row["deduction_rub"]:
            reasons.append("DEDUCTION_PRESENT")
        if reasons:
            exceptions.append(
                {
                    "line_id": row["line_id"],
                    "report_date": row["report_date"],
                    "sku": row["sku"],
                    "product": row["product"],
                    "operation_type": row["operation_type"],
                    "reason": ";".join(reasons),
                    "reported_payout_rub": kopecks_to_text(row["reported_payout_rub"]),
                    "calculated_payout_rub": kopecks_to_text(calculated),
                    "reconciliation_delta_rub": kopecks_to_text(delta),
                }
            )

    summary = _display_totals(total)
    summary["row_count"] = row_count
    summary["exception_count"] = len(exceptions)

    product_rows = [
        {"sku": sku, "product": product, **_display_totals(values)}
        for (sku, product), values in sorted(products.items())
    ]
    operation_rows = [
        {"operation_type": operation, **_display_totals(values)}
        for operation, values in sorted(operations.items())
    ]
    return {
        "summary": [summary],
        "products": product_rows,
        "operations": operation_rows,
        "exceptions": exceptions,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(result: dict[str, list[dict[str, Any]]], output_dir: str | Path) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    for name in ("summary", "products", "operations", "exceptions"):
        _write_csv(output_path / f"{name}.csv", result[name])

