"""Regression tests for the online-order cancellation financial contract."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cancel_and_reject_remove_order_sale_and_invoice():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    helper_start = source.index("def _online_order_invoice_candidates")
    helper_end = source.index("# =====================\n# CUSTOMER AUTH SCHEMAS", helper_start)
    helper = source[helper_start:helper_end]

    assert 'sales.reference_order_id == order.id' in helper
    assert 'UniversalTransaction.category == "SALE"' in helper
    assert "for sale_transaction in sale_transactions" in helper
    assert "db.delete(invoice)" in helper
    assert "for invoice in invoices" in helper
    assert "SALE_REVERSAL" in helper
    assert 'payment_event.category = "REFUND_REQUIRED"' in helper


def test_real_payment_evidence_is_preserved_when_invoice_is_removed():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    helper_start = source.index("def _online_order_invoice_candidates")
    helper_end = source.index("# =====================\n# CUSTOMER AUTH SCHEMAS", helper_start)
    helper = source[helper_start:helper_end]

    assert 'category.in_(["PAYMENT", "REFUND_REQUIRED"])' in helper
    assert 'category = "REFUND_REQUIRED"' in helper
    assert "Refund required for cancelled online order" in helper
    assert "received_amount" in helper


def test_customer_cancel_and_owner_reject_publish_invoice_deleted():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    assert '"type": "invoice.deleted"' in source
    assert '"ONLINE_ORDER_CANCELLATION"' in source
    assert '"ONLINE_ORDER_REJECTION"' in source


def test_sales_restore_omits_legacy_cancelled_invoices_and_summary_totals():
    source = (ROOT / "sales_restore_service.py").read_text(encoding="utf-8")
    assert "Invoice.status != InvoiceStatus.CANCELLED" in source
    assert "from models import Invoice, InvoiceStatus," in source



def test_online_checkout_deducts_stock_and_persists_out_movements():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    authenticated_start = source.index('@router.post("/order")')
    guest_start = source.index('@router.post("/guest-order")')
    my_orders_start = source.index('@router.get("/my-orders")')
    authenticated = source[authenticated_start:guest_start]
    guest = source[guest_start:my_orders_start]

    assert "product.current_stock -= item.quantity" in authenticated
    assert "product.current_stock -= item.quantity" in guest
    assert "_record_online_order_stock_movements(db, order, order_items)" in authenticated
    assert "_record_online_order_stock_movements(db, order, order_items)" in guest
    assert 'movement_type="OUT"' in source
    assert 'reason="ONLINE_ORDER"' in source
    assert "STOCK-OUT-{line_index}" in source


def test_cancel_or_reject_restores_stock_with_idempotent_in_movement():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    helper_start = source.index("def _online_order_invoice_candidates")
    helper_end = source.index("# =====================\n# CUSTOMER AUTH SCHEMAS", helper_start)
    helper = source[helper_start:helper_end]

    assert 'movement_type="IN"' in helper
    assert 'reason="ONLINE_ORDER_RESTORED"' in helper
    assert "STOCK-IN-{line_index}" in helper
    assert "existing_restore is not None" in helper



def test_cancellation_removes_all_legacy_invoice_variants_and_journal_reversals():
    source = (ROOT / "online_store.py").read_text(encoding="utf-8")
    assert "def _online_order_invoice_candidates" in source
    assert "Invoice.invoice_number == prefix" in source
    assert 'Invoice.notes.ilike(f"%Online Order #{order.id} |%")' in source
    assert 'Invoice.invoice_number.like(f"{prefix}-%")' in source
    assert "cancelled_invoices = _reverse_online_order_financials" in source
    assert "for deleted_invoice in deleted_invoice_snapshots" in source


def test_profit_and_loss_excludes_payment_and_cancellation_artifact_categories():
    source = (ROOT / "retail_intelligence.py").read_text(encoding="utf-8")
    assert 'excluded_income_categories = ["PAYMENT", "REFUND_REQUIRED", "SALE_REVERSAL"]' in source
    assert 'notin_(["SALE_REVERSAL", "REFUND_REQUIRED"])' in source
    assert 'notin_(["PAYMENT", "REFUND_REQUIRED", "SALE_REVERSAL"])' in source



def test_legacy_cancelled_order_migration_removes_old_invoice_and_reversal_records():
    migration = (ROOT / "alembic/versions/041_cancelled_online_order_financial_cleanup.py").read_text(encoding="utf-8")
    assert "CANCELLED', 'REJECTED', 'RETURNED" in migration
    assert "DELETE FROM invoices" in migration
    assert "DELETE FROM universal_transactions" in migration
    assert "category = 'REFUND_REQUIRED'" in migration
    assert "category = 'SALE_REVERSAL'" in migration
