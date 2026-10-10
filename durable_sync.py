"""Durable, tenant-scoped change feed for recoverable live sync.

Every producer calls append_sync_event() before committing its business
transaction. The per-shop clock row serializes sequence allocation, so a
client can safely advance a cursor without skipping a concurrent commit.
Redis remains a best-effort low-latency signal; this table is the recovery log.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from db import get_db
from models import (
    CustomerSyncClock,
    CustomerSyncEvent,
    SyncClock,
    SyncEvent,
)
from security import ROLE_CUSTOMER, get_current_user_dict, owner_only

router = APIRouter(prefix="/api/sync", tags=["Durable Sync"])
logger = logging.getLogger(__name__)


def append_sync_event(db: Session, event: Dict[str, Any]) -> Dict[str, Any]:
    """Persist an event inside the caller's active transaction; never commits.

    The upsert on sync_clocks takes a row lock until the surrounding
    transaction commits. Concurrent events for a shop therefore receive
    commit-ordered, contiguous cursors. Supported production dialect: Postgres.
    SQLite is supported for isolated tests.
    """
    try:
        shop_id = int(event["shop_id"])
        event_type = str(event["type"]).strip()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("sync event requires integer shop_id and non-empty type") from exc
    if shop_id <= 0 or not event_type:
        raise ValueError("sync event requires integer shop_id and non-empty type")

    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert_clock = postgresql_insert(SyncClock)
    elif dialect == "sqlite":
        insert_clock = sqlite_insert(SyncClock)
    else:
        raise RuntimeError(f"Durable sync is not supported for database dialect: {dialect}")

    clock_upsert = (
        insert_clock.values(shop_id=shop_id, seq=1)
        .on_conflict_do_update(
            index_elements=[SyncClock.shop_id],
            set_={"seq": SyncClock.seq + 1},
        )
        .returning(SyncClock.seq)
    )
    seq = int(db.execute(clock_upsert).scalar_one())

    payload = dict(event)
    payload.setdefault("event_id", str(uuid.uuid4()))
    payload.setdefault("version", 1)
    payload.setdefault("occurred_at", datetime.now(timezone.utc).isoformat())
    payload["sync_seq"] = seq

    # Online-order events also receive a customer-specific sequence. The
    # customer clock is committed with the order transaction, so one customer
    # can recover events across multiple shops without mixing shop cursors.
    customer_id = 0
    # Only online-order lifecycle events use OnlineCustomerAuth IDs. Invoice
    # events may carry a different CRM Customer.id; forwarding those into this
    # feed could expose unrelated business/customer data across identity spaces.
    customer_visible_types = {"order.created", "order.status_changed"}
    try:
        if event_type in customer_visible_types:
            customer_id = int(payload.get("customer_id") or 0)
    except (TypeError, ValueError):
        customer_id = 0

    customer_seq = None
    if customer_id > 0:
        if dialect == "postgresql":
            insert_customer_clock = postgresql_insert(CustomerSyncClock)
        else:
            insert_customer_clock = sqlite_insert(CustomerSyncClock)
        customer_clock_upsert = (
            insert_customer_clock.values(customer_id=customer_id, seq=1)
            .on_conflict_do_update(
                index_elements=[CustomerSyncClock.customer_id],
                set_={"seq": CustomerSyncClock.seq + 1},
            )
            .returning(CustomerSyncClock.seq)
        )
        customer_seq = int(db.execute(customer_clock_upsert).scalar_one())
        payload["customer_seq"] = customer_seq

    db.add(
        SyncEvent(
            shop_id=shop_id,
            seq=seq,
            event_id=str(payload["event_id"]),
            event_type=event_type,
            payload=payload,
        )
    )
    if customer_seq is not None:
        db.add(
            CustomerSyncEvent(
                customer_id=customer_id,
                seq=customer_seq,
                event_id=str(payload["event_id"]),
                event_type=event_type,
                payload=payload,
            )
        )
    # Flush exposes constraint errors before the business transaction commits.
    db.flush()
    return payload


@router.get("/changes")
def get_sync_changes(
    after: int = Query(0, ge=0, description="Last successfully applied per-shop cursor"),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Read a bounded, durable page of changes for the authenticated owner's shop."""
    request_started = time.perf_counter()
    shop_id = int(current_user["user_id"])

    clock_started = time.perf_counter()
    clock = db.get(SyncClock, shop_id)
    high_watermark = int(clock.seq) if clock else 0
    clock_ms = (time.perf_counter() - clock_started) * 1000

    if after > high_watermark:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "sync_cursor_ahead",
                "message": "The saved sync cursor is ahead of this shop's change log; run a safe bootstrap.",
                "high_watermark": high_watermark,
            },
        )

    # Most real-time sync calls are polls with an already-current cursor. Avoid
    # querying sync_events when there is no newer event to deliver.
    if after == high_watermark:
        total_ms = (time.perf_counter() - request_started) * 1000
        if total_ms >= 250:
            logger.warning(
                "SLOW_SYNC_CHANGES shop_id=%s after=%s limit=%s rows=0 clock_ms=%.1f "
                "query_ms=0.0 assembly_ms=0.0 total_ms=%.1f cursor_current=true",
                shop_id, after, limit, clock_ms, total_ms,
            )
        return {
            "events": [],
            "next_cursor": high_watermark,
            "high_watermark": high_watermark,
            "has_more": False,
        }

    query_started = time.perf_counter()
    # Project only response columns rather than hydrating full ORM objects.
    # The primary key (shop_id, seq) already supports this tenant/cursor scan.
    rows = (
        db.query(
            SyncEvent.seq.label("seq"),
            SyncEvent.event_id.label("event_id"),
            SyncEvent.event_type.label("event_type"),
            SyncEvent.payload.label("payload"),
            SyncEvent.created_at.label("created_at"),
        )
        .filter(
            SyncEvent.shop_id == shop_id,
            SyncEvent.seq > after,
            SyncEvent.seq <= high_watermark,
        )
        .order_by(SyncEvent.seq.asc())
        .limit(limit + 1)
        .all()
    )
    query_ms = (time.perf_counter() - query_started) * 1000
    has_more = len(rows) > limit
    page = rows[:limit]
    # When there are more rows, return only the last row actually delivered.
    # Otherwise the cursor can skip the remainder of this bounded page.
    next_cursor = int(page[-1].seq) if has_more and page else high_watermark

    assembly_started = time.perf_counter()
    response = {
        "events": [
            {
                **(row.payload if isinstance(row.payload, dict) else {}),
                "event_id": row.event_id,
                "type": row.event_type,
                "shop_id": shop_id,
                "sync_seq": row.seq,
                "occurred_at": (
                    row.created_at.isoformat()
                    if row.created_at
                    else (row.payload or {}).get("occurred_at")
                ),
            }
            for row in page
        ],
        "next_cursor": next_cursor,
        "high_watermark": high_watermark,
        "has_more": has_more,
    }
    assembly_ms = (time.perf_counter() - assembly_started) * 1000
    total_ms = (time.perf_counter() - request_started) * 1000
    if total_ms >= 250:
        logger.warning(
            "SLOW_SYNC_CHANGES shop_id=%s after=%s limit=%s rows=%s has_more=%s "
            "clock_ms=%.1f query_ms=%.1f assembly_ms=%.1f total_ms=%.1f",
            shop_id, after, limit, len(page), has_more, clock_ms, query_ms, assembly_ms, total_ms,
        )
    return response


