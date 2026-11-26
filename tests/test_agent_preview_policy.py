"""Regression tests for owner-confirmed AI preview expiry."""
from datetime import datetime, timezone

from agentic.preview_policy import (
    DEFAULT_PREVIEW_TTL_MINUTES,
    expired_preview_detail,
    preview_expires_at,
    preview_ttl_minutes,
    preview_ttl_seconds,
)


def test_agent_preview_ttl_defaults_to_fifteen_minutes(monkeypatch):
    monkeypatch.delenv("RETAIL_MIND_AGENT_PREVIEW_TTL_MINUTES", raising=False)
    assert preview_ttl_minutes() == 15
    assert preview_ttl_seconds() == 900
    assert DEFAULT_PREVIEW_TTL_MINUTES == 15


def test_agent_preview_ttl_is_bounded(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_PREVIEW_TTL_MINUTES", "2")
    assert preview_ttl_minutes() == 5
    monkeypatch.setenv("RETAIL_MIND_AGENT_PREVIEW_TTL_MINUTES", "120")
    assert preview_ttl_minutes() == 60
    monkeypatch.setenv("RETAIL_MIND_AGENT_PREVIEW_TTL_MINUTES", "invalid")
    assert preview_ttl_minutes() == 15


def test_preview_expiry_uses_naive_utc_and_configured_ttl(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_PREVIEW_TTL_MINUTES", "15")
    now = datetime(2026, 11, 27, 10, 0, tzinfo=timezone.utc)
    expiry = preview_expires_at(now)
    assert expiry.tzinfo is None
    assert expiry == datetime(2026, 11, 27, 10, 15)


def test_expired_preview_error_has_stable_machine_readable_code():
    detail = expired_preview_detail("action-123", "bill")
    assert detail["code"] == "agent_preview_expired"
    assert detail["action_id"] == "action-123"
    assert "expired" in detail["message"].lower()
