from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from models import BankReconciliation
from retail_intelligence import (
    ReconCreate,
    _recon_money,
    _reconciliation_matches,
    _reconciliation_response,
    router,
)


def _record(**overrides):
    values = {
        "id": 41,
        "shop_id": 7,
        "recon_date": date(2026, 10, 15),
        "expected_upi_amount": Decimal("1250.00"),
        "actual_bank_deposit": Decimal("1250.00"),
        "status": "MATCHED",
        "notes": "daily UPI batch",
        "idempotency_key": "bank-recon-test-key-41",
        "created_at": datetime(2026, 10, 15, 12, 30, 0),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(**overrides):
    values = {
        "recon_date": date(2026, 10, 15),
        "expected_upi_amount": "1250.00",
        "actual_bank_deposit": "1250.00",
        "notes": "daily UPI batch",
        "idempotency_key": "bank-recon-test-key-41",
    }
    values.update(overrides)
    return ReconCreate(**values)


def test_reconciliation_route_contract_and_model_index():
    routes = {
        (route.path, method)
        for route in router.routes
        for method in (route.methods or set())
    }
    assert ("/bank-recon", "POST") in routes
    assert ("/bank-recon", "GET") in routes

    fields = getattr(BankReconciliation, "__table__").columns.keys()
    assert "idempotency_key" in fields
    assert "created_at" in fields
    index_names = {index.name for index in BankReconciliation.__table__.indexes}
    assert "uq_bank_reconciliation_shop_idempotency" in index_names


def test_legacy_request_without_idempotency_key_remains_supported():
    request = ReconCreate(
        recon_date=date(2026, 10, 15),
        expected_upi_amount=100,
        actual_bank_deposit=100,
    )
    assert request.idempotency_key is None
    assert _recon_money(request.expected_upi_amount) == Decimal("100.00")


def test_retry_is_accepted_only_when_immutable_financial_facts_match():
    record = _record()
    assert _reconciliation_matches(record, _request(), "daily UPI batch")
    assert not _reconciliation_matches(
        record,
        _request(actual_bank_deposit="1249.00"),
        "daily UPI batch",
    )
    assert not _reconciliation_matches(
        record,
        _request(recon_date=date(2026, 10, 14)),
        "daily UPI batch",
    )
    assert not _reconciliation_matches(record, _request(), "corrected note")


def test_response_contains_auditable_values_and_marks_replay():
    response = _reconciliation_response(_record(), duplicate=True)
    assert response["reconciliation_id"] == 41
    assert response["expected_upi_amount"] == 1250.0
    assert response["actual_bank_deposit"] == 1250.0
    assert response["difference"] == 0.0
    assert response["created_at"] == "2026-10-15T12:30:00"
    assert response["duplicate"] is True
    assert response["status"] == "MATCHED"
