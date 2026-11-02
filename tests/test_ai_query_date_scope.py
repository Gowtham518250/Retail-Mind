"""Date-scope resolution regression: independent expectations, frozen clock, IST/UTC boundaries."""
import json
from datetime import datetime, date
from pathlib import Path

import pytest

import query_retrival as qr

DATA = Path(__file__).parent / "data"
CASES = []
for name in ("ai_query_date_cases.json", "ai_query_date_heldout_cases.json"):
    CASES += json.loads((DATA / name).read_text(encoding="utf-8"))["cases"]


class _Frozen(datetime):
    frozen = None

    @classmethod
    def now(cls, tz=None):
        return cls.frozen.astimezone(tz) if tz else cls.frozen


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_date_scope(monkeypatch, case):
    _Frozen.frozen = datetime.fromisoformat(case["now_utc"])
    monkeypatch.setattr(qr, "datetime", _Frozen)
    scope = qr._resolve_explicit_date_scope(case["query"])
    resolved = scope["kind"] in {"exact", "range"} and scope["start_date"] and scope["end_date"]
    clarify = (not resolved) and qr._has_unresolved_date_intent(case["query"], scope)
    if case["outcome"] == "resolved":
        assert resolved, f"{case['query']!r} should resolve"
        assert (scope["start_date"].isoformat(), scope["end_date"].isoformat()) == (case["start"], case["end"])
    elif case["outcome"] == "clarify":
        assert not resolved and clarify, f"{case['query']!r} must ask, never guess"
    else:
        assert not resolved and not clarify


def test_product_names_that_look_like_months_do_not_create_a_date_filter(monkeypatch):
    _Frozen.frozen = datetime.fromisoformat("2026-11-02T04:00:00+00:00")
    monkeypatch.setattr(qr, "datetime", _Frozen)
    for q in ("sales of march rice brand", "stock of may flower oil", "price of sept special pack"):
        assert qr._resolve_explicit_date_scope(q)["kind"] == "unspecified", q


def test_future_named_and_numeric_dates_require_clarification(monkeypatch):
    _Frozen.frozen = datetime.fromisoformat("2026-11-02T04:00:00+00:00")
    monkeypatch.setattr(qr, "datetime", _Frozen)
    for q in ("sales on 15 October 2027", "sales on 2027-10-15", "sales in 2028"):
        scope = qr._resolve_explicit_date_scope(q)
        assert scope["kind"] == "unsupported", q
        assert qr._has_unresolved_date_intent(q, scope), q


def test_invalid_named_date_range_requires_clarification(monkeypatch):
    _Frozen.frozen = datetime.fromisoformat("2026-11-02T04:00:00+00:00")
    monkeypatch.setattr(qr, "datetime", _Frozen)
    q = "sales from 29 February 2025 to 1 March 2025"
    scope = qr._resolve_explicit_date_scope(q)
    assert scope["kind"] == "unsupported"
    assert qr._has_unresolved_date_intent(q, scope)


def test_leap_day_without_year_resolves_to_the_most_recent_valid_occurrence(monkeypatch):
    _Frozen.frozen = datetime.fromisoformat("2026-11-02T04:00:00+00:00")
    monkeypatch.setattr(qr, "datetime", _Frozen)
    scope = qr._resolve_explicit_date_scope("sales on 29 February")
    assert scope["kind"] == "exact"
    assert scope["start_date"] == date(2024, 2, 29)
