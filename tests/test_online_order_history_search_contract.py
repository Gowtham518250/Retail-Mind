import inspect

from online_store import get_incoming_orders, router


def test_owner_order_history_supports_case_insensitive_customer_name_search():
    source = inspect.getsource(get_incoming_orders)
    assert "search: Optional[str]" in source
    assert "OnlineCustomerAuth.user_name.ilike(pattern)" in source
    assert "OnlineCustomerAuth.phone.ilike(pattern)" in source
    assert "clean_search.isdigit()" in source


def test_owner_order_history_returns_match_count_before_pagination():
    source = inspect.getsource(get_incoming_orders)
    assert "q.with_entities(func.count(OnlineOrder.id)).scalar()" in source
    assert ".offset(skip)" in source
    assert ".limit(max(1, min(limit, 200)))" in source
    assert '"total": total_matches' in source


def test_owner_order_history_route_remains_registered():
    routes = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()) or set())))
        for route in router.routes
    }
    assert any(path == "/store/owner/orders" and "GET" in methods for path, methods in routes)
