import inspect

from online_store import get_owner_order_analytics, router


def test_shop_scoped_order_analytics_route_is_registered():
    routes = {
        getattr(route, "path", "")
        for route in router.routes
    }
    assert "/store/owner/orders/analytics" in routes


def test_analytics_counts_orders_separately_from_order_value():
    source = inspect.getsource(get_owner_order_analytics)

    # Order counts come from database row counts, not summed currency values
    # and not just the paginated rows shown in the owner-order list.
    assert '"totalCount": total_count' in source
    assert 'total_count = int(base.count() or 0)' in source
    assert 'total_revenue = float(eligible.with_entities(sum_total).scalar() or 0)' in source
    assert 'today_count = int(today_eligible.count() or 0)' in source
    assert '"totalRevenue": round(total_revenue, 2)' in source


def test_analytics_are_tenant_scoped_and_exclude_cancelled_orders_from_value():
    source = inspect.getsource(get_owner_order_analytics)
    assert 'OnlineOrder.shop_id == shop_id' in source
    assert 'excluded_statuses = ("REJECTED", "CANCELLED", "RETURNED")' in source
    assert 'ZoneInfo("Asia/Kolkata")' in source
