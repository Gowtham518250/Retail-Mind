from invoices_billing import InvoiceSyncCreate, _resolve_invoice_sync_payment_state


def test_regular_checkout_with_zero_receipt_defaults_to_paid():
    assert _resolve_invoice_sync_payment_state(12, 0, False, "Payment via Cash - Regular Sale") == (
        12.0, "PAID", "PAID"
    )


def test_legacy_regular_cash_sale_with_explicit_note_is_repaired():
    assert _resolve_invoice_sync_payment_state(
        25, 0, None, "Payment via CASH - Regular Sale"
    ) == (25.0, "PAID", "PAID")


def test_borrow_invoice_is_not_marked_paid():
    assert _resolve_invoice_sync_payment_state(
        25, 0, True, "Payment via CASH - Borrow Invoice"
    ) == (0.0, "SENT", "UNPAID")


def test_explicit_partial_cash_receipt_remains_partial():
    assert _resolve_invoice_sync_payment_state(
        100, 30, False, "Payment via CASH - Regular Sale"
    ) == (30.0, "PARTIAL", "PARTIAL")


def test_old_unlabelled_zero_paid_invoice_is_not_guessed_as_paid():
    assert _resolve_invoice_sync_payment_state(50, 0, None, None) == (
        0.0, "SENT", "UNPAID"
    )


def test_sync_schema_exposes_payment_method_and_borrow_intent():
    fields = getattr(
        InvoiceSyncCreate, "model_fields",
        getattr(InvoiceSyncCreate, "__fields__", {}),
    )
    assert "payment_method" in fields
    assert "is_borrow" in fields
