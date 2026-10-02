from growth_suite import _coupon_value, router, customer_router


def test_growth_routes_are_registered():
    routes = {route.path for route in router.routes}
    customer_routes = {route.path for route in customer_router.routes}
    assert "/growth/overview" in routes
    assert "/growth/analytics" in routes
    assert "/growth/reorder-suggestions" in routes
    assert "/growth/branches" in routes
    assert "/growth/coupons" in routes
    assert "/growth/returns" in routes
    assert "/growth/deliveries" in routes
    assert "/growth/security-center" in routes
    assert "/growth/copilot" in routes
    assert "/store/coupon/validate" in customer_routes
    assert "/store/returns" in customer_routes
    assert "/store/buy-again" in customer_routes
    assert "/store/recommendations" in customer_routes
    assert "/store/loyalty" in customer_routes


class Coupon:
    discount_type = "PERCENT"
    discount_value = 10
    minimum_order_amount = 100
    maximum_discount = 50


def test_coupon_value_is_bounded_and_respects_minimum():
    assert _coupon_value(Coupon(), 80) == 0.0
    assert _coupon_value(Coupon(), 400) == 40.0
    assert _coupon_value(Coupon(), 1000) == 50.0
