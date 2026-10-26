"""Regression contract tests for the traceable daily business summary."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_daily_report_uses_real_expenses_and_no_percentage_guess():
    source = (ROOT / "report_service.py").read_text(encoding="utf-8")
    assert "ShopExpense.expense_date == report_date" in source
    assert "Decimal(\"0.4\")" not in source
    assert "Profit estimate unavailable" in source


def test_daily_report_uses_shared_sales_recognition_and_separates_payments():
    source = (ROOT / "report_service.py").read_text(encoding="utf-8")
    assert "recognized_invoice_filters()" in source
    assert "Payment.payment_date >= start_utc" in source
    assert "Payment.payment_date < end_utc" in source
    assert '"gross_sales"' in source
    assert '"returns"' in source
    assert '"net_sales"' in source
    assert '"total_collected"' in source


def test_daily_report_returns_audit_sources_and_operational_alerts():
    source = (ROOT / "report_service.py").read_text(encoding="utf-8")
    assert '"invoice_ids"' in source
    assert '"payment_ids"' in source
    assert '"expense_ids"' in source
    assert '"return_ids"' in source
    assert '"customer_credit_outstanding"' in source
    assert '"stock_alert_count"' in source


def test_refund_settlement_does_not_rewrite_return_decision_date():
    source = (ROOT / "growth_suite.py").read_text(encoding="utf-8")
    assert "if ret.processed_at is None:" in source
