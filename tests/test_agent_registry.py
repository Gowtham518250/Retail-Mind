"""Contract and fast unit checks for the Retail Mind agent runtime."""
import os

# security.py intentionally refuses to start without a secret; CI uses a
# disposable test-only value and never reads production credentials.
os.environ.setdefault("SECRET_KEY", "retail-mind-agent-ci-only-not-for-production")

import pytest
from pydantic import ValidationError

from agentic.graph import build_agent_graph
from agentic.registry import list_capabilities
from agentic.service import _action_hash
from agentic.tools import (
    CustomerSearchArgs,
    InventorySearchArgs,
    KhataPaymentPreviewArgs,
    OrderTransitionPreviewArgs,
    _customer_search,
    _inventory_search,
)
from models import AgentConversation, AgentMessage, AgentPendingAction, AgentToolExecution
from sarvam_tts import clean_speech_text, sarvam_tts_language_code
from agentic.routes import router


def _flatten_params(expression):
    return expression.compile().params


def test_registry_reports_real_capabilities_but_keeps_writes_gated(monkeypatch):
    monkeypatch.delenv("RETAIL_MIND_AGENT_ENABLED", raising=False)
    capabilities = {item["name"]: item for item in list_capabilities()}
    assert capabilities["inventory.lookup"]["implemented"] is True
    assert capabilities["inventory.manage"]["implemented"] is True
    assert capabilities["inventory.manage"]["enabled"] is False
    assert capabilities["inventory.manage"]["requires_confirmation"] is True
    assert capabilities["billing.prepare"]["implemented"] is True
    assert capabilities["billing.confirm"]["requires_confirmation"] is True
    assert capabilities["khata.payment"]["implemented"] is True
    assert capabilities["orders.transition"]["implemented"] is True
    assert capabilities["khata.record"]["implemented"] is True
    assert capabilities["khata.record"]["requires_confirmation"] is True
    assert capabilities["orders.manage"]["implemented"] is False
    assert all(item["enabled"] is False for item in capabilities.values())

    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("SARVAM_API_KEY", "test-sarvam-key")
    enabled = {item["name"]: item for item in list_capabilities()}
    assert enabled["inventory.lookup"]["enabled"] is True
    assert enabled["billing.confirm"]["enabled"] is True
    assert enabled["khata.record"]["enabled"] is True


def test_tool_arguments_cannot_supply_a_tenant_or_unexpected_fields():
    with pytest.raises(ValidationError):
        InventorySearchArgs.model_validate({"query": "rice", "shop_id": 77})
    with pytest.raises(ValidationError):
        CustomerSearchArgs.model_validate({"query": "Ravi", "user_id": 77})


def test_inventory_query_always_filters_by_authenticated_shop():
    class Query:
        def __init__(self, rows):
            self.rows = rows
            self.criteria = []

        def filter(self, *criteria):
            self.criteria.extend(criteria)
            return self

        def order_by(self, *_):
            return self

        def limit(self, *_):
            return self

        def all(self):
            return self.rows

    class DB:
        def __init__(self, rows):
            self.rows = rows
            self.query_object = None

        def query(self, _model):
            self.query_object = Query(self.rows)
            return self.query_object

    db = DB([])
    result = _inventory_search(db, 42, InventorySearchArgs(query="rice"))
    assert result["count"] == 0
    compiled = [param for item in db.query_object.criteria for param in _flatten_params(item).values()]
    assert 42 in compiled


def test_customer_query_always_filters_by_authenticated_shop():
    class Query:
        def __init__(self):
            self.criteria = []

        def filter(self, *criteria):
            self.criteria.extend(criteria)
            return self

        def order_by(self, *_):
            return self

        def limit(self, *_):
            return self

        def all(self):
            return []

    class DB:
        def query(self, _model):
            self.query_object = Query()
            return self.query_object

    db = DB()
    result = _customer_search(db, 89, CustomerSearchArgs(query="Kumar"))
    assert result["count"] == 0
    compiled = [param for item in db.query_object.criteria for param in _flatten_params(item).values()]
    assert 89 in compiled


