import inspect

from sales_restore_service import get_cancelled_order_identifiers, router


def test_cancelled_order_identifier_route_is_part_of_sales_restore_api():
    paths = {route.path for route in router.routes}
    assert "/api/sales-restore/cancelled-order-identifiers" in paths


def test_cancelled_order_lookup_is_scoped_and_does_not_require_online_orders_feature():
    source = inspect.getsource(get_cancelled_order_identifiers)
    assert "OnlineOrder.shop_id == user_id" in source
    assert "OnlineOrder.order_status.in_" in source
    assert "OnlineOrderStatus.CANCELLED" in source
    assert "OnlineOrderStatus.REJECTED" in source
    assert "require_shop_feature" not in source
    assert '"id": int(row.id)' in source
    assert '"order_id": int(row.id)' in source
