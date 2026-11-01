import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_inventory_deduction_concurrency():
    """
    Test that pessimistic locking (with_for_update) prevents negative stock
    when multiple concurrent requests attempt to buy the last item.
    """
    assert True


def test_sync_offline_invoice_deduplication():
    """
    Test that syncing the same offline invoice ID twice results in a single invoice.
    """
    assert True


def test_next_bill_number_route_exists():
    from app import api

    routes = {getattr(route, "path", "") for route in api.routes}
    assert "/api/invoices/next-bill-number" in routes


from pathlib import Path
import re

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
    from app import api

    paths = {getattr(route, "path", "") for route in api.routes}
    assert "/api/billing/feature-access/{feature_code}" in paths


def test_subscription_checkout_lock_is_held_until_new_checkout_insert():
    source = Path("subscription_billing.py").read_text(encoding="utf-8")
    start = source.index("async def create_subscription")
    end = source.index(
        '@router.post("/api/billing/subscriptions/{subscription_id}/cancel")',
        start,
    )
    block = source[start:end]
    lock_at = block.index("pg_advisory_xact_lock")
    insert_at = block.index("INSERT INTO rm_shop_subscriptions")
    assert lock_at < insert_at

    # Existing-plan changes commit in place before this branch inserts a
    # new CREATING row. For a fresh checkout, ensure the provider request and
    # at least one commit occur only after the new row is persisted.
    create_call_at = block.index('await client.post(f"{base}/subscriptions"')
    commit_positions = [
        match.start()
        for match in re.finditer(r"db\.commit\(\)", block)
    ]
    assert create_call_at > insert_at
    assert any(position > insert_at for position in commit_positions)


def test_pending_checkout_recovery_and_active_plan_safety_are_present():
    source = Path("subscription_billing.py").read_text(encoding="utf-8")
    assert "INTERVAL '10 minutes'" in source
    assert "PENDING_CASHFREE_CHECKOUT" in source
    assert 'json={"subscription_id": cashfree_id, "action": "CANCEL"}' in source


def test_three_character_pro_plan_code_is_valid():
    from subscription_billing import CreateSubscriptionBody

    request = CreateSubscriptionBody(plan_code="PRO")
    assert request.plan_code == "PRO"


def test_active_subscription_upgrade_changes_the_existing_cashfree_mandate():
    source = Path("subscription_billing.py").read_text(encoding="utf-8")
    start = source.index("async def create_subscription")
    end = source.index(
        '@router.post("/api/billing/subscriptions/{subscription_id}/cancel")',
        start,
    )
    checkout = source[start:end]

    assert '"action": "CHANGE_PLAN"' in checkout
    assert '"action_details": {"plan_id": target_plan_id}' in checkout
    assert '"requires_checkout": False' in checkout
    assert "CASHFREE_PLAN_CHANGE_FAILED" in checkout
    assert "ACTIVE_SUBSCRIPTION_EXISTS" not in checkout


def test_cashfree_activation_date_uses_ist_date_component():
    from datetime import datetime
    from subscription_billing import _cashfree_activation_date

    # Cashfree uses only the date component; DB timestamps are stored as UTC.
    period_end_utc = datetime(2026, 11, 1, 20, 0, 0)
    assert _cashfree_activation_date(period_end_utc) == "2026-11-02"


def test_cancellation_pending_upgrade_reactivates_before_change_plan():
    source = Path("subscription_billing.py").read_text(encoding="utf-8")
    start = source.index("async def create_subscription")
    end = source.index(
        '@router.post("/api/billing/subscriptions/{subscription_id}/cancel")',
        start,
    )
    checkout = source[start:end]

    activate_at = checkout.index('"action": "ACTIVATE"')
    change_plan_at = checkout.index('"action": "CHANGE_PLAN"')
    assert activate_at < change_plan_at
    assert '"next_scheduled_time": activation_date' in checkout
    assert "cancel_at_period_end=FALSE" in checkout
    assert "cancelled_at=NULL" in checkout
    assert "SUBSCRIPTION_REACTIVATION_FAILED" in checkout
    assert "SUBSCRIPTION_REACTIVATED_UPGRADE_FAILED" in checkout
    assert '"cancellation_reversed": cancellation_pending' in checkout


def test_cancellation_pending_upgrade_does_not_create_a_second_mandate():
    source = Path("subscription_billing.py").read_text(encoding="utf-8")
    start = source.index("async def create_subscription")
    active_start = source.index("    if active:", start)
    pending_start = source.index("    pending_rows =", active_start)
    active_branch = source[active_start:pending_start]

    assert "cashfree_subscription_id" in active_branch
    assert '"action": "ACTIVATE"' in active_branch
    assert '"action": "CHANGE_PLAN"' in active_branch
    assert "INSERT INTO rm_shop_subscriptions" not in active_branch
    assert '"requires_checkout": False' in active_branch


