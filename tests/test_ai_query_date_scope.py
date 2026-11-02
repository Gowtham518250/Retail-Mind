"""Focused date-scope regression tests using a frozen IST business clock."""
from datetime import datetime, timezone, timedelta

import query_retrival as qr


class _Frozen(datetime):
    frozen = datetime(2026, 11, 2, 4, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.frozen.astimezone(tz) if tz else cls.frozen


def _freeze(monkeypatch, instant="2026-11-02T04:00:00+00:00"):
    _Frozen.frozen = datetime.fromisoformat(instant)
    monkeypatch.setattr(qr, "datetime", _Frozen)


def test_day_before_yesterday_is_two_days_back(monkeypatch):
    _freeze(monkeypatch)
    scope = qr._resolve_explicit_date_scope("sales day before yesterday")
    assert scope["start_date"].isoformat() == "2026-10-31"
    assert scope["end_date"].isoformat() == "2026-10-31"


def test_named_date_range_and_month_resolve(monkeypatch):
    _freeze(monkeypatch)
    scope = qr._resolve_explicit_date_scope("sales from 1 October to 15 October")
    assert (scope["start_date"].isoformat(), scope["end_date"].isoformat()) == ("2026-10-01", "2026-10-15")
    month = qr._resolve_explicit_date_scope("expenses in October")
    assert (month["start_date"].isoformat(), month["end_date"].isoformat()) == ("2026-10-01", "2026-10-31")


def test_future_month_requires_clarification(monkeypatch):
    _freeze(monkeypatch)
    scope = qr._resolve_explicit_date_scope("sales in February 2028")
    assert scope["kind"] == "unspecified"
    assert qr._has_unresolved_date_intent("sales in February 2028", scope)


def test_month_like_product_names_do_not_create_date_filter(monkeypatch):
    _freeze(monkeypatch)
    for query in ("sales of march rice brand", "stock of may flower oil", "price of sept special pack"):
        assert qr._resolve_explicit_date_scope(query)["kind"] == "unspecified"
