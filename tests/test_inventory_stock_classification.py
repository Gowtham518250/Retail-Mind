from decimal import Decimal
from types import SimpleNamespace

import inventory as inventory_module


def test_inventory_status_separates_fractional_low_stock_from_out_of_stock():
    products = [
        SimpleNamespace(
            is_active=True,
            current_stock=Decimal("0.500"),
            min_stock=Decimal("0.500"),
            max_stock=100,
            unit_price=Decimal("60.00"),
        ),
        SimpleNamespace(
            is_active=True,
            current_stock=Decimal("0"),
            min_stock=Decimal("2.500"),
            max_stock=100,
            unit_price=Decimal("10.00"),
        ),
        SimpleNamespace(
            is_active=True,
            current_stock=Decimal("2.750"),
            min_stock=Decimal("0.500"),
            max_stock=100,
            unit_price=Decimal("20.00"),
        ),
    ]

    summary = inventory_module._inventory_status_summary(products)

    assert summary["total_products"] == 3
    assert summary["low_stock"] == 1
    assert summary["critical_stock"] == 1
    assert summary["optimal_stock"] == 1
    assert summary["overstocked"] == 0
    assert summary["total_items_in_stock"] == 3.25
    assert summary["total_stock_value"] == 85.0


def test_inventory_status_ignores_archived_products_and_defaults_null_min_stock():
    products = [
        SimpleNamespace(
            is_active=True,
            current_stock=Decimal("9.500"),
            min_stock=None,
            max_stock=100,
            unit_price=Decimal("5.00"),
        ),
        SimpleNamespace(
            is_active=False,
            current_stock=Decimal("0"),
            min_stock=Decimal("10"),
            max_stock=100,
            unit_price=Decimal("5.00"),
        ),
    ]

    summary = inventory_module._inventory_status_summary(products)

    assert summary["total_products"] == 1
    assert summary["low_stock"] == 1
    assert summary["critical_stock"] == 0
    assert summary["total_items_in_stock"] == 9.5
    assert summary["total_stock_value"] == 47.5
