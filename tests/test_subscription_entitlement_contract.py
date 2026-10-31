import inspect

from subscription_entitlements import (
    check_all_feature_access,
    check_feature_access,
    feature_is_allowed,
    router,
)


def test_batched_feature_access_endpoint_is_registered_alongside_single_feature_route():
    paths = {route.path for route in router.routes}
    assert "/api/billing/feature-access" in paths
    assert "/api/billing/feature-access/{feature_code}" in paths


def test_batched_feature_access_resolves_entitlements_once():
    source = inspect.getsource(check_all_feature_access)
    assert source.count("get_shop_entitlements(") == 1
    assert '"online_orders"' in source
    assert '"ai_queries"' in source
    assert "feature_is_allowed(entitlement, code)" in source


def test_feature_access_uses_server_plan_feature_and_ai_limit():
    entitlement = {
        "features": {"online_orders": True},
        "daily_ai_query_limit": 25,
    }
    assert feature_is_allowed(entitlement, "online_orders") is True
    assert feature_is_allowed(entitlement, "ai_queries") is True
    assert feature_is_allowed(
        {"features": {"online_orders": False}, "daily_ai_query_limit": 0},
        "online_orders",
    ) is False
    assert feature_is_allowed(
        {"features": {"online_orders": True}, "daily_ai_query_limit": 0},
        "ai_queries",
    ) is False


def test_existing_single_feature_access_endpoint_remains_available():
    source = inspect.getsource(check_feature_access)
    assert "get_shop_entitlements(" in source
    assert "feature_is_allowed(entitlement, feature_code)" in source
