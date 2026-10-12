from datetime import date

import pytest


class _FakeMappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappings(self._rows)


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = str(sql)
        self.params = params
        return _FakeResult(self.rows)


def test_sold_product_list_uses_invoice_lines_and_shop_business_date():
    from query_retrival import _fast_sold_products_query

    db = _FakeDb([
        {"product_name": "Rice", "quantity_sold": 2},
        {"product_name": "Sugar", "quantity_sold": 1.5},
    ])
    scope_date = date(2026, 10, 12)

    result = _fast_sold_products_query(
        "Tell me which products were sold today?",
        db,
        user_id=7,
        date_scope={
            "kind": "exact",
            "start_date": scope_date,
            "end_date": scope_date,
            "label": "today",
        },
    )

    assert result is not None
    assert "Products sold today: Rice (2 sold), Sugar (1.5 sold)." == result["answer"]
    assert result["results"] == [
        {"product_name": "Rice", "quantity_sold": 2.0},
        {"product_name": "Sugar", "quantity_sold": 1.5},
    ]
    assert "FROM invoices i" in db.sql
    assert "JOIN invoice_line_items ili" in db.sql
    assert "i.status NOT IN ('CANCELLED', 'DRAFT')" in db.sql
    assert "i.invoice_date BETWEEN :start_date AND :end_date" in db.sql
    assert "s.sale_date BETWEEN :start_date AND :end_date" in db.sql
    assert "NOT EXISTS (SELECT 1 FROM invoice_products)" in db.sql
    assert db.params == {
        "user_id": 7,
        "start_date": scope_date,
        "end_date": scope_date,
    }


def test_sold_product_list_without_date_searches_available_history():
    from query_retrival import _fast_sold_products_query

    db = _FakeDb([{"product_name": "Tea", "quantity_sold": 4}])
    result = _fast_sold_products_query(
        "Which products were sold?",
        db,
        user_id=22,
        date_scope={
            "kind": "unspecified",
            "start_date": None,
            "end_date": None,
            "label": "not specified",
        },
    )

    assert result is not None
    assert "in the available sales history" in result["answer"]
    assert "invoice_date BETWEEN" not in db.sql
    assert "sale_date BETWEEN" not in db.sql
    assert db.params == {"user_id": 22}


@pytest.mark.parametrize(
    "query",
    [
        "How many items were sold today?",
        "What was the total sales amount today?",
        "Show raw sales rows for today",
        "What is my inventory stock?",
    ],
)
def test_sold_product_list_fast_path_does_not_capture_other_intents(query):
    from query_retrival import _fast_sold_products_query

    assert _fast_sold_products_query(
        query,
        _FakeDb([]),
        user_id=7,
        date_scope={"kind": "unspecified", "start_date": None, "end_date": None, "label": "not specified"},
    ) is None


def test_empty_sold_product_list_returns_explicit_empty_state():
    from query_retrival import _fast_sold_products_query

    result = _fast_sold_products_query(
        "Which products were sold today?",
        _FakeDb([]),
        user_id=7,
        date_scope={
            "kind": "exact",
            "start_date": date(2026, 10, 12),
            "end_date": date(2026, 10, 12),
            "label": "today",
        },
    )

    assert result is not None
    assert "couldn't find any identifiable products sold today" in result["answer"].lower()
    assert result["results"] == []


def test_translated_product_question_returns_before_rag_sql_generation(monkeypatch):
    import asyncio
    import query_retrival

    db = _FakeDb([{"product_name": "Milk", "quantity_sold": 3}])
    monkeypatch.setattr(
        query_retrival,
        "_translate_query_and_classify",
        lambda _query, _language: {
            "english_query": "Tell me which products were sold today?",
            "classification": {
                "intent": "general",
                "confidence": 0.62,
                "translation_confidence": 0.98,
                "source": "test",
            },
        },
    )
    monkeypatch.setattr(query_retrival, "_persist_query_history", lambda **_kwargs: None)
    monkeypatch.setattr(
        query_retrival,
        "_cached_schema_search",
        lambda _query: (_ for _ in ()).throw(AssertionError("RAG must not run for deterministic product-list questions")),
    )

    response = asyncio.run(
        query_retrival.ask_query(
            query="ఈరోజు ఏ ఉత్పత్తులు అమ్ముడయ్యాయి?",
            language_code="te",
            db=db,
            user_id=7,
        )
    )

    assert response["answer"] == "Products sold today: Milk (3 sold)."
    assert response["row_count"] == 1
    assert response["translated_query"] == "Tell me which products were sold today?"
    assert response["generated_sql"].startswith("DIRECT_QUERY: invoice line products")
