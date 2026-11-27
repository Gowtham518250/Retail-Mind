from datetime import datetime, timedelta, timezone

from agentic.service import _iso_utc


def test_iso_utc_marks_naive_database_timestamp_as_utc():
    value = datetime(2026, 11, 27, 10, 30, 0)

    assert _iso_utc(value) == "2026-11-27T10:30:00Z"


def test_iso_utc_converts_aware_timestamp_to_utc():
    value = datetime(
        2026, 11, 27, 16, 0, 0,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    assert _iso_utc(value) == "2026-11-27T10:30:00Z"


def test_iso_utc_preserves_none():
    assert _iso_utc(None) is None
