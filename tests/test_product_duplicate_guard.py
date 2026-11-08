from decimal import Decimal
from types import SimpleNamespace

import inventory as inventory_module
from models import Product, ProductCreateRequest


def test_product_min_stock_orm_uses_numeric_three_decimal_places():
    column = Product.__table__.c.min_stock
    assert column.type.precision == 12
    assert column.type.scale == 3


def test_create_request_idempotency_constraint_is_shop_scoped():
    constraints = {
        tuple(column.name for column in item.columns)
        for item in ProductCreateRequest.__table__.constraints
        if getattr(item, "name", None) == "uq_product_create_user_operation"
    }
    assert ("user_id", "operation_id") in constraints


def test_duplicate_detail_shows_existing_product_data():
    existing = SimpleNamespace(
        id=42,
        product_name="Classmate Notebook",
        sku="8901234567890",
        unit_price=45,
        purchase_price=30,
        current_stock=12,
        min_stock=Decimal("2.500"),
        unit="pcs",
        category="Stationery",
        is_active=True,
    )
    matches = inventory_module._product_identity_conflicts_from_rows(
        [existing],
        product_name="CLASSMATE NOTEBOOK",
        sku="0000000000000",
    )
    assert matches[0]["match_types"] == ["PRODUCT_NAME"]
    assert matches[0]["product"]["product_name"] == "Classmate Notebook"
    assert matches[0]["product"]["barcode"] == "8901234567890"
    assert matches[0]["product"]["current_stock"] == 12.0
    assert matches[0]["product"]["min_stock"] == 2.5


def test_duplicate_preflight_endpoint_is_shop_scoped_and_supports_edit_exclusion():
    source = open("inventory.py", encoding="utf-8").read()
    assert '@router.get("/products/duplicate-check")' in source
    assert "exclude_product_id: Optional[int]" in source
    assert "Product.user_id == user_id" in source


def test_update_schema_accepts_barcode_sku_edits():
    update = inventory_module.ProductUpdate(sku="8901234567890")
    assert update.sku == "8901234567890"



def test_archived_product_name_and_barcode_can_be_reused():
    archived = SimpleNamespace(
        id=41,
        product_name="Biscuit",
        sku="biscuit",
        unit_price=30,
        purchase_price=20,
        current_stock=10,
        min_stock=10,
        unit="pcs",
        category="General",
        is_active=False,
    )
    matches = inventory_module._product_identity_conflicts_from_rows(
        [archived],
        product_name="Biscuit",
        sku="biscuit",
    )
    assert matches == []


def test_active_product_still_blocks_duplicate_name_and_barcode():
    active = SimpleNamespace(
        id=42,
        product_name="Biscuit",
        sku="biscuit",
        unit_price=30,
        purchase_price=20,
        current_stock=10,
        min_stock=10,
        unit="pcs",
        category="General",
        is_active=True,
    )
    matches = inventory_module._product_identity_conflicts_from_rows(
        [active],
        product_name="Biscuit",
        sku="biscuit",
    )
    assert matches[0]["match_types"] == ["PRODUCT_NAME", "BARCODE"]
