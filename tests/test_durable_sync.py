import os

import pytest

os.environ.setdefault("SECRET_KEY", "ci-durable-sync-test-secret-key-1234567890")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db import Base
from durable_sync import append_sync_event, get_my_sync_changes, get_sync_changes
from models import CustomerSyncClock, CustomerSyncEvent, SyncClock, SyncEvent


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[SyncClock.__table__, SyncEvent.__table__, CustomerSyncClock.__table__, CustomerSyncEvent.__table__])
    return sessionmaker(bind=engine)()


def test_sync_events_use_contiguous_per_shop_sequences():
    db = _session()
    try:
        first = append_sync_event(db, {"type": "invoice.created", "shop_id": 7, "invoice_id": 12})
        second = append_sync_event(db, {"type": "attendance.changed", "shop_id": 7, "worker_id": 4})
        other_shop = append_sync_event(db, {"type": "invoice.created", "shop_id": 8, "invoice_id": 13})
        db.commit()

        assert first["sync_seq"] == 1
        assert second["sync_seq"] == 2
        assert other_shop["sync_seq"] == 1
        assert db.get(SyncClock, 7).seq == 2
        assert db.get(SyncClock, 8).seq == 1
        assert db.query(SyncEvent).filter(SyncEvent.shop_id == 7).count() == 2
    finally:
        db.close()


def test_sync_events_roll_back_with_business_transaction():
    db = _session()
    try:
        append_sync_event(db, {"type": "invoice.created", "shop_id": 7, "invoice_id": 12})
        db.rollback()

        assert db.get(SyncClock, 7) is None
        assert db.query(SyncEvent).count() == 0
    finally:
        db.close()



def test_customer_change_feed_has_independent_cursors_across_shops():
    db = _session()
    try:
        first = append_sync_event(db, {
            "type": "order.created",
            "shop_id": 7,
            "customer_id": 42,
            "order_id": 100,
        })
        second = append_sync_event(db, {
            "type": "order.status_changed",
            "shop_id": 8,
            "customer_id": 42,
            "order_id": 200,
        })
        other_customer = append_sync_event(db, {
            "type": "order.created",
            "shop_id": 8,
            "customer_id": 99,
            "order_id": 300,
        })
        # Invoice customer IDs belong to the CRM Customer table, not the
        # OnlineCustomerAuth identity namespace, and must not enter this feed.
        invoice_event = append_sync_event(db, {
            "type": "invoice.created",
            "shop_id": 8,
            "customer_id": 42,
            "invoice_id": 900,
        })
        db.commit()

        assert "customer_seq" not in invoice_event
        assert first["customer_seq"] == 1
        assert second["customer_seq"] == 2
        assert other_customer["customer_seq"] == 1
        assert db.get(CustomerSyncClock, 42).seq == 2
        assert db.get(CustomerSyncClock, 99).seq == 1
        assert db.query(CustomerSyncEvent).filter(
            CustomerSyncEvent.customer_id == 42
        ).count() == 2
    finally:
        db.close()


def test_customer_changes_are_scoped_to_authenticated_customer():
    db = _session()
    try:
        append_sync_event(db, {
            "type": "order.created",
            "shop_id": 7,
            "customer_id": 42,
            "order_id": 100,
        })
        append_sync_event(db, {
            "type": "order.created",
            "shop_id": 7,
            "customer_id": 99,
            "order_id": 200,
        })
        db.commit()

        response = get_my_sync_changes(
            after=0,
            limit=100,
            current_user={"role": "CUSTOMER", "user_id": 42},
            db=db,
        )
        assert response["high_watermark"] == 1
        assert len(response["events"]) == 1
        assert response["events"][0]["order_id"] == 100

        with pytest.raises(Exception) as error:
            get_my_sync_changes(
                after=0,
                limit=100,
                current_user={"role": "OWNER", "user_id": 7},
                db=db,
            )
        assert getattr(error.value, "status_code", None) == 403
    finally:
        db.close()


def test_owner_sync_changes_are_shop_scoped_and_cursor_paged():
    db = _session()
    try:
        for invoice_id in (101, 102, 103):
            append_sync_event(
                db,
                {"type": "invoice.created", "shop_id": 7, "invoice_id": invoice_id},
            )
        append_sync_event(
            db,
            {"type": "invoice.created", "shop_id": 8, "invoice_id": 801},
        )
        db.commit()

        first = get_sync_changes(
            after=0,
            limit=2,
            current_user={"role": "OWNER", "user_id": 7},
            db=db,
        )
        assert [event["sync_seq"] for event in first["events"]] == [1, 2]
        assert [event["invoice_id"] for event in first["events"]] == [101, 102]
        assert first["next_cursor"] == 2
        assert first["high_watermark"] == 3
        assert first["has_more"] is True

        second = get_sync_changes(
            after=first["next_cursor"],
            limit=2,
            current_user={"role": "OWNER", "user_id": 7},
            db=db,
        )
        assert [event["sync_seq"] for event in second["events"]] == [3]
        assert [event["invoice_id"] for event in second["events"]] == [103]
        assert second["next_cursor"] == 3
        assert second["has_more"] is False

        # A caught-up poll is empty and keeps the current cursor stable.
        caught_up = get_sync_changes(
            after=second["next_cursor"],
            limit=2,
            current_user={"role": "OWNER", "user_id": 7},
            db=db,
        )
        assert caught_up == {
            "events": [],
            "next_cursor": 3,
            "high_watermark": 3,
            "has_more": False,
        }
    finally:
        db.close()
