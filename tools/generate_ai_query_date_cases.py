"""Generate the AI-query date-scope eval set (expected values derived independently of the code under test).

Each case freezes "now" as a UTC instant (so IST/UTC day-boundary behaviour is exercised) and states
the expected outcome class:
  resolved -> kind exact/range with exact start/end dates
  clarify  -> NOT resolved, but a date was clearly requested (the app must ask, never guess)
  none     -> no date in the question (must stay 'unspecified' and not trigger a clarification)
Usage: python tools/generate_ai_query_date_cases.py
"""
from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
ANCHORS = {
    "mon-2026-11-02": datetime(2026, 11, 2, 4, 0, tzinfo=timezone.utc),
    "year-start-2027-01-01": datetime(2027, 1, 1, 10, 0, tzinfo=timezone.utc),
    "month-end-2026-03-31": datetime(2026, 3, 31, 6, 0, tzinfo=timezone.utc),
    "leap-2028-03-01": datetime(2028, 3, 1, 6, 0, tzinfo=timezone.utc),
    "ist-ahead-of-utc-2026-11-01": datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc),  # IST already Nov 1
    "ist-new-year-2027-01-01": datetime(2026, 12, 31, 19, 0, tzinfo=timezone.utc),      # IST already Jan 1
}


def shift_months(d: date, n: int) -> date:
    idx = d.year * 12 + (d.month - 1) + n
    y, m0 = divmod(idx, 12)
    return date(y, m0 + 1, min(d.day, calendar.monthrange(y, m0 + 1)[1]))


def month_range(y: int, m: int):
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def most_recent_year(today: date, month: int, day: int) -> int:
    return today.year if date(today.year, month, day) <= today else today.year - 1


cases: list[dict] = []


def add(anchor, q, outcome, start=None, end=None, group=""):
    cases.append({
        "id": f"date-{len(cases) + 1:03d}", "group": group, "anchor": anchor,
        "now_utc": ANCHORS[anchor].isoformat(), "query": q, "outcome": outcome,
        "start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
    })


for name, now in ANCHORS.items():
    t = now.astimezone(IST).date()
    mon = t - timedelta(days=t.weekday())
    lm_start, lm_end = month_range(*((t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)))
    add(name, "sales today", "resolved", t, t, "single_day")
    add(name, "what were my sales today?", "resolved", t, t, "single_day")
    add(name, "yesterday's sales", "resolved", t - timedelta(1), t - timedelta(1), "single_day")
    add(name, "revenue yesterday", "resolved", t - timedelta(1), t - timedelta(1), "single_day")
    add(name, "sales day before yesterday", "resolved", t - timedelta(2), t - timedelta(2), "single_day")
    add(name, "sales this week", "resolved", mon, t, "week")
    add(name, "sales last week", "resolved", mon - timedelta(7), mon - timedelta(1), "week")
    add(name, "sales in the past week", "resolved", t - timedelta(6), t, "week")
    add(name, "sales this month", "resolved", t.replace(day=1), t, "month")
    add(name, "sales last month", "resolved", lm_start, lm_end, "month")
    add(name, "total sales in the last 1 month", "resolved", shift_months(t, -1), t, "month")
    add(name, "sales for the last 3 months", "resolved", shift_months(t, -3), t, "month")
    add(name, "sales this year", "resolved", date(t.year, 1, 1), t, "year")
    add(name, "sales last year", "resolved", date(t.year - 1, 1, 1), date(t.year - 1, 12, 31), "year")
    add(name, "sales in the last 7 days", "resolved", t - timedelta(6), t, "rolling")
    add(name, "sales last 30 days", "resolved", t - timedelta(29), t, "rolling")
    add(name, "sales for last 10 days", "resolved", t - timedelta(9), t, "rolling")
    add(name, "expenses in the last 2 weeks", "resolved", t - timedelta(13), t, "rolling")
    y = most_recent_year(t, 10, 15)
    add(name, "sales on 15 October", "resolved", date(y, 10, 15), date(y, 10, 15), "named_date")
    add(name, "sales on october 15", "resolved", date(y, 10, 15), date(y, 10, 15), "named_date")
    add(name, "sales on 15th oct", "resolved", date(y, 10, 15), date(y, 10, 15), "named_date")
    my = t.year if 10 <= t.month else t.year - 1
    add(name, "expenses in October", "resolved", *month_range(my, 10), "named_month")
    ry = most_recent_year(t, 10, 1)
    add(name, "sales from 1 October to 15 October", "resolved", date(ry, 10, 1), date(ry, 10, 15), "named_range")
    add(name, "give me the sales between 1st oct and 15th oct", "resolved", date(ry, 10, 1), date(ry, 10, 15), "named_range")

