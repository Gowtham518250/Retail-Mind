"""Regression tests for UPI-ledger idempotency and unreferenced candidates."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from upi_ledger_service import UpiLedgerService


class FakeQuery:
    def __init__(self, db):
        self.db = db
        self.criteria = {}

    def filter_by(self, **criteria):
        self.criteria.update(criteria)
        return self

    def first(self):
        for row in self.db.rows:
            if all(getattr(row, key, None) == value for key, value in self.criteria.items()):
                return row
        return None


class FakeDB:
    def __init__(self):
        self.rows = []
        self.next_id = 1

    def query(self, _model):
        return FakeQuery(self)

    def add(self, row):
        row.id = self.next_id
        self.next_id += 1
        self.rows.append(row)

    def commit(self):
        pass

    def rollback(self):
        pass


def test_replay_of_same_normalized_reference_creates_only_one_ledger_row():
    db = FakeDB()
    first = UpiLedgerService.record_upi_payment(
        db, 10, 55, "shop@upi", Decimal("500.00"),
        customer_upi="payer@upi", upi_reference="utr-1234-ab",
    )
    second = UpiLedgerService.record_upi_payment(
        db, 10, 55, "shop@upi", Decimal("500.00"),
        customer_upi="payer@upi", upi_reference="UTR 1234 AB",
    )

    assert first["status"] == "recorded"
    assert second["status"] == "duplicate"
    assert second["ledger_id"] == first["ledger_id"]
    assert len(db.rows) == 1


def test_same_reference_with_different_amount_requires_review():
    db = FakeDB()
    UpiLedgerService.record_upi_payment(
        db, 10, 55, "shop@upi", Decimal("500.00"), upi_reference="UTR-1234",
    )

    with pytest.raises(HTTPException) as excinfo:
        UpiLedgerService.record_upi_payment(
            db, 10, 55, "shop@upi", Decimal("700.00"), upi_reference="UTR 1234",
        )
    assert excinfo.value.status_code == 409
    assert len(db.rows) == 1


def test_unreferenced_notification_is_not_written_as_a_ledger_entry():
    db = FakeDB()
    result = UpiLedgerService.record_upi_payment(
        db, 10, 55, "shop@upi", Decimal("500.00"), upi_reference=None,
    )
    assert result["status"] == "needs_confirmation"
    assert result["recorded"] is False
    assert result["ledger_id"] is None
    assert db.rows == []
