from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from agentic.inventory_actions import prepare_inventory_stock_movement
from agentic.registry import list_capabilities
from agentic.tools import InventoryStockMovementArgs, TOOL_DEFINITIONS
from models import AgentPendingAction, Product


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.result


class _Db:
    def __init__(self, product=None):
        self.product = product
        self.added = []

    def query(self, model):
        if model is Product:
            return _Query(self.product)
        if model is AgentPendingAction:
            return _Query(None)
        raise AssertionError(f"Unexpected query model: {model}")

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None


def _product(stock="8"):
    return SimpleNamespace(
        id=7,
        user_id=42,
        is_active=True,
        product_name="Rice",
        sku="RICE-001",
        current_stock=Decimal(stock),
        unit="kg",
        min_stock=2,
    )


def test_inventory_tool_rejects_untrusted_tenant_fields():
    with pytest.raises(ValidationError):
        InventoryStockMovementArgs.model_validate({
            "product_id": 7,
            "movement_type": "IN",
            "quantity": 5,
            "shop_id": 999,
        })


def test_inventory_tool_accepts_only_known_movement_types():
    with pytest.raises(ValidationError):
        InventoryStockMovementArgs.model_validate({
            "product_id": 7,
            "movement_type": "REFUND",
            "quantity": 5,
        })


def test_inventory_tool_is_allowlisted():
    names = {
        item["function"]["name"]
        for item in TOOL_DEFINITIONS
        if item.get("type") == "function"
    }
    assert "prepare_inventory_stock_movement" in names


def test_inventory_restock_preview_does_not_mutate_stock():
    product = _product()
    db = _Db(product)
    result = prepare_inventory_stock_movement(
        db,
        shop_id=42,
        conversation_id="conversation-1",
        request_text="add 5 kg rice to stock",
        product_id=7,
        movement_type="IN",
        quantity=Decimal("5"),
    )
    assert result["success"] is True
    assert result["preview"]["stock_before"] == 8.0
    assert result["preview"]["stock_after"] == 13.0
    assert result["preview"]["requires_owner_confirmation"] is True
    assert product.current_stock == Decimal("8")
    assert len(db.added) == 1
    assert db.added[0].action_type == "INVENTORY_STOCK_MOVEMENT"


def test_inventory_stock_out_preview_rejects_insufficient_stock():
    with pytest.raises(ValueError, match="only 8 are available"):
        prepare_inventory_stock_movement(
            _Db(_product()),
            shop_id=42,
            conversation_id="conversation-2",
            request_text="remove 10 kg rice",
            product_id=7,
            movement_type="OUT",
            quantity=Decimal("10"),
        )


def test_inventory_adjustment_preview_sets_target_not_delta():
    result = prepare_inventory_stock_movement(
        _Db(_product()),
        shop_id=42,
        conversation_id="conversation-3",
        request_text="correct rice stock count to 3 kg",
        product_id=7,
        movement_type="ADJUSTMENT",
        quantity=Decimal("3"),
    )
    assert result["preview"]["stock_before"] == 8.0
    assert result["preview"]["stock_after"] == 3.0
    assert result["preview"]["movement_type"] == "ADJUSTMENT"


def test_inventory_adjustment_allows_zero_but_stock_in_does_not():
    product = _product()
    result = prepare_inventory_stock_movement(
        _Db(product),
        shop_id=42,
        conversation_id="conversation-4",
        request_text="correct stock to zero",
        product_id=7,
        movement_type="ADJUSTMENT",
        quantity=Decimal("0"),
    )
    assert result["preview"]["stock_after"] == 0.0

    with pytest.raises(ValueError, match="outside the supported range"):
        prepare_inventory_stock_movement(
            _Db(product),
            shop_id=42,
            conversation_id="conversation-5",
            request_text="add zero rice",
            product_id=7,
            movement_type="IN",
            quantity=Decimal("0"),
        )


def test_inventory_tool_rejects_product_not_owned_by_shop():
    with pytest.raises(ValueError, match="not found in this shop"):
        prepare_inventory_stock_movement(
            _Db(None),
            shop_id=42,
            conversation_id="conversation-6",
            request_text="restock product 7",
            product_id=7,
            movement_type="IN",
            quantity=Decimal("1"),
        )


def test_inventory_manage_capability_requires_confirmation(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "true")
    capabilities = {item["name"]: item for item in list_capabilities()}
    inventory = capabilities["inventory.manage"]
    assert inventory["implemented"] is True
    assert inventory["enabled"] is True
    assert inventory["requires_confirmation"] is True


def test_inventory_manage_stays_disabled_when_agent_flag_is_off(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "false")
    capabilities = {item["name"]: item for item in list_capabilities()}
    inventory = capabilities["inventory.manage"]
    assert inventory["implemented"] is True
    assert inventory["enabled"] is False
