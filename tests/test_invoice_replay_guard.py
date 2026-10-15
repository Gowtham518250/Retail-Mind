from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from invoices_billing import InvoiceSyncCreate, InvoiceLineItemCreate, _invoice_replay_matches


def _existing_invoice(*, total=110, tax=10, name="Cash Customer", phone=None, day=date(2026, 10, 15), lines=None):
    return SimpleNamespace(
        invoice_number="INV-1",
        total_amount=Decimal(str(total)),
        tax=Decimal(str(tax)),
        customer_name=name,
        customer_phone=phone,
        invoice_date=day,
        line_items=lines or [],
        paid_amount=Decimal("30.00"),
        payment_status="PARTIAL",
    )


def _payload(*, total=110, tax=10, name="Cash Customer", phone=None, day="2026-10-15", lines=None):
    return InvoiceSyncCreate(
        invoice_number="INV-1",
        offline_id="offline-sale-1",
        customer_name=name,
        customer_phone=phone,
        total_amount=total,
        paid_amount=0,
        tax=tax,
        payment_status="PAID",
        invoice_date=day,
        line_items=lines,
    )


def test_invoice_retry_accepts_same_immutable_sale_even_after_payment_changes():
    existing = _existing_invoice(lines=[SimpleNamespace(description="Rice", quantity=Decimal("2"), unit_price=Decimal("50"))])
    data = _payload(lines=[InvoiceLineItemCreate(product_name="Rice", quantity=2, unit_price=50)])
    assert _invoice_replay_matches(existing, data, "INV-1") is True


def test_invoice_retry_rejects_changed_total_under_same_offline_id():
    assert _invoice_replay_matches(_existing_invoice(), _payload(total=115), "INV-1") is False


def test_invoice_retry_rejects_changed_line_items_under_same_offline_id():
    existing = _existing_invoice(lines=[SimpleNamespace(description="Rice", quantity=Decimal("2"), unit_price=Decimal("50"))])
    changed = _payload(lines=[InvoiceLineItemCreate(product_name="Rice", quantity=3, unit_price=50)])
    assert _invoice_replay_matches(existing, changed, "INV-1") is False
