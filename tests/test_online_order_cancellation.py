"""Regression tests for the online-order cancellation financial contract."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cancel_and_reject_remove_order_sale_and_invoice():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    helper_start = source.index("def _reverse_online_order_financials")
    helper_end = source.index("# =====================\n# CUSTOMER AUTH SCHEMAS", helper_start)
    helper = source[helper_start:helper_end]

    assert 'sales.reference_order_id == order.id' in helper
    assert 'UniversalTransaction.category == "SALE"' in helper
    assert "db.delete(sale_transaction)" in helper
    assert "db.delete(invoice)" in helper
    assert 'category="SALE_REVERSAL"' in helper


def test_real_payment_evidence_is_preserved_when_invoice_is_removed():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    helper_start = source.index("def _reverse_online_order_financials")
    helper_end = source.index("# =====================\n# CUSTOMER AUTH SCHEMAS", helper_start)
    helper = source[helper_start:helper_end]

    assert 'category == "PAYMENT"' in helper
    assert 'category="PAYMENT"' in helper
    assert "payment_reference" in helper
    assert "refund follow-up required" in helper


def test_customer_cancel_and_owner_reject_publish_invoice_deleted():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    assert '"type": "invoice.deleted"' in source
    assert '"ONLINE_ORDER_CANCELLATION"' in source
    assert '"ONLINE_ORDER_REJECTION"' in source


def test_sales_restore_omits_legacy_cancelled_invoices_and_summary_totals():
    source = (ROOT / "sales_restore_service.py").read_text(encoding="utf-8")
    assert "Invoice.status != InvoiceStatus.CANCELLED" in source
    assert "from models import Invoice, InvoiceStatus," in source


def test_customer_web_calls_the_authenticated_cancel_endpoint():
    orders_page = (
        ROOT / "frontend-web" / "src" / "app" / "orders" / "page.tsx"
    ).read_text(encoding="utf-8")

    assert "API_BASE + '/store/order/' + order.order_id + '/cancel'" in orders_page
    assert "method: 'POST'" in orders_page
    assert "Authorization: 'Bearer ' + token" in orders_page
    assert "data?.status !== 'CANCELLED'" in orders_page
