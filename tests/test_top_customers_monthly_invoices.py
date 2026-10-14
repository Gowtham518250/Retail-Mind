import asyncio
from datetime import date

import pytest


class _FakeMappings:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def one(self):
        if not self.rows:
            raise AssertionError("Expected one aggregate row")
        return self.rows[0]


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return _FakeMappings(self.rows)


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = {}

    def execute(self, statement, params):
        self.sql = str(statement)
        self.params = dict(params)
        return _FakeResult(self.rows)


def test_top_customers_ranks_by_billed_value_and_scopes_shop_and_month():
    from query_retrival import _fast_top_customers_query

    db = _FakeDb([
        {
            "customer_name": "Asha",
            "invoice_count": 3,
            "total_billed": 1800,
            "total_paid": 1300,
        },
        {
            "customer_name": "Ravi",
            "invoice_count": 2,
            "total_billed": 1200,
            "total_paid": 1200,
        },
    ])
    start = date(2026, 10, 1)
    end = date(2026, 10, 14)

    result = _fast_top_customers_query(
        "Top customers by invoice value this month",
        db,
        user_id=17,
        date_scope={
            "kind": "range",
            "start_date": start,
            "end_date": end,
            "label": "this month",
        },
    )

    assert result is not None
    assert result["results"][0]["customer_name"] == "Asha"
    assert "Top customers by billed invoice value this month" in result["answer"]
    assert "i.user_id = :user_id" in db.sql
    assert "c.user_id = i.user_id" in db.sql
    assert "i.status NOT IN ('CANCELLED', 'DRAFT')" in db.sql
    assert "i.invoice_date >= :scope_start AND i.invoice_date <= :scope_end" in db.sql
    assert "ORDER BY total_billed DESC" in db.sql
    assert db.params == {
        "user_id": 17,
        "row_limit": 10,
        "scope_start": start,
        "scope_end": end,
    }


def test_top_customers_can_rank_by_invoice_count_and_parse_limit():
    from query_retrival import _fast_top_customers_query

    db = _FakeDb([
        {
            "customer_name": "Ravi",
            "invoice_count": 8,
            "total_billed": 2200,
            "total_paid": 2000,
        }
    ])

    result = _fast_top_customers_query(
        "Show top 5 customers by invoice count",
        db,
        user_id=4,
        date_scope={"kind": "unspecified", "start_date": None, "end_date": None, "label": "not specified"},
    )

    assert result is not None
    assert "ORDER BY invoice_count DESC" in db.sql
    assert db.params == {"user_id": 4, "row_limit": 5}
    assert "invoice count" in result["answer"]


def test_monthly_invoices_returns_month_by_month_summary_without_groq():
    from query_retrival import _fast_invoice_report_query

    db = _FakeDb([
        {
            "invoice_month": date(2026, 10, 1),
            "invoice_count": 12,
            "total_billed": 32000,
            "total_paid": 25000,
            "outstanding_amount": 7000,
        },
        {
            "invoice_month": date(2026, 9, 1),
            "invoice_count": 9,
            "total_billed": 21800,
            "total_paid": 20000,
            "outstanding_amount": 1800,
        },
    ])

    result = _fast_invoice_report_query(
        "monthly invoices",
        db,
        user_id=8,
        date_scope={"kind": "unspecified", "start_date": None, "end_date": None, "label": "not specified"},
    )

    assert result is not None
    assert "Monthly invoice summary (most recent 24 months)" in result["answer"]
    assert result["results"][0]["invoice_month"] == "2026-10-01"
    assert result["results"][0]["invoice_count"] == 12
    assert "DATE_TRUNC('month', i.invoice_date)" in db.sql
    assert "i.user_id = :user_id" in db.sql
    assert "i.status NOT IN ('CANCELLED', 'DRAFT')" in db.sql
    assert "GROUP BY DATE_TRUNC('month', i.invoice_date)::date" in db.sql
    assert db.params == {"user_id": 8, "row_limit": 24}


def test_invoice_count_this_month_uses_date_scope_and_excludes_drafts():
    from query_retrival import _fast_invoice_report_query

    db = _FakeDb([{
        "invoice_count": 4,
        "total_billed": 5600,
        "total_paid": 4200,
        "outstanding_amount": 1400,
    }])
    start = date(2026, 10, 1)
    end = date(2026, 10, 14)

    result = _fast_invoice_report_query(
        "How many invoices this month?",
        db,
        user_id=8,
        date_scope={
            "kind": "range",
            "start_date": start,
            "end_date": end,
            "label": "this month",
        },
    )

    assert result is not None
    assert "4 eligible invoice(s) this month" in result["answer"]
    assert "invoice_date >= :scope_start AND i.invoice_date <= :scope_end" in db.sql
    assert db.params == {"user_id": 8, "scope_start": start, "scope_end": end}


@pytest.mark.parametrize(
    "question",
    [
        "What is my inventory stock?",
        "What are the top products?",
        "Show overdue invoices",
        "What is the outstanding invoice balance?",
    ],
)
def test_handlers_do_not_capture_unrelated_or_receivables_queries(question):
    from query_retrival import _fast_invoice_report_query, _fast_top_customers_query

    db = _FakeDb([])
    scope = {"kind": "unspecified", "start_date": None, "end_date": None, "label": "not specified"}

    assert _fast_top_customers_query(question, db, user_id=5, date_scope=scope) is None
    assert _fast_invoice_report_query(question, db, user_id=5, date_scope=scope) is None


def test_top_customers_route_returns_before_rag(monkeypatch):
    import query_retrival

    db = _FakeDb([{
        "customer_name": "Asha",
        "invoice_count": 3,
        "total_billed": 1800,
        "total_paid": 1300,
    }])
    monkeypatch.setattr(query_retrival, "_persist_query_history", lambda **_kwargs: None)
    monkeypatch.setattr(
        query_retrival,
        "_cached_schema_search",
        lambda _query: (_ for _ in ()).throw(AssertionError("Top-customer query must not use RAG.")),
    )

    response = asyncio.run(query_retrival.ask_query(
        query="Top customers",
        language_code="en",
        db=db,
        user_id=17,
    ))

    assert response["query_engine_version"] == "2026-10-14-top-customers-monthly-invoices-v11"
    assert response["answer"].startswith("Top customers by billed invoice value")
    assert response["sql"].startswith("DIRECT_QUERY: top customers")


def test_monthly_invoice_route_returns_before_rag(monkeypatch):
    import query_retrival

    db = _FakeDb([{
        "invoice_month": date(2026, 10, 1),
        "invoice_count": 12,
        "total_billed": 32000,
        "total_paid": 25000,
        "outstanding_amount": 7000,
    }])
    monkeypatch.setattr(query_retrival, "_persist_query_history", lambda **_kwargs: None)
    monkeypatch.setattr(
        query_retrival,
        "_cached_schema_search",
        lambda _query: (_ for _ in ()).throw(AssertionError("Monthly invoice query must not use RAG.")),
    )

    response = asyncio.run(query_retrival.ask_query(
        query="monthly invoices",
        language_code="en",
        db=db,
        user_id=8,
    ))

    assert response["query_engine_version"] == "2026-10-14-top-customers-monthly-invoices-v11"
    assert response["answer"].startswith("Monthly invoice summary")
    assert response["sql"].startswith("DIRECT_QUERY: monthly invoice summary")
