-- PostgreSQL-версия витрин для нормализованного демонстрационного отчёта.
-- Денежные значения хранятся в рублях NUMERIC, расходы указываются положительными.

CREATE SCHEMA IF NOT EXISTS portfolio;

CREATE TABLE IF NOT EXISTS portfolio.wb_finance_lines (
    line_id TEXT PRIMARY KEY,
    report_date DATE NOT NULL,
    sku TEXT NOT NULL,
    product TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    retail_amount_rub NUMERIC(18,2) NOT NULL,
    commission_rub NUMERIC(18,2) NOT NULL,
    logistics_rub NUMERIC(18,2) NOT NULL,
    storage_rub NUMERIC(18,2) NOT NULL,
    acceptance_rub NUMERIC(18,2) NOT NULL,
    penalty_rub NUMERIC(18,2) NOT NULL,
    deduction_rub NUMERIC(18,2) NOT NULL,
    adjustment_rub NUMERIC(18,2) NOT NULL,
    reported_payout_rub NUMERIC(18,2) NOT NULL
);

CREATE OR REPLACE VIEW portfolio.wb_finance_reconciliation AS
SELECT
    line_id,
    report_date,
    sku,
    product,
    operation_type,
    quantity,
    retail_amount_rub,
    commission_rub,
    logistics_rub,
    storage_rub,
    acceptance_rub,
    penalty_rub,
    deduction_rub,
    adjustment_rub,
    reported_payout_rub,
    retail_amount_rub
        - commission_rub
        - logistics_rub
        - storage_rub
        - acceptance_rub
        - penalty_rub
        - deduction_rub
        + adjustment_rub AS calculated_payout_rub,
    reported_payout_rub - (
        retail_amount_rub
        - commission_rub
        - logistics_rub
        - storage_rub
        - acceptance_rub
        - penalty_rub
        - deduction_rub
        + adjustment_rub
    ) AS reconciliation_delta_rub
FROM portfolio.wb_finance_lines;

CREATE OR REPLACE VIEW portfolio.wb_finance_by_product AS
SELECT
    sku,
    product,
    SUM(quantity) AS quantity,
    SUM(retail_amount_rub) AS retail_amount_rub,
    SUM(commission_rub) AS commission_rub,
    SUM(logistics_rub) AS logistics_rub,
    SUM(storage_rub) AS storage_rub,
    SUM(acceptance_rub) AS acceptance_rub,
    SUM(penalty_rub) AS penalty_rub,
    SUM(deduction_rub) AS deduction_rub,
    SUM(adjustment_rub) AS adjustment_rub,
    SUM(reported_payout_rub) AS reported_payout_rub,
    SUM(calculated_payout_rub) AS calculated_payout_rub,
    SUM(reconciliation_delta_rub) AS reconciliation_delta_rub
FROM portfolio.wb_finance_reconciliation
GROUP BY sku, product;

