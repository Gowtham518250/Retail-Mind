from growth_suite import _coupon_value, router, customer_router


def test_growth_routes_are_registered():
    routes = {route.path for route in router.routes}
    customer_routes = {route.path for route in customer_router.routes}
    assert "/overview" in routes
    assert "/analytics" in routes
    assert "/reorder-suggestions" in routes
    assert "/branches" in routes
    assert "/coupons" in routes
    assert "/returns" in routes
    assert "/deliveries" in routes
    assert "/security-center" in routes
    assert "/copilot" in routes
    assert "/coupon/validate" in customer_routes
    assert "/returns" in customer_routes
    assert "/buy-again" in customer_routes
    assert "/recommendations" in customer_routes
    assert "/loyalty" in customer_routes


class Coupon:
    discount_type = "PERCENT"
    discount_value = 10
    minimum_order_amount = 100
    maximum_discount = 50


def test_coupon_value_is_bounded_and_respects_minimum():
    assert _coupon_value(Coupon(), 80) == 0.0
    assert _coupon_value(Coupon(), 400) == 40.0
    assert _coupon_value(Coupon(), 1000) == 50.0
