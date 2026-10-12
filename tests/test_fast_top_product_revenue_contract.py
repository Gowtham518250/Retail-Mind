from datetime import date


class _FakeMappings:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return _FakeMappings(self._row)


class _FakeDb:
    def __init__(self, row):
        self.row = row
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = str(sql)
        self.params = params
        return _FakeResult(self.row)


def _last_month_scope():
    return {
        "kind": "range",
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 30),
        "label": "last month",
    }


def test_highest_revenue_product_uses_invoice_line_revenue_and_date_range():
    from query_retrival import _fast_top_product_revenue_query

    db = _FakeDb({"product_name": "Premium Rice", "revenue": 1657})
    result = _fast_top_product_revenue_query(
        "Tell me the name of the product that brought the highest revenue in last month's sales.",
        db,
        user_id=7,
        date_scope=_last_month_scope(),
    )

    assert result is not None
    assert result["answer"] == (
        "The product with the highest recorded sales revenue last month "
        "was Premium Rice, with ₹1,657.00 in sales."
    )
    assert result["results"] == [{"product_name": "Premium Rice", "revenue": 1657.0}]
    assert "FROM invoices i" in db.sql
    assert "JOIN invoice_line_items ili ON ili.invoice_id = i.id" in db.sql
    assert "SUM(ili.line_total)::numeric AS revenue" in db.sql
    assert "i.user_id = :user_id" in db.sql
    assert "i.status NOT IN ('CANCELLED', 'DRAFT')" in db.sql
    assert "i.invoice_date BETWEEN :start_date AND :end_date" in db.sql
    assert "SUM(s.total)::numeric AS revenue" in db.sql
    assert "s.sale_date BETWEEN :start_date AND :end_date" in db.sql
    assert "NOT EXISTS (SELECT 1 FROM invoice_product_revenue)" in db.sql
    assert "ORDER BY revenue DESC NULLS LAST, product_name ASC" in db.sql
    assert "LIMIT 1" in db.sql
    assert db.params == {
        "user_id": 7,
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 30),
    }


def test_top_product_handler_returns_explicit_empty_state_when_no_sales_match():
    from query_retrival import _fast_top_product_revenue_query

    result = _fast_top_product_revenue_query(
        "Which product generated the most revenue last month?",
        _FakeDb(None),
        user_id=5,
        date_scope=_last_month_scope(),
    )

    assert result is not None
    assert "couldn't find a product with recorded sales revenue last month" in result["answer"].lower()
    assert result["results"] == []


def test_top_product_handler_ignores_regular_totals_and_non_revenue_questions():
    from query_retrival import _fast_top_product_revenue_query

    for query in (
        "How much revenue did my shop make last month?",
        "Which products were sold last month?",
        "Which product sold the most units last month?",
        "What is my current inventory?",
    ):
        assert _fast_top_product_revenue_query(
            query,
            _FakeDb(None),
            user_id=5,
            date_scope=_last_month_scope(),
        ) is None


def test_translated_top_revenue_question_returns_before_rag_and_generic_kpis(monkeypatch):
    import asyncio
    import query_retrival

    db = _FakeDb({"product_name": "Premium Rice", "revenue": 1657})
    scope = _last_month_scope()
    monkeypatch.setattr(
        query_retrival,
        "_translate_query_and_classify",
        lambda _query, _language: {
            "english_query": (
                "Tell me the name of the product that brought the highest revenue "
                "in last month's sales."
            ),
            "classification": {
                "intent": "general",
                "metric": "other",
                "confidence": 0.62,
                "translation_confidence": 0.98,
                "source": "test",
            },
        },
    )
    monkeypatch.setattr(query_retrival, "_resolve_explicit_date_scope", lambda _query: scope)
    monkeypatch.setattr(query_retrival, "_persist_query_history", lambda **_kwargs: None)
    monkeypatch.setattr(
        query_retrival,
        "_fast_sold_products_query",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("Top-product intent must run before generic product-list intent")
        ),
    )
    monkeypatch.setattr(
        query_retrival,
        "_fast_profit_query",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("Top-product intent must run before generic financial handlers")
        ),
    )
    monkeypatch.setattr(
        query_retrival,
        "_cached_schema_search",
        lambda _query: (_ for _ in ()).throw(
            AssertionError("Top-product questions must not invoke RAG/Text-to-SQL")
        ),
    )

    response = asyncio.run(
        query_retrival.ask_query(
            query="నాకు గత నెలలో అత్యధిక ఆదాయం తెచ్చిన ఉత్పత్తి పేరు చెప్పు",
            language_code="te",
            db=db,
            user_id=7,
        )
    )

    assert response["answer"] == (
        "The product with the highest recorded sales revenue last month "
        "was Premium Rice, with ₹1,657.00 in sales."
    )
    assert response["row_count"] == 1
    assert response["translated_query"].startswith("Tell me the name of the product")
    assert response["generated_sql"].startswith("DIRECT_QUERY: top product revenue")