def test_graph_compiles_without_provider_credentials():
    graph = build_agent_graph()
    assert graph is not None


def test_pending_action_preview_hash_binds_shop_and_payload():
    preview = {"total_amount": 125.0}
    payload = {"invoice_number": "AIM-TEST", "items": [{"qty": 1}]}
    first = _action_hash("action-1", 10, preview, payload)
    assert _action_hash("action-1", 10, preview, payload) == first
    assert _action_hash("action-1", 11, preview, payload) != first
    assert _action_hash("action-1", 10, preview, {"invoice_number": "AIM-CHANGED"}) != first


def test_agent_tables_are_declared_for_migration():
    assert AgentConversation.__tablename__ == "agent_conversations"
    assert AgentMessage.__tablename__ == "agent_messages"
    assert AgentPendingAction.__tablename__ == "agent_pending_actions"
    assert AgentToolExecution.__tablename__ == "agent_tool_executions"


def test_sarvam_tts_supports_selected_indian_languages():
    assert sarvam_tts_language_code("te") == "te-IN"
    assert sarvam_tts_language_code("ta-IN") == "ta-IN"
    assert sarvam_tts_language_code("or") == "od-IN"
    with pytest.raises(ValueError):
        sarvam_tts_language_code("fr")


def test_tts_text_cleanup_removes_markdown_links_and_urls():
    clean = clean_speech_text("**Sales** [dashboard](https://example.test) and https://example.test/a")
    assert "Sales" in clean
    assert "dashboard" in clean
    assert "https://" not in clean
    assert "**" not in clean



def test_payment_preview_requires_one_invoice_and_rejects_extra_tenant_fields():
    valid = KhataPaymentPreviewArgs.model_validate({
        "invoice_id": 123,
        "amount": 500,
        "payment_method": "UPI",
    })
    assert valid.invoice_id == 123
    assert valid.amount == 500
    with pytest.raises(ValidationError):
        KhataPaymentPreviewArgs.model_validate({
            "invoice_id": 123, "amount": 500, "shop_id": 7,
        })


def test_order_transition_preview_only_allows_confirmable_transitions():
    assert OrderTransitionPreviewArgs.model_validate({
        "order_id": 9, "action": "REJECT"
    }).action == "REJECT"
    with pytest.raises(ValidationError):
        OrderTransitionPreviewArgs.model_validate({
            "order_id": 9, "action": "DELIVER"
        })
    with pytest.raises(ValidationError):
        OrderTransitionPreviewArgs.model_validate({
            "order_id": 9, "action": "CANCEL"
        })


def test_registry_keeps_delivery_and_legacy_financial_writes_disabled(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("SARVAM_API_KEY", "test-sarvam-key")
    capabilities = {item["name"]: item for item in list_capabilities()}
    assert capabilities["khata.payment"]["enabled"] is True
    assert capabilities["orders.transition"]["enabled"] is True
    assert capabilities["khata.record"]["enabled"] is True
    assert capabilities["khata.record"]["requires_confirmation"] is True
    assert capabilities["orders.manage"]["enabled"] is False
    assert capabilities["attendance.manage"]["implemented"] is True
    assert capabilities["attendance.manage"]["enabled"] is True
    assert capabilities["attendance.manage"]["requires_confirmation"] is True
    assert capabilities["workers.lookup"]["implemented"] is True
    assert capabilities["workers.lookup"]["enabled"] is True
    assert capabilities["workers.lookup"]["requires_confirmation"] is False


def test_agent_routes_are_registered():
    route_map = {(route.path, method) for route in router.routes for method in getattr(route, "methods", set())}
    assert ("/api/agent/chat", "POST") in route_map
    assert ("/api/agent/voice", "POST") in route_map
    assert ("/api/agent/speech", "POST") in route_map
    assert ("/api/agent/actions/{action_id}/confirm", "POST") in route_map
    assert ("/api/agent/conversations", "GET") in route_map
