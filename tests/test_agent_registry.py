"""Contract and fast unit checks for the Retail Mind agent runtime."""
import os
import asyncio
from types import SimpleNamespace

# security.py intentionally refuses to start without a secret; CI uses a
# disposable test-only value and never reads production credentials.
os.environ.setdefault("SECRET_KEY", "retail-mind-agent-ci-only-not-for-production")

import pytest
from pydantic import ValidationError

from langgraph.graph import END
from agentic.graph import (
    build_agent_graph, available_tool_definitions,
    _format_pending_action_answer, _route_after_tools, _forced_action_tool,
)
from agentic.registry import list_capabilities
from agentic.service import _action_hash
from agentic.tools import (
    CustomerSearchArgs,
    InventorySearchArgs,
    KhataPaymentPreviewArgs,
    OrderTransitionPreviewArgs,
    _customer_search,
    _inventory_search,
    _is_bill_follow_up_message,
    _clean_bill_instruction_filler,
    _recent_bill_context,
    _recent_bill_source_transcript,
    _prepare_bill,
)
from models import (
    AgentConversation, AgentMessage, AgentPendingAction, AgentToolExecution,
    AgentShopSettings,
)
from agentic.access import resolve_agent_access
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


def test_successful_action_preview_skips_second_provider_call_and_uses_saved_values():
    action = {
        "success": True,
        "action_id": "action-123",
        "status": "PENDING",
        "preview_hash": "a" * 64,
        "preview": {
            "operation": "CREATE_INVOICE",
            "invoice_number": "AIM-TEST-123",
            "customer_name": "Cash Customer",
            "total_amount": 200.0,
            "items": [{
                "product_name": "rice",
                "quantity": 1.0,
                "unit_price": 200.0,
                "line_total": 200.0,
            }],
        },
    }
    state = {"tool_outputs": [{"name": "prepare_bill_from_current_message", "result": action}]}

    assert _route_after_tools(state) == END
    answer = _format_pending_action_answer(action)
    assert "rice: 1 × ₹200.00 = ₹200.00" in answer
    assert "Total: ₹200.00" in answer
    assert "No invoice has been created" in answer


def test_failed_tool_result_still_routes_to_model_for_clarification():
    state = {"tool_outputs": [{"result": {"success": False, "message": "Need more details"}}]}
    assert _route_after_tools(state) == "call_model"


def test_bill_follow_up_uses_only_recent_owner_authored_context():
    assert _is_bill_follow_up_message("ok create the bill with 10 rupees") is True
    assert _is_bill_follow_up_message("rice with price 200 with quantity 1") is False

    context = {
        "recent_user_messages": [
            "rice with price 200 with quantity 1",
            "my customer number is 9876543210",
        ]
    }
    result = _recent_bill_context(context, "ok create the bill with 10 rupees")
    assert result is not None
    assert "rice with price 200 with quantity 1" in result
    assert "9876543210" not in result
    assert "Latest owner reply: ok create the bill with 10 rupees" in result
    assert _recent_bill_context(context, "add 2 milk at ₹60") is None


def test_bill_follow_up_restores_item_source_for_numeric_price_grounding():
    context = {
        "recent_user_messages": [
            "rice with price 200 with quantity 1",
            "just create the bill with 200",
        ]
    }
    merged = _recent_bill_source_transcript(context, "ok create the bill with 10 rupees")
    assert merged == (
        "rice with price 200 with quantity 1. Latest owner instruction: "
        "ok create the bill with 10 rupees"
    )

    # A complete new item request must not inherit an unrelated previous sale.
    fresh = _recent_bill_source_transcript(context, "add 2 milk at 60 rupees")
    assert fresh == "add 2 milk at 60 rupees"


def test_explicit_bill_request_forces_bill_preview_without_inventory_search():
    state = {
        "context": {
            "user_text": "Create a bill for rice, quantity 1, price ₹200",
            "allow_actions": True,
        },
        "tool_definitions": available_tool_definitions(True),
        "tool_rounds": 0,
    }
    assert _forced_action_tool(state) == "prepare_bill_from_current_message"


def test_bill_price_follow_up_forces_bill_preview_but_tutorial_does_not():
    tools = available_tool_definitions(True)
    follow_up = {
        "context": {
            "user_text": "okay, use ₹10",
            "allow_actions": True,
            "recent_user_messages": ["create a bill for rice, quantity 1, price ₹200"],
        },
        "tool_definitions": tools,
        "tool_rounds": 0,
    }
    tutorial = {
        "context": {
            "user_text": "How do I create a bill?",
            "allow_actions": True,
        },
        "tool_definitions": tools,
        "tool_rounds": 0,
    }
    assert _forced_action_tool(follow_up) == "prepare_bill_from_current_message"
    assert _forced_action_tool(tutorial) is None


def test_name_and_amount_khata_request_forces_scoped_khata_preview():
    state = {
        "context": {
            "user_text": "Create Khata for Ganesh with amount ₹5,000",
            "allow_actions": True,
        },
        "tool_definitions": available_tool_definitions(True),
        "tool_rounds": 0,
    }
    assert _forced_action_tool(state) == "prepare_khata_ledger_movement"


