from datetime import datetime, timedelta, timezone

from datetime_utils import as_utc_aware, is_after_utc, is_before_utc


def test_naive_legacy_timestamp_is_interpreted_as_utc():
    value = datetime(2026, 10, 14, 15, 0, 0)

    assert as_utc_aware(value) == datetime(2026, 10, 14, 15, 0, 0, tzinfo=timezone.utc)


def test_aware_timestamp_is_converted_to_utc():
    value = datetime(
        2026, 10, 14, 21, 0, 0,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    assert as_utc_aware(value) == datetime(2026, 10, 14, 15, 30, 0, tzinfo=timezone.utc)


def test_before_and_after_helpers_support_mixed_datetime_values():
    now = datetime(2026, 10, 14, 15, 0, 0, tzinfo=timezone.utc)
    naive_past = datetime(2026, 10, 14, 14, 0, 0)
    naive_future = datetime(2026, 10, 14, 16, 0, 0)

    assert is_before_utc(naive_past, now)
    assert is_after_utc(naive_future, now)
    assert not is_before_utc(naive_future, now)
    assert not is_after_utc(naive_past, now)


def test_none_datetime_is_neither_before_nor_after():
    now = datetime.now(timezone.utc)

    assert as_utc_aware(None) is None
    assert not is_before_utc(None, now)
    assert not is_after_utc(None, now)
