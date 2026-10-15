import json
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base
from models import Product, PurchaseOrder, PurchaseOrderStatus, StockMovement, User
from purchase_orders import POReceiptItem, POReceiptRequest, _receive_po_items, create_purchase_order, PurchaseOrderCreate


@pytest.fixture()
def shop_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    user = User(user_name="PO Tester", email="po-tester@example.com", password="hashed", user_type="OWNER")
    db.add(user)
    db.commit()
    db.refresh(user)
    product = Product(
        user_id=user.id, product_name="Rice", sku="RICE-1",
        current_stock=Decimal("3"), min_stock=2, unit_price=50, purchase_price=40, is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    yield db, user, product
    db.close()
    engine.dispose()


def _order(db, user, product, *, ordered="10", received="0", status=PurchaseOrderStatus.ORDERED):
    db.add(PurchaseOrder(
        shop_id=user.id,
        supplier_name="Supplier A",
        status=status,
        total_cost=Decimal("400"),
        idempotency_key=None,
        items_json=json.dumps([{
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": float(Decimal(ordered)),
            "unit_cost": 40.0,
            "received_quantity": float(Decimal(received)),
        }]),
    ))
    db.commit()
    return db.query(PurchaseOrder).filter_by(shop_id=user.id).one()


def test_partial_purchase_receipt_adds_only_received_quantity(shop_db):
    db, user, product = shop_db
    po = _order(db, user, product)
    result = _receive_po_items(db, user.id, po.id, "receipt-key-0001", [{"item_index": 0, "quantity": Decimal("4")}])
    db.refresh(product)
    db.refresh(po)
    item = json.loads(po.items_json)[0]
    assert Decimal(str(product.current_stock)) == Decimal("7.000")
    assert Decimal(str(item["received_quantity"])) == Decimal("4.0")
    assert po.status == PurchaseOrderStatus.PARTIALLY_RECEIVED
    assert len(db.query(StockMovement).filter(StockMovement.reference_id.like(f"PO-{po.id}-R-%")).all()) == 1
    assert result["duplicate"] is False


def test_replaying_same_receipt_key_does_not_add_stock_twice(shop_db):
    db, user, product = shop_db
    po = _order(db, user, product)
    _receive_po_items(db, user.id, po.id, "receipt-key-0001", [{"item_index": 0, "quantity": Decimal("4")}])
    replay = _receive_po_items(db, user.id, po.id, "receipt-key-0001", [{"item_index": 0, "quantity": Decimal("4")}])
    db.refresh(product)
    assert Decimal(str(product.current_stock)) == Decimal("7.000")
    assert replay["duplicate"] is True
    assert db.query(StockMovement).count() == 1


def test_receipt_cannot_exceed_ordered_balance(shop_db):
    db, user, product = shop_db
    po = _order(db, user, product, ordered="5", received="4")
    with pytest.raises(HTTPException) as exc:
        _receive_po_items(db, user.id, po.id, "receipt-key-0002", [{"item_index": 0, "quantity": Decimal("2")}])
    assert exc.value.status_code == 422
    db.refresh(product)
    assert Decimal(str(product.current_stock)) == Decimal("3.000")


def test_purchase_order_creation_uses_idempotency_key_and_conflict_guard(shop_db):
    db, user, product = shop_db
    data = PurchaseOrderCreate(
        supplier_name="Supplier A",
        items=[{"product_id": product.id, "product_name": "Rice", "quantity": 10, "unit_cost": 40}],
        idempotency_key="create-po-idempotency-key",
    )
    first = create_purchase_order(data, db=db, current_user={"user_id": user.id})
    second = create_purchase_order(data, db=db, current_user={"user_id": user.id})
    assert first["id"] == second["id"]
    assert second["duplicate"] is True
    assert db.query(PurchaseOrder).count() == 1

    changed = PurchaseOrderCreate(
        supplier_name="Supplier A",
        items=[{"product_id": product.id, "product_name": "Rice", "quantity": 8, "unit_cost": 40}],
        idempotency_key="create-po-idempotency-key",
    )
    with pytest.raises(HTTPException) as exc:
        create_purchase_order(changed, db=db, current_user={"user_id": user.id})
    assert exc.value.status_code == 409
