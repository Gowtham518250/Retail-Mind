from decimal import Decimal
from inspect import getsource
from types import SimpleNamespace

from inventory_sync_service import (
    StockDeductionRequest,
    _stock_movement_matches_request,
    _duplicate_stock_response,
    deduct_stock_with_idempotency,
)
from models import StockMovement


def _request(**overrides):
    values = {
        "product_id": 7,
        "quantity": Decimal("2.500"),
        "reason": "SALE",
        "reference_id": "invoice-42",
        "idempotency_key": "invoice-42-product-7-sale",
    }
    values.update(overrides)
    return StockDeductionRequest(**values)


def _movement(**overrides):
    values = {
        "product_id": 7,
        "movement_type": SimpleNamespace(value="OUT"),
        "quantity": Decimal("2.500"),
        "reason": "sale",
        "reference_id": "invoice-42",
        "idempotency_key": "invoice-42-product-7-sale",
        "created_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_stock_movement_persists_a_unique_non_null_idempotency_key():
    assert "idempotency_key" in StockMovement.__table__.columns
    index = next(
        index for index in StockMovement.__table__.indexes
        if index.name == "uq_stock_movement_idempotency_key"
    )
    assert index.unique is True


def test_exact_stock_retry_matches_existing_movement():
    assert _stock_movement_matches_request(_movement(), _request()) is True


def test_stock_retry_with_changed_quantity_is_not_a_duplicate_success():
    assert _stock_movement_matches_request(
        _movement(), _request(quantity=Decimal("3.000"))
    ) is False


def test_stock_retry_with_changed_reference_or_product_is_rejected():
    assert _stock_movement_matches_request(
        _movement(), _request(reference_id="invoice-43")
    ) is False
    assert _stock_movement_matches_request(
        _movement(), _request(product_id=8)
    ) is False


def test_duplicate_response_does_not_invent_historical_before_stock():
    product = SimpleNamespace(id=7, current_stock=Decimal("4.000"))
    response = _duplicate_stock_response(product, _movement())
    assert response.previous_stock == Decimal("4.000")
    assert response.new_stock == Decimal("4.000")


def test_stock_endpoint_checks_tenant_product_before_replay_and_saves_key():
    source = getsource(deduct_stock_with_idempotency)
    assert source.index("Product.id == request.product_id") < source.index(
        "StockMovement.idempotency_key == request.idempotency_key"
    )
    assert "idempotency_key=request.idempotency_key" in source
    assert "except IntegrityError:" in source
    assert "status_code=409" in source
    assert "background_tasks.add_task(" in source
