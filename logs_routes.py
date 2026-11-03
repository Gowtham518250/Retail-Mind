"""
Log ingestion endpoint for the mobile client's ComprehensiveLogger.

Previously missing entirely, which is why production logs were full of:
    POST /api/logs/ingest -> 404 Not Found

The client batches local debug/telemetry logs and POSTs them here on an
interval. This is intentionally lightweight: accept whatever shape the
client sends, store it, and always return 200/201 so the client can clear
its local buffer. It does NOT require auth - the client may be mid-401 (an
expired/expiring session) when it flushes its buffer, and we still want to
capture that log batch rather than dropping it.
"""

from datetime import datetime, timezone
from typing import Any, Optional
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from db import get_db, Base
from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.orm import Session as OrmSession

router = APIRouter(prefix="/api/logs", tags=["Client Logging"])
logger = logging.getLogger(__name__)


class ClientLogBatch(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[Any] = None
    app_version: Optional[str] = None
    platform: Optional[str] = None
    logs: Optional[list] = None
    timestamp: Optional[str] = None


class ClientLogEntry(Base):
    """Stores raw client log batches for later inspection/debugging."""
    __tablename__ = "client_log_batches"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    app_version = Column(String, nullable=True)
    platform = Column(String, nullable=True)
    payload = Column(JSON, nullable=True)
    client_timestamp = Column(String, nullable=True)
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


@router.post("/ingest")
def ingest_logs(batch: ClientLogBatch, db: OrmSession = Depends(get_db)):
    """
    Accept a batch of client-side logs. Use the standard request-scoped DB
    dependency so session cleanup and rollback are handled consistently.
    """
    try:
        entry = ClientLogEntry(
            session_id=batch.session_id,
            user_id=str(batch.user_id) if batch.user_id is not None else None,
            app_version=batch.app_version,
            platform=batch.platform,
            payload=batch.logs,
            client_timestamp=batch.timestamp,
        )
        db.add(entry)
        db.commit()
        return {"success": True, "stored": len(batch.logs or [])}
    except Exception:
        db.rollback()
        # Avoid exposing database details in a public telemetry response.
        logger.exception("Client log batch could not be persisted")
        return {"success": False, "error": "storage_unavailable"}
