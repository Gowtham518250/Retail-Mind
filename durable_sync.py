"""Durable, tenant-scoped change feed for recoverable live sync.

Every producer calls append_sync_event() before committing its business
transaction. The per-shop clock row serializes sequence allocation, so a
client can safely advance a cursor without skipping a concurrent commit.
Redis remains a best-effort low-latency signal; this table is the recovery log.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from db import get_db
from models import SyncClock, SyncEvent
from security import owner_only

router = APIRouter(prefix="/api/sync", tags=["Durable Sync"])


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

    db.add(
        SyncEvent(
            shop_id=shop_id,
            seq=seq,
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
    shop_id = int(current_user["user_id"])
    clock = db.get(SyncClock, shop_id)
    high_watermark = int(clock.seq) if clock else 0

    if after > high_watermark:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "sync_cursor_ahead",
                "message": "The saved sync cursor is ahead of this shop's change log; run a safe bootstrap.",
                "high_watermark": high_watermark,
            },
        )

    rows = (
        db.query(SyncEvent)
        .filter(
            SyncEvent.shop_id == shop_id,
            SyncEvent.seq > after,
            SyncEvent.seq <= high_watermark,
        )
        .order_by(SyncEvent.seq.asc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    # When there are more rows, return only the last row actually delivered.
    # Otherwise the cursor can skip the remainder of this bounded page.
    next_cursor = int(page[-1].seq) if has_more and page else high_watermark

    return {
        "events": [
            {
                **(row.payload if isinstance(row.payload, dict) else {}),
                "event_id": row.event_id,
                "type": row.event_type,
                "shop_id": row.shop_id,
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