def test_bill_preview_keeps_spoken_price_and_never_tracks_stock(monkeypatch):
    import inventory as inventory_module

    captured = {}

    async def fake_parse(request, *, user_id, db):
        captured["request"] = request
        captured["user_id"] = user_id
        return {
            "success": True,
            "needs_clarification": False,
            "items": [{
                # A catalog link is deliberately ignored by the AI invoice path.
                "product_id": 7,
                "product_name": "rice",
                "quantity": 1,
                "unit_price": 200,
                "needs_confirmation": False,
                "price_missing": False,
                "price_needs_confirmation": False,
            }],
        }

    class Query:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class Db:
        def __init__(self):
            self.added = []

        def query(self, model):
            assert model is AgentPendingAction
            return Query()

        def add(self, value):
            self.added.append(value)

        def flush(self):
            return None

    monkeypatch.setattr(inventory_module, "parse_voice_billing", fake_parse)
    db = Db()
    result = asyncio.run(_prepare_bill(
        db,
        {
            "shop_id": 42,
            "conversation_id": "a4b47f00-94a6-40e6-8540-72c5db03f501",
            "user_text": "Create a bill for rice, quantity 1, price ₹200",
            "language_code": "te",
            "recent_user_messages": [],
        },
    ))

    assert result["success"] is True
    assert captured["user_id"] == 42
    line = result["preview"]["items"][0]
    assert line["product_id"] is None
    assert line["stock_tracked"] is False
    assert line["unit_price"] == 200.0
    assert line["line_total"] == 200.0
    assert result["preview"]["total_amount"] == 200.0
    assert db.added[0].payload["line_items"][0]["stock_tracked"] is False
    assert "conversation_context" in captured["request"].model_fields_set or captured["request"].conversation_context is None


def test_saved_bill_answer_uses_the_owner_selected_language():
    action = {
        "success": True,
        "action_id": "action-language",
        "status": "PENDING",
        "preview_hash": "a" * 64,
        "preview": {
            "operation": "CREATE_INVOICE",
            "invoice_number": "AIM-TE-100",
            "customer_name": "Ganesh",
            "total_amount": 200.0,
            "items": [{
                "product_name": "rice",
                "quantity": 1.0,
                "unit_price": 200.0,
                "line_total": 200.0,
            }],
        },
    }
    answer = _format_pending_action_answer(action, "te-IN")
    assert "బిల్ ప్రివ్యూ" in answer
    assert "₹200.00" in answer
    assert "స్టాక్" in answer


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
    assert AgentShopSettings.__tablename__ == "rm_shop_agent_settings"


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


def test_agent_access_requires_platform_plan_and_owner_opt_in():
    entitlement = {
        "plan_code": "PRO",
        "features": {
            "ai_agent": True,
            "ai_agent_voice": True,
            "ai_agent_actions": False,
        },
        "daily_ai_query_limit": 25,
    }
    preferences = {
        "assistant_enabled": True,
        "voice_enabled": True,
        "actions_enabled": True,
    }
    access = resolve_agent_access(
        platform_enabled=True,
        groq_configured=True,
        sarvam_configured=True,
        entitlement=entitlement,
        preferences=preferences,
    )
    assert access["assistant_enabled"] is True
    assert access["voice_enabled"] is True
    assert access["actions_enabled"] is False
    assert access["plan_access"]["actions"] is False


def test_agent_is_off_for_free_plan_even_when_owner_opts_in():
    entitlement = {
        "plan_code": "FREE",
        "features": {
            "ai_agent": False,
            "ai_agent_voice": False,
            "ai_agent_actions": False,
        },
        "daily_ai_query_limit": 0,
    }
    preferences = {
        "assistant_enabled": True,
        "voice_enabled": True,
        "actions_enabled": True,
    }
    access = resolve_agent_access(
        platform_enabled=True,
        groq_configured=True,
        sarvam_configured=True,
        entitlement=entitlement,
        preferences=preferences,
    )
    assert access["assistant_enabled"] is False
    assert access["voice_enabled"] is False
    assert access["actions_enabled"] is False
    assert access["status"] == "plan_required"


def test_agent_owner_preferences_are_disabled_by_default():
    entitlement = {
        "plan_code": "BASIC",
        "features": {"ai_agent": True, "ai_agent_voice": False, "ai_agent_actions": False},
        "daily_ai_query_limit": 7,
    }
    access = resolve_agent_access(
        platform_enabled=True,
        groq_configured=True,
        sarvam_configured=False,
        entitlement=entitlement,
        preferences={},
    )
    assert access["assistant_enabled"] is False
    assert access["voice_enabled"] is False
    assert access["actions_enabled"] is False
    assert access["status"] == "owner_disabled"


