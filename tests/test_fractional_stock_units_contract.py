from decimal import Decimal

from sqlalchemy import Numeric
from pydantic import ValidationError

import inventory as inventory_module
from models import Product, ProductBatch, StockMovement


def test_product_create_preserves_fractional_stock_and_unit():
    product = inventory_module.ProductCreate(
        product_name="Loose Rice",
        sku="RICE-001",
        current_stock=Decimal("2.500"),
        unit=" kg ",
        unit_price=60,
        purchase_price=45,
    )

    assert product.current_stock == Decimal("2.500")
    assert product.unit == "kg"


def test_product_update_accepts_fractional_stock_and_unit_changes():
    update = inventory_module.ProductUpdate(
        current_stock=Decimal("0.375"),
        unit="g",
    )

    assert update.current_stock == Decimal("0.375")
    assert update.unit == "g"


def test_stock_movement_and_batch_schemas_accept_fractional_quantities():
    movement = inventory_module.StockMovementCreate(
        product_id=1,
        movement_type="OUT",
        quantity=Decimal("0.250"),
        reason="SALE",
    )
    batch = inventory_module.ProductBatchCreate(
        product_id=1,
        batch_number="BATCH-1",
        quantity=Decimal("1.750"),
    )

    assert movement.quantity == Decimal("0.250")
    assert batch.quantity == Decimal("1.750")


def test_orm_columns_support_three_decimal_places_and_product_unit():
    for column in (
        Product.__table__.c.current_stock,
        StockMovement.__table__.c.quantity,
        ProductBatch.__table__.c.quantity,
    ):
        assert isinstance(column.type, Numeric)
        assert column.type.precision == 12
        assert column.type.scale == 3

    assert Product.__table__.c.unit.default.arg == "pcs"


def test_product_response_includes_fractional_stock_and_unit():
    response = inventory_module.ProductResponse(
        id=1,
        product_name="Loose Rice",
        sku="RICE-001",
        current_stock=2.5,
        unit="kg",
        min_stock=2,
        max_stock=100,
        unit_price=60,
    )

    assert response.current_stock == 2.5
    assert response.unit == "kg"



def test_inventory_import_preview_preserves_decimal_stock_and_unit():
    columns = ["Product Name", "SKU", "Current Stock", "Unit", "Unit Price"]
    mapping = inventory_module._inventory_import_fallback_mapping(columns)
    rows = inventory_module._inventory_import_build_preview_rows(
        columns,
        [{
            "Product Name": "Loose Rice",
            "SKU": "RICE-001",
            "Current Stock": "2.500",
            "Unit": "kg",
            "Unit Price": "60",
        }],
        mapping,
    )

    assert rows[0]["current_stock"] == 2.5
    assert rows[0]["unit"] == "kg"
    assert rows[0]["issues"] == []


def test_stock_api_rejects_more_than_three_decimal_places():
    with __import__("pytest").raises(ValidationError):
        inventory_module.ProductCreate(
            product_name="Loose Rice",
            sku="RICE-002",
            current_stock=Decimal("1.2345"),
            unit="kg",
            unit_price=60,
        )

    with __import__("pytest").raises(ValidationError):
        inventory_module.StockMovementCreate(
            product_id=1,
            movement_type="OUT",
            quantity=Decimal("0.0001"),
        )