A1 = "mon-2026-11-02"
for q, s, e, g in [
    ("sales on 2026-10-15", date(2026, 10, 15), date(2026, 10, 15), "absolute"),
    ("sales on 15/10/2026", date(2026, 10, 15), date(2026, 10, 15), "absolute"),
    ("sales on 15-10-2026", date(2026, 10, 15), date(2026, 10, 15), "absolute"),
    ("sales on october 15, 2025", date(2025, 10, 15), date(2025, 10, 15), "absolute"),
    ("sales on 15 october 2025", date(2025, 10, 15), date(2025, 10, 15), "absolute"),
    ("sales from 2026-10-01 to 2026-10-15", date(2026, 10, 1), date(2026, 10, 15), "absolute"),
    ("sales between 2026-10-15 and 2026-10-01", date(2026, 10, 1), date(2026, 10, 15), "absolute"),
    ("sales from 1 october 2026 to 15 october 2026", date(2026, 10, 1), date(2026, 10, 15), "absolute"),
    ("sales in October 2025", date(2025, 10, 1), date(2025, 10, 31), "absolute"),
    ("sales in february 2028", None, None, "future_date"),  # future month at this anchor: ask, never guess
    ("sales in November", date(2026, 11, 1), date(2026, 11, 2), "absolute"),
    ("sales in December", date(2025, 12, 1), date(2025, 12, 31), "absolute"),
    ("sales on 15 December", date(2025, 12, 15), date(2025, 12, 15), "absolute"),
    ("sales since 2026-10-01", date(2026, 10, 1), date(2026, 11, 2), "absolute"),
    ("sales from 2026-10-01 to today", date(2026, 10, 1), date(2026, 11, 2), "absolute"),
    ("sales since 1 october", date(2026, 10, 1), date(2026, 11, 2), "absolute"),
    ("last 45 days sales", date(2026, 9, 19), date(2026, 11, 2), "absolute"),
    ("sales for last 6 months", date(2026, 5, 2), date(2026, 11, 2), "absolute"),
    ("sales previous month", date(2026, 10, 1), date(2026, 10, 31), "absolute"),
    ("sales current week", date(2026, 11, 2), date(2026, 11, 2), "absolute"),
    ("sales year to date", date(2026, 1, 1), date(2026, 11, 2), "absolute"),
    ("sales on 31 february", None, None, "invalid_date"),
]:
    if s is None:
        add(A1, q, "clarify", group=g)
    else:
        add(A1, q, "resolved", s, e, g)

add("leap-2028-03-01", "sales in february 2028", "resolved", date(2028, 2, 1), date(2028, 2, 29), "absolute")

for q in ["sales last quarter", "sales this quarter", "sales in q2", "financial year sales",
          "sales tomorrow", "sales last night", "sales this morning", "sales before 2026-10-01",
          "sales after 2026-10-01", "sales until 2026-10-15", "sales before 15/10/2026"]:
    add(A1, q, "clarify", group="needs_clarification")

for q in ["show top selling products", "how many customers do I have", "stock of rice",
          "which product has lowest stock", "list all workers", "total udhar balance",
          "may i know my customers", "what is my profit margin", "all time sales", "sales of march rice brand"]:
    add(A1, q, "none", group="no_date")

out = Path(__file__).resolve().parent.parent / "tests" / "data" / "ai_query_date_cases.json"
out.write_text(json.dumps({"anchors": {k: v.isoformat() for k, v in ANCHORS.items()}, "cases": cases}, indent=1), encoding="utf-8")
print(f"wrote {len(cases)} cases -> {out}")
