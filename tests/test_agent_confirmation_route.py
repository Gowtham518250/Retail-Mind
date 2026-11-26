"""Regression test for the agent action confirmation route."""
import os
import uuid

os.environ.setdefault("SECRET_KEY", "retail-mind-agent-ci-only-not-for-production")

from agentic import routes as routes_module


def test_agent_confirmation_route_calls_service_not_itself(monkeypatch):
    action_id = str(uuid.uuid4())
    calls = {}

    monkeypatch.setattr(routes_module, "resolve_shop_id", lambda _user: 123)
    monkeypatch.setattr(
        routes_module,
        "_require_agent_access",
        lambda _db, shop_id, feature: calls.update(access=(shop_id, feature)),
    )

    def fake_service(db, *, shop_id, current_user, action_id, supplied_preview_hash):
        calls["service"] = {
            "db": db,
            "shop_id": shop_id,
            "current_user": current_user,
            "action_id": action_id,
            "supplied_preview_hash": supplied_preview_hash,
        }
        return {"success": True, "status": "COMPLETED"}

    monkeypatch.setattr(
        routes_module, "confirm_agent_action_service", fake_service
    )
    db = object()
    user = {"id": 123}
    request = routes_module.AgentConfirmRequest(preview_hash="a" * 64)

    result = routes_module.confirm_agent_action(
        action_id, request, current_user=user, db=db
    )

    assert result == {"success": True, "status": "COMPLETED"}
    assert calls["access"] == (123, "actions")
    assert calls["service"] == {
        "db": db,
        "shop_id": 123,
        "current_user": user,
        "action_id": action_id,
        "supplied_preview_hash": "a" * 64,
    }
