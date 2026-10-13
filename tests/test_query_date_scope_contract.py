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


def test_implicit_sales_question_uses_deterministic_kpi_and_clear_answer(monkeypatch):
    import query_retrival

    today = date(2026, 10, 13)
    yesterday = date(2026, 10, 12)
    monkeypatch.setattr(
        query_retrival,
        "_business_dates",
        lambda: (today, yesterday),
    )

    question = "What were my sales yesterday?"
    scope = query_retrival._resolve_explicit_date_scope(question)
    plan = query_retrival._make_deterministic_query_plan(question)

    assert plan["intent"] == "aggregate"
    assert plan["metric"] == "sales_amount"
    assert plan["confidence"] >= 0.90
    assert query_retrival._can_use_fast_business_query(question, scope)

    db = _FakeDb({"total_sales_amount": 12345.6})
    result = query_retrival._fast_business_query(
        question,
        db,
        user_id=7,
        date_scope=scope,
    )

    assert result["answer"] == "Your total sales amount yesterday is ₹12,345.60."
    assert result["results"] == [{"total_sales_amount": 12345.6}]
    assert "FROM invoices i" in db.sql
    assert "i.invoice_date = :previous_business_date" in db.sql
    assert "FROM sales s" in db.sql
    assert "s.sale_date = :previous_business_date" in db.sql
    assert db.params == {"user_id": 7, "previous_business_date": yesterday}
    assert result["generated_sql"].strip().upper().startswith("SELECT")
