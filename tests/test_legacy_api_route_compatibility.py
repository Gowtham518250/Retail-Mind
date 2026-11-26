"""Compatibility contract for mobile clients using legacy list endpoints."""
import os

os.environ.setdefault("SECRET_KEY", "retail-mind-route-ci-only-not-for-production")

from app import api


def test_legacy_product_and_customer_list_routes_are_mounted():
    route_methods = {
        (route.path, method)
        for route in api.routes
        for method in getattr(route, "methods", set())
    }

    assert ("/api/products", "GET") in route_methods
    assert ("/api/customers", "GET") in route_methods
    assert ("/api/customers/", "GET") in route_methods
