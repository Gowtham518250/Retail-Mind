from datetime import date


class _FakeMappings:
    def __init__(self, row):
        self.row = row

    def one(self):
        return self.row


class _FakeResult:
    def __init__(self, row):
        self.row = row

    def mappings(self):
        return _FakeMappings(self.row)


class _FakeDb:
    def __init__(self, row):
        self.row = row
        self.sql = None
        self.params = None

    def execute(self, statement, params):
        self.sql = str(statement)
        self.params = dict(params)
        return _FakeResult(self.row)


def test_last_one_month_including_today_is_a_rolling_calendar_month(monkeypatch):
    import query_retrival

    today = date(2026, 10, 12)
    monkeypatch.setattr(
        query_retrival,
        "_business_dates",
        lambda: (today, date(2026, 10, 11)),
    )

    question = "How much sales did my shop make in the last 1 month up to today?"
    scope = query_retrival._resolve_explicit_date_scope(question)

    assert scope == {
        "kind": "range",
        "start_date": date(2026, 9, 12),
        "end_date": date(2026, 10, 12),
        "label": "last 1 month",
    }
    assert query_retrival._can_use_fast_business_query(question, scope)


def test_last_30_days_includes_today_and_prior_29_dates(monkeypatch):
    import query_retrival

    today = date(2026, 10, 12)
    monkeypatch.setattr(
        query_retrival,
        "_business_dates",
        lambda: (today, date(2026, 10, 11)),
    )

    scope = query_retrival._resolve_explicit_date_scope(
        "What is my total sales over the last 30 days including today?"
    )

    assert scope["start_date"] == date(2026, 9, 13)
    assert scope["end_date"] == today
    assert scope["label"] == "last 30 days"


def test_last_month_without_a_number_remains_previous_calendar_month(monkeypatch):
    import query_retrival

    today = date(2026, 10, 12)
    monkeypatch.setattr(
        query_retrival,
        "_business_dates",
        lambda: (today, date(2026, 10, 11)),
    )

    scope = query_retrival._resolve_explicit_date_scope("What were my total sales last month?")

    assert scope["start_date"] == date(2026, 9, 1)
    assert scope["end_date"] == date(2026, 9, 30)
    assert scope["label"] == "last month"


def test_fast_sales_kpi_uses_the_resolved_rolling_range_for_both_sources(monkeypatch):
    import query_retrival

    today = date(2026, 10, 12)
    monkeypatch.setattr(
        query_retrival,
        "_business_dates",
        lambda: (today, date(2026, 10, 11)),
    )
    question = "How much sales did my shop make in the last 1 month up to today?"
    scope = query_retrival._resolve_explicit_date_scope(question)
    db = _FakeDb({"total_sales_amount": 42000})

    result = query_retrival._fast_business_query(
        question,
        db,
        user_id=7,
        date_scope=scope,
    )

    assert result["results"] == [{"total_sales_amount": 42000.0}]
    assert "i.invoice_date BETWEEN :start_date AND :end_date" in db.sql
    assert "s.sale_date BETWEEN :start_date AND :end_date" in db.sql
    assert db.params == {
        "user_id": 7,
        "start_date": date(2026, 9, 12),
        "end_date": date(2026, 10, 12),
    }