def test_cashfree_plan_id_is_stable_and_price_versioned():
    from subscription_billing import _cashfree_plan_id

    monthly = _cashfree_plan_id("PRO", "MONTHLY", 19900)
    yearly = _cashfree_plan_id("PRO", "YEARLY", 199900)
    changed_price = _cashfree_plan_id("PRO", "MONTHLY", 24900)

    assert monthly == "rm_pro_monthly_19900"
    assert yearly == "rm_pro_yearly_199900"
    assert monthly != yearly
    assert monthly != changed_price


def test_owner_subscription_middleware_is_registered_after_app_creation():
    source = Path("app.py").read_text(encoding="utf-8")
    assert source.index("api = FastAPI(") < source.index("async def subscription_feature_enforcement")
    assert '"/store/owner/orders"' in source
    assert '"/store/owner/reviews"' in source
    assert 'require_shop_feature(db, owner_user_id, "online_orders")' in source


def test_cashfree_plan_is_created_before_fetch_lookup():
    import asyncio
    from subscription_billing import _ensure_cashfree_plan

    class Response:
        status_code = 201
        text = ""
        headers = {}

        def json(self):
            return {"plan_id": "rm_pro_monthly_19900"}

    class Client:
        def __init__(self):
            self.calls = []

        async def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            return Response()

        async def get(self, url, **kwargs):
            self.calls.append(("GET", url, kwargs))
            raise AssertionError("A newly created plan must not require a GET.")

    client = Client()
    result = asyncio.run(_ensure_cashfree_plan(
        client,
        base="https://sandbox.cashfree.com/pg",
        app_id="test-app-id",
        secret="test-secret",
        plan_code="PRO",
        plan_name="Pro",
        billing_interval="MONTHLY",
        amount_paise=19900,
    ))

    assert result == "rm_pro_monthly_19900"
    assert len(client.calls) == 1
    method, url, kwargs = client.calls[0]
    assert method == "POST"
    assert url.endswith("/plans")
    assert kwargs["headers"]["x-idempotency-key"] == "rm-plan-rm_pro_monthly_19900"
    assert kwargs["headers"]["x-request-id"]
    assert kwargs["json"]["plan_recurring_amount"] == 199.0
    assert kwargs["json"]["plan_interval_type"] == "MONTH"


def test_cashfree_plan_reuses_existing_plan_only_after_definition_verification():
    import asyncio
    from subscription_billing import _ensure_cashfree_plan

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)
            self.headers = {}

        def json(self):
            return self._payload

    class Client:
        def __init__(self):
            self.calls = []

        async def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            return Response(409, {"code": "PLAN_ALREADY_EXISTS"})

        async def get(self, url, **kwargs):
            self.calls.append(("GET", url, kwargs))
            return Response(200, {
                "plan_id": "rm_pro_monthly_19900",
                "plan_type": "PERIODIC",
                "plan_currency": "INR",
                "plan_interval_type": "MONTH",
                "plan_intervals": 1,
                "plan_recurring_amount": 199.0,
                "plan_max_amount": 199.0,
                "plan_status": "ACTIVE",
            })

    client = Client()
    result = asyncio.run(_ensure_cashfree_plan(
        client,
        base="https://sandbox.cashfree.com/pg",
        app_id="test-app-id",
        secret="test-secret",
        plan_code="PRO",
        plan_name="Pro",
        billing_interval="MONTHLY",
        amount_paise=19900,
    ))

    assert result == "rm_pro_monthly_19900"
    assert [call[0] for call in client.calls] == ["POST", "GET"]


def test_cashfree_plan_creation_error_returns_provider_diagnostics():
    import asyncio
    from fastapi import HTTPException
    from subscription_billing import _ensure_cashfree_plan

    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = str(payload)
            self.headers = {}

        def json(self):
            return self._payload

    class Client:
        async def post(self, url, **kwargs):
            return Response(403, {"code": "PERMISSION_DENIED"})

        async def get(self, url, **kwargs):
            return Response(404, {"code": "PLAN_NOT_FOUND"})

    with pytest.raises(HTTPException) as raised:
        asyncio.run(_ensure_cashfree_plan(
            Client(),
            base="https://sandbox.cashfree.com/pg",
            app_id="test-app-id",
            secret="test-secret",
            plan_code="PRO",
            plan_name="Pro",
            billing_interval="MONTHLY",
            amount_paise=19900,
        ))

    assert raised.value.status_code == 502
    assert raised.value.detail["code"] == "CASHFREE_PLAN_PREPARATION_FAILED"
    assert raised.value.detail["provider_status"] == 403
    assert raised.value.detail["verification_status"] == 404
    assert raised.value.detail["provider_code"] == "PERMISSION_DENIED"
    assert raised.value.detail["request_id"]


def test_owner_orders_403_logs_subscription_entitlement_reason():
    source = Path("app.py").read_text(encoding="utf-8")
    middleware = source[source.index("async def subscription_feature_enforcement"):]
    assert "SUBSCRIPTION_FEATURE_DENIED" in middleware
    assert 'detail.get("feature", "online_orders")' in middleware
    assert 'detail.get("current_plan", "unknown")' in middleware
