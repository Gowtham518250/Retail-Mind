"""Shared expiry policy for owner-confirmed AI action previews.

Preview timestamps are stored as naive UTC for compatibility with the existing
AgentPendingAction schema. The API exposes the same TTL in seconds to clients.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone


DEFAULT_PREVIEW_TTL_MINUTES = 15
MIN_PREVIEW_TTL_MINUTES = 5
MAX_PREVIEW_TTL_MINUTES = 60


def preview_ttl_minutes() -> int:
    """Return a bounded preview TTL; default to 15 minutes."""
    raw = os.getenv("RETAIL_MIND_AGENT_PREVIEW_TTL_MINUTES", "")
    if not raw.strip():
        return DEFAULT_PREVIEW_TTL_MINUTES
    try:
        configured = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PREVIEW_TTL_MINUTES
    return min(MAX_PREVIEW_TTL_MINUTES, max(MIN_PREVIEW_TTL_MINUTES, configured))


def preview_ttl_seconds() -> int:
    return preview_ttl_minutes() * 60


def preview_expires_at(now: datetime | None = None) -> datetime:
    """Return a naive UTC expiry timestamp for the existing DB column."""
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    expiry = reference.astimezone(timezone.utc) + timedelta(minutes=preview_ttl_minutes())
    return expiry.replace(tzinfo=None)


def expired_preview_detail(action_id: str, subject: str) -> dict[str, str]:
    """Stable machine-readable response so clients can retire an expired card."""
    label = (subject or "Action").strip().capitalize()
    return {
        "code": "agent_preview_expired",
        "action_id": str(action_id),
        "message": (
            f"This {label.lower()} preview expired. Prepare a new preview before confirming."
        ),
    }
