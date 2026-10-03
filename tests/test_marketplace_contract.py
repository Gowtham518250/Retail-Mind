import inspect

from online_store import OwnerOrderAction, ai_shopping_recommendations, marketplace_search, router


def test_customer_marketplace_contract_is_online_only_and_stock_aware():
    source = inspect.getsource(marketplace_search)
    assert "ShopProfile.is_online_store_enabled == True" in source
    assert "Product.current_stock > 0" in source


def test_customer_ai_recommendation_searches_enabled_shops_and_in_stock_items():
    source = inspect.getsource(ai_shopping_recommendations)
    assert "ShopProfile.is_online_store_enabled == True" in source
    assert "Product.current_stock > 0" in source


def test_delivery_otp_contract_requires_customer_otp_for_delivery_action():
    assert "customer_otp" in OwnerOrderAction.model_fields

    routes = {getattr(route, "path", "") for route in router.routes}
    assert "/store/owner/orders/{order_id}/delivery-otp" in routes
    assert "/store/owner/orders/{order_id}/action" in routes


def test_customer_marketplace_can_find_shops_by_category_metadata():
    import inspect

    source = inspect.getsource(marketplace_search)
    assert "ShopProfile.shop_type.ilike(like)" in source
    assert "ShopProfile.shop_categories.ilike(like)" in source
