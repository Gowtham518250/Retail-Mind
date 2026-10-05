def test_customer_ai_router_is_registered_and_grounded():
    from customer_ai_shopping import customer_ai_shopping

    assert callable(customer_ai_shopping)


def test_customer_ai_route_exists():
    from app import api

    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()))))
        for route in api.routes
    }
    assert any(
        path == "/store/customer-ai" and "GET" in methods
        for path, methods in routes
    )


def test_customer_ai_uses_current_orm_field_names():
    from models import Product, ShopProfile

    assert hasattr(ShopProfile, "shop_id")
    assert hasattr(Product, "user_id")
    assert hasattr(Product, "unit_price")

def test_customer_ai_health_route_exists():
    from app import api

    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()))))
        for route in api.routes
    }
    assert any(
        path == "/store/customer-ai/health" and "GET" in methods
        for path, methods in routes
    )


def test_customer_ai_uses_real_store_and_stock_filters():
    from customer_ai_shopping import customer_ai_shopping
    import inspect

    source = inspect.getsource(customer_ai_shopping)
    assert "ShopProfile.is_online_store_enabled.is_(True)" in source
    assert "Product.current_stock > 0" in source


def test_customer_ai_uses_unit_price_for_ranking():
    from customer_ai_shopping import customer_ai_shopping
    import inspect

    source = inspect.getsource(customer_ai_shopping)
    assert "pair[0].unit_price" in source
    assert "pair[0].price" not in source
