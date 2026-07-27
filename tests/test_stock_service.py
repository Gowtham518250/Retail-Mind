import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base
from models import Notification, Product, StockMovement, User
from stock_service import StockService


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    user = User(
        user_name="tester",
        email="tester@example.com",
        password="hashed",
        user_type="OWNER",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    yield db

    db.close()


def test_stock_service_deducts_quantity_and_records_movement(session):
    product = Product(
        user_id=session.query(User).first().id,
        product_name="Widget",
        sku="W-1",
        current_stock=10,
        min_stock=5,
        unit_price=25,
    )
    session.add(product)
    session.commit()
    session.refresh(product)

    product, movement = StockService.apply_stock_change(
        session,
        product_id=product.id,
        user_id=product.user_id,
        quantity=3,
        movement_type="OUT",
        reason="sale",
        reference_id="order-1",
    )
    session.commit()

    assert product.current_stock == 7
    assert movement.quantity == 3
    assert session.query(StockMovement).count() == 1
    assert session.query(Notification).count() == 0


def test_stock_service_rejects_insufficient_stock(session):
    product = Product(
        user_id=session.query(User).first().id,
        product_name="Widget",
        sku="W-2",
        current_stock=2,
        min_stock=5,
        unit_price=25,
    )
    session.add(product)
    session.commit()
    session.refresh(product)

    with pytest.raises(Exception) as excinfo:
        StockService.apply_stock_change(
            session,
            product_id=product.id,
            user_id=product.user_id,
            quantity=3,
            movement_type="OUT",
        )

    assert "Insufficient stock" in str(excinfo.value)
    assert session.query(StockMovement).count() == 0
    assert product.current_stock == 2