def test_agent_voice_needs_sarvam_and_owner_consent():
    entitlement = {
        "plan_code": "PRO",
        "features": {"ai_agent": True, "ai_agent_voice": True, "ai_agent_actions": False},
        "daily_ai_query_limit": 25,
    }
    preferences = {"assistant_enabled": True, "voice_enabled": True, "actions_enabled": False}
    missing_provider = resolve_agent_access(
        platform_enabled=True, groq_configured=True, sarvam_configured=False,
        entitlement=entitlement, preferences=preferences,
    )
    assert missing_provider["assistant_enabled"] is True
    assert missing_provider["voice_enabled"] is False
    assert missing_provider["status"] == "enabled"


def test_business_operation_tools_are_not_exposed_without_owner_action_opt_in():
    read_only_names = {
        item["function"]["name"] for item in available_tool_definitions(False)
    }
    all_names = {
        item["function"]["name"] for item in available_tool_definitions(True)
    }
    action_names = {
        "prepare_bill_from_current_message",
        "prepare_invoice_payment",
        "prepare_online_order_transition",
        "prepare_inventory_stock_movement",
        "prepare_attendance_record",
        "prepare_khata_ledger_movement",
    }
    assert action_names.isdisjoint(read_only_names)
    assert action_names.issubset(all_names)
    assert "search_inventory" in read_only_names
    assert "get_sales_summary" in read_only_names


def test_bill_instruction_filler_is_removed_without_changing_item_facts():
    assert _clean_bill_instruction_filler(
        "ghee 2 and iam approved to create bill"
    ) == "ghee 2"
    assert _recent_bill_source_transcript(
        {"recent_user_messages": []},
        "ghee 2 and i am approved to create bill",
    ) == "ghee 2"


def test_yes_confirmation_reuses_original_bill_source_and_records_reply():
    context = {
        "recent_user_messages": [
            "ghee 2 and i am approved to create bill",
        ]
    }
    assert _recent_bill_source_transcript(context, "Yes") == "ghee 2"
    parser_context = _recent_bill_context(context, "Yes")
    assert "Earlier owner message 1: ghee 2" in parser_context
    assert "Latest owner reply: Yes" in parser_context
    assert "Latest owner instruction: Yes" not in parser_context


def test_grounded_bill_facts_bypass_generic_model_clarification_and_ask_only_for_price(monkeypatch):
    import inventory as inventory_module

    async def fake_parse(request, *, user_id, db):
        return {
            "success": True,
            "needs_clarification": True,
            "clarification_question": "Please repeat the product name and quantity.",
            "items": [{
                "product_name": "ghee",
                "quantity": 2,
                "quantity_grounded": True,
                "unit_grounded": True,
                "unit_mismatch": False,
                "ambiguous_candidates": [],
                "confidence_inferred": False,
                "price_role_inferred": False,
                "needs_confirmation": True,
                "price_missing": True,
                "price_needs_confirmation": True,
                "price_warning": "Please provide the selling price for ghee.",
            }],
        }

    monkeypatch.setattr(inventory_module, "parse_voice_billing", fake_parse)
    result = asyncio.run(_prepare_bill(
        object(),
        {
            "shop_id": 42,
            "conversation_id": "a4b47f00-94a6-40e6-8540-72c5db03f501",
            "user_text": "Yes",
            "language_code": "en",
            "recent_user_messages": ["ghee 2 and i am approved to create bill"],
        },
    ))
    assert result["success"] is False
    assert result["needs_clarification"] is True
    assert result["message"] == "Please provide the selling price for ghee."
    assert "repeat the product name" not in result["message"].lower()


def test_invoice_phone_number_is_a_bill_follow_up_and_restores_original_bill_details():
    original = "Create an invoice for 2 rice at 50 rupees"
    context = {"recent_user_messages": [original]}
    assert _is_bill_follow_up_message("9876543210") is True
    assert _recent_bill_source_transcript(context, "9876543210") == original


def test_invoice_preview_requests_customer_phone_before_running_parser(monkeypatch):
    import inventory as inventory_module

    def parser_must_not_run(*args, **kwargs):
        raise AssertionError("parser must not run until the mandatory customer phone is supplied")

    monkeypatch.setattr(inventory_module, "parse_voice_billing", parser_must_not_run)
    result = asyncio.run(_prepare_bill(
        object(),
        {
            "shop_id": 42,
            "conversation_id": "c5b98f14-2fbd-4f35-98c9-c24d56b8d031",
            "user_text": "Create an invoice for 2 rice at 50 rupees",
            "language_code": "en",
            "recent_user_messages": [],
        },
    ))
    assert result["success"] is False
    assert result["needs_clarification"] is True
    assert "10-digit mobile number" in result["message"]


def test_standalone_customer_phone_forces_existing_invoice_preview_flow():
    state = {
        "context": {
            "user_text": "9876543210",
            "allow_actions": True,
            "recent_user_messages": ["Create an invoice for 2 rice at 50 rupees"],
        },
        "tool_definitions": available_tool_definitions(True),
        "tool_rounds": 0,
    }
    assert _forced_action_tool(state) == "prepare_bill_from_current_message"
