import os
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

os.environ.setdefault("SECRET_KEY", "retail-mind-agent-ci-only-not-for-production")

from agentic.registry import list_capabilities
from agentic.tools import KhataLedgerMovementArgs, TOOL_DEFINITIONS
from agentic.khata_actions import prepare_khata_ledger_movement
from models import AgentPendingAction, Customer, KhataBalance, KhataHistory


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args, **_kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.result[0] if isinstance(self.result, list) and self.result else (
            None if isinstance(self.result, list) else self.result
        )

    def all(self):
        if self.result is None:
            return []
        return self.result if isinstance(self.result, list) else [self.result]


class _Db:
    def __init__(self, account=None, *, khata_matches=None, customer_matches=None):
        self.account = account
        self.khata_matches = khata_matches
        self.customer_matches = customer_matches or []
        self.added = []

    def query(self, model):
        if model is AgentPendingAction:
            return _Query(None)
        if model is KhataBalance:
            if self.khata_matches is not None:
                return _Query(self.khata_matches)
            return _Query(self.account)
        if model is Customer:
            return _Query(self.customer_matches)
        raise AssertionError(f"Unexpected query model: {model}")

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None


def test_khata_tool_rejects_untrusted_tenant_fields():
    with pytest.raises(ValidationError):
        KhataLedgerMovementArgs.model_validate({
            "operation": "CREDIT",
            "customer_phone": "9876543210",
            "amount": 250,
            "shop_id": 999,
        })


def test_khata_tool_requires_valid_indian_mobile_and_positive_amount():
    with pytest.raises(ValidationError):
        KhataLedgerMovementArgs.model_validate({
            "operation": "CREDIT",
            "customer_phone": "1234567890",
            "amount": 250,
        })
    with pytest.raises(ValidationError):
        KhataLedgerMovementArgs.model_validate({
            "operation": "REPAYMENT",
            "customer_phone": "9876543210",
            "amount": 0,
        })


def test_khata_credit_accepts_name_without_phone():
    parsed = KhataLedgerMovementArgs.model_validate({
        "operation": "CREDIT",
        "customer_name": "Ganesh",
        "amount": 5000,
    })
    assert parsed.customer_phone is None
    assert parsed.customer_name == "Ganesh"


def test_khata_tool_requires_either_name_or_phone():
    with pytest.raises(ValidationError):
        KhataLedgerMovementArgs.model_validate({
            "operation": "CREDIT",
            "amount": 5000,
        })


def test_name_only_khata_credit_prepares_preview_without_mutating_ledger():
    db = _Db(khata_matches=[], customer_matches=[])
    result = prepare_khata_ledger_movement(
        db,
        shop_id=42,
        conversation_id="conversation-ganesh",
        request_text="add 5000 khata for Ganesh",
        operation="CREDIT",
        customer_phone=None,
        amount=Decimal("5000"),
        customer_name="Ganesh",
    )
    assert result["success"] is True
    assert result["preview"]["customer_name"] == "Ganesh"
    assert result["preview"]["amount"] == 5000.0
    assert result["preview"]["balance_before"] == 0.0
    assert result["preview"]["balance_after"] == 5000.0
    assert result["preview"]["customer_phone_last4"] is None
    assert db.added[0].payload["customer_phone"] is None
    assert db.added[0].status == "PENDING"


def test_name_only_khata_lookup_rejects_duplicate_names():
    matches = [
        SimpleNamespace(customer_name="Ganesh", customer_phone="9876543210", khata_balance=Decimal("0")),
        SimpleNamespace(customer_name="Ganesh", customer_phone="9876543211", khata_balance=Decimal("0")),
    ]
    db = _Db(khata_matches=matches)
    with pytest.raises(ValueError, match="More than one Khata customer"):
        prepare_khata_ledger_movement(
            db,
            shop_id=42,
            conversation_id="conversation-ambiguous",
            request_text="add 5000 khata for Ganesh",
            operation="CREDIT",
            customer_phone=None,
            amount=Decimal("5000"),
            customer_name="Ganesh",
        )


def test_name_only_repayment_requires_an_existing_shop_scoped_khata_account():
    db = _Db(khata_matches=[], customer_matches=[])
    with pytest.raises(ValueError, match="No existing Khata account"):
        prepare_khata_ledger_movement(
            db,
            shop_id=42,
            conversation_id="conversation-repay",
            request_text="Ganesh paid 500",
            operation="REPAYMENT",
            customer_phone=None,
            amount=Decimal("500"),
            customer_name="Ganesh",
        )


def test_khata_tool_has_allowlisted_preview_function():
    names = {
        item["function"]["name"]
        for item in TOOL_DEFINITIONS
        if item.get("type") == "function"
    }
    assert "prepare_khata_ledger_movement" in names


def test_khata_credit_creates_preview_without_mutating_account():
    account = SimpleNamespace(khata_balance=Decimal("100.00"), customer_name="Ravi")
    db = _Db(account)
    result = prepare_khata_ledger_movement(
        db,
        shop_id=42,
        conversation_id="conversation-1",
        request_text="add 250 khata for Ravi",
        operation="CREDIT",
        customer_phone="9876543210",
        amount=Decimal("250"),
        customer_name="Ravi",
    )
    assert result["success"] is True
    assert result["preview"]["balance_before"] == 100.0
    assert result["preview"]["balance_after"] == 350.0
    assert result["preview"]["requires_owner_confirmation"] is True
    assert account.khata_balance == Decimal("100.00")
    assert len(db.added) == 1
    assert db.added[0].action_type == "KHATA_LEDGER_MOVEMENT"


def test_khata_repayment_cannot_exceed_current_balance():
    db = _Db(SimpleNamespace(khata_balance=Decimal("100.00"), customer_name="Ravi"))
    with pytest.raises(ValueError, match="cannot exceed"):
        prepare_khata_ledger_movement(
            db,
            shop_id=42,
            conversation_id="conversation-1",
            request_text="repay 150",
            operation="REPAYMENT",
            customer_phone="9876543210",
            amount=Decimal("150"),
        )


def test_khata_repayment_preview_calculates_remaining_balance():
    db = _Db(SimpleNamespace(khata_balance=Decimal("100.00"), customer_name="Ravi"))
    result = prepare_khata_ledger_movement(
        db,
        shop_id=42,
        conversation_id="conversation-2",
        request_text="repay 35",
        operation="REPAYMENT",
        customer_phone="9876543210",
        amount=Decimal("35"),
    )
    assert result["preview"]["balance_after"] == 65.0
    assert result["preview"]["operation"] == "RECORD_KHATA_REPAYMENT"


def test_legacy_khata_history_maps_original_columns_and_unique_replay_key():
    columns = set(KhataHistory.__table__.columns.keys())
    assert {"reference_id", "description", "transaction_date", "idempotency_key"} <= columns
    indexes = {index.name: index for index in KhataHistory.__table__.indexes}
    assert indexes["uq_khata_history_idempotency_key"].unique is True


def test_registry_marks_khata_record_as_implemented_but_confirmation_required(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "true")
    capabilities = {item["name"]: item for item in list_capabilities()}
    khata = capabilities["khata.record"]
    assert khata["implemented"] is True
    assert khata["requires_confirmation"] is True
    assert khata["enabled"] is True


def test_new_khata_action_remains_off_when_agent_feature_flag_is_off(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "false")
    capabilities = {item["name"]: item for item in list_capabilities()}
    assert capabilities["khata.record"]["implemented"] is True
    assert capabilities["khata.record"]["enabled"] is False
