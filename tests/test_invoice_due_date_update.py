from datetime import date

from invoices_billing import InvoiceUpdate


def test_invoice_update_accepts_and_tracks_due_date():
    update = InvoiceUpdate(due_date="2026-12-15")

    assert update.due_date == date(2026, 12, 15)
    assert "due_date" in update.__fields_set__


def test_invoice_update_can_explicitly_clear_due_date():
    update = InvoiceUpdate(due_date=None)

    assert update.due_date is None
    assert "due_date" in update.__fields_set__


def test_invoice_update_omission_does_not_request_due_date_change():
    update = InvoiceUpdate(notes="Updated invoice note")

    assert "due_date" not in update.__fields_set__
