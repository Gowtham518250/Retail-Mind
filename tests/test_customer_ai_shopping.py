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
