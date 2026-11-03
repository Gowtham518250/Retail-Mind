from decimal import Decimal

from invoices_billing import (
    InvoiceLineItemCreate,
    InvoiceSyncCreate,
    _resolve_invoice_sync_payment_state,
)


def test_regular_cash_checkout_with_zero_receipt_defaults_to_paid():
    assert _resolve_invoice_sync_payment_state(
        12, 0, False, "Payment via Cash - Regular Sale", "CASH"
    ) == (12.0, "PAID", "PAID")


def test_legacy_regular_cash_sale_with_explicit_note_is_repaired():
    assert _resolve_invoice_sync_payment_state(
        25, 0, None, "Payment via Cash - Regular Sale", None
    ) == (25.0, "PAID", "PAID")


def test_borrow_invoice_is_not_marked_paid():
    assert _resolve_invoice_sync_payment_state(
        25, 0, True, "Payment via Cash - Borrow Invoice", "CASH"
    ) == (0.0, "SENT", "UNPAID")


def test_explicit_partial_cash_receipt_remains_partial():
    assert _resolve_invoice_sync_payment_state(
        100, 30, False, "Payment via Cash - Regular Sale", "CASH"
    ) == (30.0, "PARTIAL", "PARTIAL")


def test_unconfirmed_online_checkout_with_zero_receipt_stays_unpaid():
    assert _resolve_invoice_sync_payment_state(
        85, 0, False, "Payment via Online - Regular Sale", "ONLINE"
    ) == (0.0, "SENT", "UNPAID")


def test_unlabelled_legacy_zero_paid_invoice_is_not_guessed_paid():
    assert _resolve_invoice_sync_payment_state(50, 0, None, None, None) == (
        0.0, "SENT", "UNPAID"
    )


def test_sync_schema_exposes_payment_method_and_borrow_intent():
    fields = getattr(
        InvoiceSyncCreate, "model_fields",
        getattr(InvoiceSyncCreate, "__fields__", {}),
    )
    assert "payment_method" in fields
    assert "is_borrow" in fields



def test_multiple_discounted_items_reconcile_with_invoice_level_tax():
    payload = InvoiceSyncCreate(
        invoice_number="BILL-MULTI-PRICE-TEST",
        total_amount=226.66,
        paid_amount=226.66,
        tax=18.66,
        payment_method="CASH",
        line_items=[
            InvoiceLineItemCreate(
                product_name="Rice",
                quantity=Decimal("2"),
                unit_price=Decimal("50"),
                discount_amount=Decimal("10"),
            ),
            InvoiceLineItemCreate(
                product_name="Flour",
                quantity=Decimal("1.5"),
                unit_price=Decimal("80"),
                discount_amount=Decimal("2"),
            ),
        ],
    )

    discounted_subtotal = sum(
        (
            item.quantity * item.unit_price
            - min(item.quantity * item.unit_price, item.discount_amount)
        )
        for item in payload.line_items
    )

    assert discounted_subtotal == Decimal("208")
    assert Decimal(str(payload.total_amount)) - Decimal(str(payload.tax)) == discounted_subtotal
    assert len(payload.line_items) == 2
    assert [item.unit_price for item in payload.line_items] == [
        Decimal("50"),
        Decimal("80"),
    ]
