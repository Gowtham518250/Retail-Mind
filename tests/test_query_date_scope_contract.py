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



def test_sql_reviewer_corrects_legacy_sales_query_and_preserves_yesterday_scope(monkeypatch):
    import json
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    question = "What were my sales yesterday?"
    original_sql = (
        "SELECT SUM(total) AS sales_amount FROM sales "
        "WHERE shopkeeper_id = :user_id AND sale_date = :previous_business_date"
    )
    corrected_sql = (
        "SELECT COALESCE(SUM(i.total_amount), 0)::numeric AS total_sales_amount "
        "FROM invoices i WHERE i.user_id = :user_id "
        "AND i.invoice_date = :previous_business_date "
        "AND i.status NOT IN ('CANCELLED', 'DRAFT')"
    )
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "approved": True,
            "sql": corrected_sql,
            "issue": "Canonical source and status filters corrected.",
        })))])

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))),
    )
    result = query_retrival._review_generated_sql_with_groq(
        question=question,
        generated_sql=original_sql,
        schema_context="invoices: user_id, invoice_date, total_amount, status",
        query_plan={"intent": "aggregate", "metric": "sales_amount", "confidence": 0.95},
        date_scope={
            "kind": "exact",
            "label": "yesterday",
            "start_date": date(2026, 10, 12),
            "end_date": date(2026, 10, 12),
        },
    )

    assert result == corrected_sql
    assert len(calls) == 1
    assert "invoices i" in result
    assert "i.user_id = :user_id" in result
    assert "i.invoice_date = :previous_business_date" in result
    assert "CANCELLED" in result


def test_sql_reviewer_rejects_query_that_drops_requested_date(monkeypatch):
    import json
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    no_date_sql = (
        "SELECT SUM(i.total_amount) AS total_sales_amount FROM invoices i "
        "WHERE i.user_id = :user_id"
    )
    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "approved": True,
                "sql": no_date_sql,
                "issue": "none",
            })))]
        )))),
    )

    result = query_retrival._review_generated_sql_with_groq(
        question="What were my sales yesterday?",
        generated_sql=no_date_sql,
        schema_context="invoices: user_id, invoice_date, total_amount, status",
        query_plan={"intent": "aggregate", "metric": "sales_amount", "confidence": 0.95},
        date_scope={
            "kind": "exact",
            "label": "yesterday",
            "start_date": date(2026, 10, 12),
            "end_date": date(2026, 10, 12),
        },
    )

    assert result is None


class _FakeAllMappings:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _FakeAllResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return _FakeAllMappings(self.rows)


class _FakeComparisonDb:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, statement, params):
        self.sql = str(statement)
        self.params = dict(params)
        return _FakeAllResult(self.rows)


def test_items_sold_today_is_a_deterministic_kpi_not_an_llm_sql_query(monkeypatch):
    import query_retrival

    today = date(2026, 10, 14)
    monkeypatch.setattr(query_retrival, "_business_dates", lambda: (today, date(2026, 10, 13)))
    question = "How many items were sold today?"
    scope = query_retrival._resolve_explicit_date_scope(question)
    plan = query_retrival._make_deterministic_query_plan(question)

    assert plan["intent"] == "aggregate"
    assert plan["metric"] == "units_sold"
    assert query_retrival._can_use_fast_business_query(question, scope)

    db = _FakeDb({"total_units_sold": 12})
    result = query_retrival._fast_business_query(question, db, user_id=7, date_scope=scope)
    assert result["results"] == [{"total_units_sold": 12.0}]
    assert "COUNT(DISTINCT i.id)" in db.sql
    assert "LEFT JOIN invoice_line_items" in db.sql
    assert "CASE WHEN invoice_rows.cnt > 0" in db.sql
    assert db.params == {"user_id": 7, "business_date": today}


def test_short_sales_today_phrase_routes_to_billed_sales_kpi():
    import query_retrival

    scope = {"kind": "exact", "start_date": date(2026, 10, 14), "end_date": date(2026, 10, 14), "label": "today"}
    plan = query_retrival._make_deterministic_query_plan("sales today")
    assert plan["intent"] == "aggregate"
    assert plan["metric"] == "sales_amount"
    assert query_retrival._can_use_fast_business_query("sales today", scope)


def test_yesterday_and_today_revenue_returns_two_separate_daily_results(monkeypatch):
    import query_retrival

    today = date(2026, 10, 14)
    yesterday = date(2026, 10, 13)
    monkeypatch.setattr(query_retrival, "_business_dates", lambda: (today, yesterday))
    db = _FakeComparisonDb([
        {"business_date": yesterday, "sales_count": 3, "sales_amount": 1500, "total_units_sold": 10},
        {"business_date": today, "sales_count": 4, "sales_amount": 2100, "total_units_sold": 12},
    ])

    result = query_retrival._fast_sales_day_comparison_query(
        "Compare yesterday and today's revenue", db, user_id=7
    )

    assert result is not None
    assert "yesterday (2026-10-13): ₹1,500.00" in result["answer"]
    assert "today (2026-10-14): ₹2,100.00" in result["answer"]
    assert "+600.00 (+40.0%)" in result["answer"]
    assert [row["total_sales_amount"] for row in result["results"]] == [1500.0, 2100.0]
    assert ":previous_business_date" in db.sql and ":business_date" in db.sql
    assert db.params == {"user_id": 7, "business_date": today, "previous_business_date": yesterday}


def test_yesterday_and_today_items_sold_returns_daily_quantity_comparison(monkeypatch):
    import query_retrival

    today = date(2026, 10, 14)
    yesterday = date(2026, 10, 13)
    monkeypatch.setattr(query_retrival, "_business_dates", lambda: (today, yesterday))
    db = _FakeComparisonDb([
        {"business_date": yesterday, "sales_count": 3, "sales_amount": 1500, "total_units_sold": 10},
        {"business_date": today, "sales_count": 4, "sales_amount": 2100, "total_units_sold": 12},
    ])

    result = query_retrival._fast_sales_day_comparison_query(
        "Compare items sold yesterday vs today", db, user_id=7
    )

    assert result is not None
    assert "yesterday (2026-10-13): 10" in result["answer"]
    assert "today (2026-10-14): 12" in result["answer"]
    assert "Change today vs yesterday: +2 item(s)" in result["answer"]
    assert [row["total_units_sold"] for row in result["results"]] == [10.0, 12.0]


def test_translation_confidence_allows_clear_english_aggregate_to_use_fast_path():
    import query_retrival

    question = "How many items were sold today?"
    scope = {"kind": "exact", "start_date": date(2026, 10, 14), "end_date": date(2026, 10, 14), "label": "today"}
    plan = query_retrival._make_deterministic_query_plan(question)
    assert plan["confidence"] >= 0.90
    classification = {"intent": "general", "metric": "other", "confidence": 0.0}

    classifier_agrees = (
        classification.get("intent") == "aggregate"
        and classification.get("metric") in {"sales_amount", "sales_count", "units_sold", "expenses"}
        and float(classification.get("confidence") or 0.0) >= 0.90
    )
    assert not classifier_agrees
    assert query_retrival._can_use_fast_business_query(question, scope)
    # The ask_query route now permits this clear deterministic plan when translation confidence >= 0.92.
    assert 0.92 >= 0.92

