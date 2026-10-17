import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

os.environ.setdefault("SECRET_KEY", "ci-owner-analytics-test-secret-key-1234567890")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models import OnlineOrder, OnlineOrderStatus
from online_store import get_owner_order_analytics


def _order(shop_id, status, payment_status, amount, created_at):
    return OnlineOrder(
        shop_id=shop_id,
        customer_id=100 + shop_id,
        order_status=status,
        payment_status=payment_status,
        payment_method="UPI" if payment_status == "PAID" else "COD",
        total_amount=Decimal(str(amount)),
        items_json="[]",
        created_at=created_at,
    )


def test_owner_order_analytics_uses_one_query_and_preserves_totals():
    engine = create_engine("sqlite:///:memory:")
    OnlineOrder.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    local_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    utc_start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    today = utc_start + timedelta(hours=1)
    yesterday = utc_start - timedelta(hours=2)

    try:
        db.add_all([
            _order(7, OnlineOrderStatus.PENDING, "UNPAID", "100.00", today),
            _order(7, OnlineOrderStatus.DELIVERED, "PAID", "200.00", today),
            _order(7, OnlineOrderStatus.REJECTED, "PAID", "50.00", today),
            _order(7, OnlineOrderStatus.CANCELLED, "UNPAID", "25.00", today),
            _order(7, OnlineOrderStatus.RETURNED, "UNPAID", "35.00", today),
            _order(7, OnlineOrderStatus.DELIVERED, "PAID", "300.00", yesterday),
            _order(8, OnlineOrderStatus.PENDING, "UNPAID", "50.00", today),
        ])
        db.commit()

        query_count = {"value": 0}

        def count_query(conn, cursor, statement, parameters, context, executemany):
            query_count["value"] += 1

        event.listen(engine, "before_cursor_execute", count_query)
        result = get_owner_order_analytics(
            db=db,
            current_user={"role": "OWNER", "user_id": 7},
        )

        assert query_count["value"] == 1
        assert result == {
            "pending": 1,
            "todayCount": 2,
            "todayRevenue": 300.0,
            "paidCount": 1,
            "todayPaidCount": 1,
            "totalCount": 6,
            "totalRevenue": 600.0,
            "totalPaidCount": 3,
            "rejectedCount": 1,
            "cancelledCount": 2,
            "available": True,
        }
    finally:
        db.close()
        engine.dispose()
