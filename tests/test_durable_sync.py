import os

os.environ.setdefault("SECRET_KEY", "ci-durable-sync-test-secret-key-1234567890")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from db import Base
from durable_sync import append_sync_event
from models import SyncClock, SyncEvent


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[SyncClock.__table__, SyncEvent.__table__])
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
