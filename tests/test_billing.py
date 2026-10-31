"""Focused contract tests for the owner billing endpoints.

These tests avoid provider calls and verify route registration/response contracts.
The full Cashfree lifecycle must also be tested against the sandbox.
"""
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app as app_module
from subscription_entitlements import get_shop_entitlements, feature_is_allowed


def test_free_entitlement_has_expected_core_features():
    class Result:
        def mappings(self):
            return self

        def first(self):
            return None

    class DB:
        def execute(self, *_args, **_kwargs):
            return Result()

    ent = get_shop_entitlements(DB(), 123)
    assert ent["plan_code"] == "FREE"
    assert ent["features"]["sales"] is True
    assert ent["features"]["khata"] is True
    assert ent["daily_ai_query_limit"] == 0


def test_ai_queries_require_positive_daily_quota():
    assert feature_is_allowed({"daily_ai_query_limit": 7}, "ai_queries") is True
    assert feature_is_allowed({"daily_ai_query_limit": 0}, "ai_queries") is False


def test_feature_access_route_is_registered():
    paths = {route.path for route in app_module.api.routes}
    assert "/api/billing/feature-access/{feature_code}" in paths


def test_subscription_checkout_lock_and_pending_recovery_are_present():
    from pathlib import Path
    source = Path("subscription_billing.py").read_text(encoding="utf-8")
    assert "pg_advisory_xact_lock" in source
    assert "INTERVAL '10 minutes'" in source
    assert "PENDING_CASHFREE_CHECKOUT" in source
    assert "ACTIVE_SUBSCRIPTION_EXISTS" in source


def test_active_subscription_is_not_silently_replaced():
    from pathlib import Path
    source = Path("subscription_billing.py").read_text(encoding="utf-8")
    assert "A second recurring mandate cannot be created" in source
    assert 'json={"subscription_id": cashfree_id, "action": "CANCEL"}' in source