@router.get("/my-changes")
def get_my_sync_changes(
    after: int = Query(0, ge=0, description="Last successfully applied customer cursor"),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user_dict),
    db: Session = Depends(get_db),
):
    """Read customer-specific order changes across all shops the customer uses."""
    if str(current_user.get("role", "")).upper() != ROLE_CUSTOMER:
        raise HTTPException(status_code=403, detail="Customer account required")

    customer_id = int(current_user["user_id"])
    clock = db.get(CustomerSyncClock, customer_id)
    high_watermark = int(clock.seq) if clock else 0

    if after > high_watermark:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "customer_sync_cursor_ahead",
                "message": "The saved customer cursor is ahead of the server; refresh the current order snapshot.",
                "high_watermark": high_watermark,
            },
        )

    rows = (
        db.query(CustomerSyncEvent)
        .filter(
            CustomerSyncEvent.customer_id == customer_id,
            CustomerSyncEvent.seq > after,
            CustomerSyncEvent.seq <= high_watermark,
        )
        .order_by(CustomerSyncEvent.seq.asc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = int(page[-1].seq) if has_more and page else high_watermark

    return {
        "events": [
            {
                **(row.payload if isinstance(row.payload, dict) else {}),
                "event_id": row.event_id,
                "type": row.event_type,
                "customer_id": row.customer_id,
                "customer_seq": row.seq,
                "occurred_at": (
                    row.created_at.isoformat()
                    if row.created_at
                    else (row.payload or {}).get("occurred_at")
                ),
            }
            for row in page
        ],
        "next_cursor": next_cursor,
        "high_watermark": high_watermark,
        "has_more": has_more,
    }
