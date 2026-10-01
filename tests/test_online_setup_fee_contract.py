def test_online_setup_fee_contract():
    from models import ShopProfile, OnlineOrder
    from online_store import PlaceOrder, GuestOrder

    assert hasattr(ShopProfile, "online_setup_fee")
    assert hasattr(OnlineOrder, "online_setup_fee")
    assert "online_setup_fee" not in PlaceOrder.model_fields
    assert "online_setup_fee" not in GuestOrder.model_fields


def test_marketplace_builder_exposes_fee_and_online_gate():
    from online_store import router

    paths = {getattr(route, "path", "") for route in router.routes}
    assert "/store/marketplace/search" in paths
    assert "/store/shops/{shop_id}/products" in paths
    assert "/store/order" in paths


def test_owner_online_settings_routes_exist():
    from shop_management import router

    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()))))
        for route in router.routes
    }
    assert any(path == "/online-settings" and "GET" in methods for path, methods in routes)
    assert any(path == "/online-settings" and "PUT" in methods for path, methods in routes)
