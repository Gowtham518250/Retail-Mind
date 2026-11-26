"""Regression coverage for customer identity in AI-prepared invoice previews."""
import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "retail-mind-agent-ci-only-not-for-production")

import inventory as inventory_module
from agentic import tools as agent_tools
from agentic.graph import _format_pending_action_answer
from models import Customer


class _Query:
    def __init__(self, result=None):
        self.result = result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.result


class _DB:
    def __init__(self, customer=None):
        self.customer = customer
        self.added = []

    def query(self, model):
        if model is Customer:
            return _Query(self.customer)
        return _Query(None)

    def add(self, value):
        self.added.append(value)

    def flush(self):
        return None


def _mock_parser(monkeypatch, captured):
    async def fake_parse(request, *, user_id, db):
        captured["transcript"] = request.transcript
        return {
            "success": True,
            "needs_clarification": False,
            "items": [
                {
                    "product_name": "Ghee",
                    "quantity": 5,
                    "unit_price": 1000,
                    "needs_confirmation": False,
                    "price_missing": False,
                    "price_needs_confirmation": False,
                }
            ],
        }

    monkeypatch.setattr(inventory_module, "parse_voice_billing", fake_parse)


def test_formatted_indian_mobile_and_customer_name_are_extracted():
    text = (
        "Create an invoice for Ganesh "
        "(phone +91 93475 88819) for Ghee, 5 kg at ₹1,000 per kg."
    )
    assert agent_tools._extract_indian_mobile(text) == "9347588819"
    assert agent_tools._extract_bill_customer_name(text) == "Ganesh"


def test_bill_preview_preserves_explicit_customer_name_and_phone(monkeypatch):
    captured = {}
    _mock_parser(monkeypatch, captured)
    db = _DB()

    result = asyncio.run(
        agent_tools._prepare_bill(
            db,
            {
                "shop_id": 1,
                "conversation_id": "a4b47f00-94a6-40e6-8540-72c5db03f501",
                "user_text": (
                    "Create an invoice for Ganesh "
                    "(phone +91 93475 88819) for Ghee, 5 kg at ₹1,000 per kg."
                ),
                "language_code": "en",
                "recent_user_messages": [],
            },
        )
    )

    assert result["success"] is True
    assert result["preview"]["customer_name"] == "Ganesh"
    assert result["preview"]["customer_phone"] == "9347588819"
    assert result["preview"]["items"][0]["product_name"] == "Ghee"
    assert result["preview"]["total_amount"] == 5000.0
    assert captured["transcript"].startswith("Ghee")
    assert "Ganesh" not in captured["transcript"]
    assert "9347588819" not in captured["transcript"]
    assert "phone" not in captured["transcript"].lower()
    action = db.added[0]
    assert action.payload["customer_name"] == "Ganesh"
    assert action.payload["customer_phone"] == "9347588819"


def test_phone_name_conflict_requires_clarification_before_preview(monkeypatch):
    captured = {}
    _mock_parser(monkeypatch, captured)
    saved_customer = SimpleNamespace(customer_name="Ramesh Kumar")
    db = _DB(customer=saved_customer)

    result = asyncio.run(
        agent_tools._prepare_bill(
            db,
            {
                "shop_id": 1,
                "conversation_id": "a4b47f00-94a6-40e6-8540-72c5db03f501",
                "user_text": (
                    "Create an invoice for Ganesh "
                    "(phone +91 93475 88819) for Ghee, 5 kg at ₹1,000 per kg."
                ),
                "language_code": "en",
                "recent_user_messages": [],
            },
        )
    )

    assert result["success"] is False
    assert result["needs_clarification"] is True
    assert "Ramesh Kumar" in result["message"]
    assert "Ganesh" in result["message"]
    assert not db.added


def test_bill_preview_answer_echoes_customer_name_and_phone():
    answer = _format_pending_action_answer(
        {
            "status": "PENDING",
            "preview": {
                "operation": "CREATE_INVOICE",
                "invoice_number": "AIM-20261127-TEST",
                "customer_name": "Ganesh",
                "customer_phone": "9347588819",
                "total_amount": 5000,
                "items": [
                    {
                        "product_name": "Ghee",
                        "quantity": 5,
                        "unit_price": 1000,
                        "line_total": 5000,
                    }
                ],
            },
        },
        "en",
    )

    assert "Bill preview is ready for Ganesh." in answer
    assert "Customer phone: 9347588819" in answer

def test_new_unrelated_bill_does_not_inherit_previous_customer_identity(monkeypatch):
    captured = {}
    _mock_parser(monkeypatch, captured)
    db = _DB()

    result = asyncio.run(
        agent_tools._prepare_bill(
            db,
            {
                "shop_id": 1,
                "conversation_id": "a4b47f00-94a6-40e6-8540-72c5db03f501",
                "user_text": "Create a new bill for rice, 2 kg at ₹80 per kg.",
                "language_code": "en",
                "recent_user_messages": [
                    "Create an invoice for Ganesh (phone +91 93475 88819) for Ghee, 5 kg at ₹1,000 per kg."
                ],
            },
        )
    )

    assert result["success"] is True
    assert result["preview"]["customer_name"] == "Cash Customer"
    assert result["preview"]["customer_phone"] is None
