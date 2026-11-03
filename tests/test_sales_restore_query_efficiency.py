import os

os.environ.setdefault("SECRET_KEY", "ci-sales-restore-test-secret-key-1234567890")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable

from models import OnlineOrder, OnlineOrderStatus
from sales_restore_service import get_cancelled_order_identifiers


def _session():
    engine = create_engine("sqlite:///:memory:")
    # This focused unit test creates only online_orders; omit foreign-key
    # DDL because its referenced production tables are intentionally absent.
    with engine.begin() as connection:
        connection.execute(
            CreateTable(
                OnlineOrder.__table__,
                include_foreign_key_constraints=[],
            )
        )
        for index in OnlineOrder.__table__.indexes:
            index.create(connection)
    return engine, sessionmaker(bind=engine)()


def test_cancelled_order_identifiers_use_one_select_and_preserve_counts():
    engine, db = _session()
    try:
        db.add_all([
            OnlineOrder(shop_id=7, customer_id=1, total_amount=10, items_json="[]", order_status=OnlineOrderStatus.PENDING),
            OnlineOrder(shop_id=7, customer_id=1, total_amount=20, items_json="[]", order_status=OnlineOrderStatus.CANCELLED),
            OnlineOrder(shop_id=7, customer_id=1, total_amount=30, items_json="[]", order_status=OnlineOrderStatus.REJECTED),
            OnlineOrder(shop_id=7, customer_id=1, total_amount=40, items_json="[]", order_status=OnlineOrderStatus.RETURNED),
            OnlineOrder(shop_id=8, customer_id=2, total_amount=50, items_json="[]", order_status=OnlineOrderStatus.CANCELLED),
        ])
        db.commit()

        statements = []

        @event.listens_for(engine, "before_cursor_execute")
        def capture_selects(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT") and "online_orders" in statement.lower():
                statements.append(statement)

        result = get_cancelled_order_identifiers(user_id=7, db=db)

        assert len(statements) == 1
        assert result["total"] == 4
        assert result["totalCount"] == 4
        assert {item["status"] for item in result["orders"]} == {
            OnlineOrderStatus.CANCELLED.value,
            OnlineOrderStatus.REJECTED.value,
            OnlineOrderStatus.RETURNED.value,
        }
        assert result["cancelledCount"] == 2
        assert result["rejectedCount"] == 1
        assert {item["id"] for item in result["orders"]} == {2, 3, 4}
    finally:
        db.close()
        engine.dispose()


def test_cancelled_order_identifiers_keep_total_when_no_orders_are_cancelled():
    engine, db = _session()
    try:
        db.add(
            OnlineOrder(
                shop_id=9,
                customer_id=3,
                total_amount=15,
                items_json="[]",
                order_status=OnlineOrderStatus.PENDING,
            )
        )
        db.commit()

        result = get_cancelled_order_identifiers(user_id=9, db=db)

        assert result["orders"] == []
        assert result["total"] == 1
        assert result["cancelledCount"] == 0
        assert result["rejectedCount"] == 0
    finally:
        db.close()
        engine.dispose()


def test_online_orders_has_shop_status_composite_index():
    assert any(
        index.name == "ix_online_orders_shop_status"
        for index in OnlineOrder.__table__.indexes
    )
