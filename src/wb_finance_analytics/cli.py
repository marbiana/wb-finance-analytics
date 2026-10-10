from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

from .finance import analyze_report, load_report, money_to_kopecks, write_outputs


def build_parser() -> argparse.ArgumentParser:
    project_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Аналитика нормализованного финансового отчёта Wildberries"
    )
    parser.add_argument("--input", type=Path, help="CSV с нормализованными строками отчёта")
    parser.add_argument("--output-dir", type=Path, default=project_dir / "outputs")
    parser.add_argument(
        "--tolerance",
        default="0.01",
        help="Допустимое расхождение выплаты в рублях (по умолчанию 0.01)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Использовать синтетический отчёт из data/demo",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    project_dir = Path(__file__).resolve().parents[2]
    if args.demo:
        input_path = project_dir / "data" / "demo" / "wb_finance_report.csv"
    elif args.input:
        input_path = args.input
    else:
        parser.error("Укажите --input или используйте --demo")

    try:
        tolerance = money_to_kopecks(Decimal(str(args.tolerance)))
    except Exception as exc:
        parser.error(f"Некорректный --tolerance: {exc}")

    rows = load_report(input_path)
    result = analyze_report(rows, tolerance_kopecks=tolerance)
    write_outputs(result, args.output_dir)
    summary = result["summary"][0]
    print(f"Строк обработано: {summary['row_count']}")
    print(f"Выплата по отчёту: {summary['reported_payout_rub']} руб.")
    print(f"Расчётная выплата: {summary['calculated_payout_rub']} руб.")
    print(f"Расхождение: {summary['reconciliation_delta_rub']} руб.")
    print(f"Строк для проверки: {summary['exception_count']}")
    print(f"Результаты: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()

