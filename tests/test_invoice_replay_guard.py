from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from pydantic import ValidationError

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


def test_invoice_line_schema_accepts_explicit_custom_untracked_item():
    item = InvoiceLineItemCreate(
        product_id=None,
        product_name="Chicken",
        quantity=1,
        unit_price=150,
        stock_tracked=False,
    )
    assert item.product_name == "Chicken"
    assert item.product_id is None
    assert item.stock_tracked is False


def test_invoice_line_schema_defaults_to_stock_tracked_for_legacy_clients():
    item = InvoiceLineItemCreate(
        product_id=None,
        product_name="Chicken",
        quantity=1,
        unit_price=150,
    )
    assert item.stock_tracked is True


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


def _financial_sync_payload(**overrides):
    values = {
        "invoice_number": "BILL-FINANCIAL-1",
        "offline_id": "offline-financial-1",
        "total_amount": 100.00,
        "paid_amount": 0.00,
        "tax": 10.00,
        "invoice_date": "2026-10-15",
        "line_items": [
            InvoiceLineItemCreate(product_name="Rice", quantity=1, unit_price=90)
        ],
    }
    values.update(overrides)
    return values


def test_sync_invoice_rejects_paid_amount_above_total():
    with pytest.raises(ValidationError, match="paid_amount cannot exceed total_amount"):
        InvoiceSyncCreate(**_financial_sync_payload(total_amount=100, paid_amount=100.01))


def test_sync_invoice_rejects_tax_above_total():
    with pytest.raises(ValidationError, match="tax cannot exceed total_amount"):
        InvoiceSyncCreate(**_financial_sync_payload(total_amount=100, tax=100.01))


def test_sync_invoice_rounds_money_to_paise_before_balance_validation():
    data = InvoiceSyncCreate(
        **_financial_sync_payload(
            total_amount=100.005,
            paid_amount=100.004,
            tax=10.004,
        )
    )
    assert data.total_amount == 100.01
    assert data.paid_amount == 100.00
    assert data.tax == 10.00


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -0.01])
def test_sync_invoice_rejects_non_finite_or_negative_monetary_values(bad_value):
    with pytest.raises(ValidationError):
        InvoiceSyncCreate(**_financial_sync_payload(total_amount=bad_value))
