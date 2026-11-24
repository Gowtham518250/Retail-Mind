from datetime import date
import asyncio


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
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((str(sql), dict(params)))
        if self.responses:
            return _FakeResult(self.responses.pop(0))
        return _FakeResult([])


def _scope():
    return {
        "kind": "unspecified",
        "start_date": None,
        "end_date": None,
        "label": "not specified",
    }


def _ghee_history_row(**overrides):
    row = {
        "source_row_id": 81,
        "invoice_id": 17,
        "invoice_number": "INV-017",
        "customer_name": "Ganesh",
        "product_name": "Cow Ghee 1L",
        "sale_date": date(2026, 11, 20),
        "quantity_sold": 2,
        "unit_price": 540,
        "line_total": 1080,
        "current_selling_price": 560,
        "product_unit": "pcs",
        "sales_count": 8,
        "total_quantity_sold": 13,
        "total_sales_revenue": 7020,
        "total_history_rows": 8,
        "sale_source": "INVOICE",
    }
    row.update(overrides)
    return row


def test_screenshot_ghee_question_routes_to_product_sales_history_and_uses_invoice_lines():
    from query_retrival import _fast_product_sales_history_query

    query = (
        "Can you tell me all sales of my ghee product, selling price "
        "and sales history?"
    )
    db = _FakeDb([[_ghee_history_row()]])

    result = _fast_product_sales_history_query(
        query,
        db,
        user_id=7,
        date_scope=_scope(),
    )

    assert result is not None
    assert result["product_search_terms"] == ["ghee"]
    assert "Cow Ghee 1L: 8 sale line(s), 13 pcs sold, revenue ₹7,020.00." in result["answer"]
    assert "Current catalogue price: ₹560.00." in result["answer"]
    assert "actual price charged" in result["answer"]
    assert result["results"][0]["unit_price"] == 540.0
    assert result["results"][0]["current_selling_price"] == 560.0
    assert result["results"][0]["invoice_number"] == "INV-017"
    assert result["results"][0]["customer_name"] == "Ganesh"

    sql, params = db.calls[0]
    assert "FROM invoices i" in sql
    assert "JOIN invoice_line_items ili ON ili.invoice_id = i.id" in sql
    assert "LEFT JOIN products p ON p.id = ili.product_id AND p.user_id = i.user_id" in sql
    assert "i.status NOT IN ('CANCELLED', 'DRAFT')" in sql
    assert "i.user_id = :user_id" in sql
    assert "ili.unit_price::numeric AS unit_price" in sql
    assert "ili.line_total::numeric AS line_total" in sql
    assert "i.invoice_date AS sale_date" in sql
    assert "cp.is_active IS TRUE" in sql
    assert "cp.user_id = i.user_id" in sql
    assert "cp.branch_id = i.branch_id" in sql
    assert "active_product.unit_price::numeric AS current_selling_price" in sql
    assert "COALESCE(active_product.unit_price, p.unit_price)" not in sql
    assert "COALESCE(active_product.unit_price, s.price)" not in sql
    assert "s.shopkeeper_id = :user_id" in sql
    assert "NOT EXISTS (SELECT 1 FROM invoice_sales)" in sql
    assert "SELECT DISTINCT product_name, price" not in sql
    assert params["user_id"] == 7
    assert params["product_term_0"] == "%ghee%"


def test_product_sales_history_preserves_resolved_date_range():
    from query_retrival import _fast_product_sales_history_query

    start = date(2026, 11, 1)
    end = date(2026, 11, 24)
    db = _FakeDb([[_ghee_history_row()]])

    result = _fast_product_sales_history_query(
        "Show all ghee sales history",
        db,
        user_id=11,
        date_scope={
            "kind": "range",
            "start_date": start,
            "end_date": end,
            "label": "1 Nov 2026 to 24 Nov 2026",
        },
    )

    assert result is not None
    sql, params = db.calls[0]
    assert "i.invoice_date BETWEEN :start_date AND :end_date" in sql
    assert "s.sale_date BETWEEN :start_date AND :end_date" in sql
    assert params["start_date"] == start
    assert params["end_date"] == end


def test_legacy_sales_are_only_used_when_no_matching_invoice_line_exists():
    from query_retrival import _fast_product_sales_history_query

    db = _FakeDb([[
        _ghee_history_row(
            invoice_id=None,
            invoice_number=None,
            customer_name=None,
            sale_source="LEGACY_SALE",
        )
    ]])

    result = _fast_product_sales_history_query(
        "Show ghee sales history",
        db,
        user_id=5,
        date_scope=_scope(),
    )

    assert result is not None
    sql, _ = db.calls[0]
    assert "FROM sales s" in sql
    assert "AND NOT EXISTS (SELECT 1 FROM invoice_sales)" in sql
    assert result["results"][0]["sale_source"] == "LEGACY_SALE"


def test_catalog_price_is_reported_when_product_exists_without_sales():
    from query_retrival import _fast_product_sales_history_query

    db = _FakeDb([
        [],
        [{
            "product_id": 12,
            "product_name": "Pure Ghee 500g",
            "current_selling_price": 310,
            "product_unit": "pcs",
        }],
    ])

    result = _fast_product_sales_history_query(
        "Tell me all sales of ghee and its selling price",
        db,
        user_id=3,
        date_scope=_scope(),
    )

    assert result is not None
    assert "no completed sales records" in result["answer"]
    assert "Pure Ghee 500g" in result["answer"]
    assert result["results"][0]["current_selling_price"] == 310.0
    assert len(db.calls) == 2


def test_unknown_product_returns_clear_shop_scoped_empty_state():
    from query_retrival import _fast_product_sales_history_query

    db = _FakeDb([[], []])
    result = _fast_product_sales_history_query(
        "Show all sales of ghee",
        db,
        user_id=3,
        date_scope=_scope(),
    )

    assert result is not None
    assert "couldn't find an active catalogue product or sales history" in result["answer"]
    assert result["results"] == []
    assert db.calls[0][1]["user_id"] == 3
    assert db.calls[1][1]["user_id"] == 3


def test_product_sales_history_handler_does_not_capture_unsupported_intents():
    from query_retrival import _fast_product_sales_history_query

    for query in (
        "Which product generated the highest sales revenue?",
        "Show sales to customer Ravi for ghee",
        "Show ghee sales by worker Ramesh",
        "Show all sales history",
        "What is the current inventory of ghee?",
    ):
        assert _fast_product_sales_history_query(
            query,
            _FakeDb([[]]),
            user_id=7,
            date_scope=_scope(),
        ) is None


def test_translated_telugu_ghee_question_uses_history_path_before_schema_rag(monkeypatch):
    import query_retrival

    db = _FakeDb([[_ghee_history_row()]])
    monkeypatch.setattr(query_retrival, "_load_shop_vocabulary", lambda _db, _user: [])
    monkeypatch.setattr(
        query_retrival,
        "_translate_query_and_classify",
        lambda _query, _language: {
            "english_query": (
                "Can you tell me all sales of my ghee product, selling price "
                "and sales history?"
            ),
            "classification": {
                "intent": "records",
                "metric": "other",
                "confidence": 0.97,
                "translation_confidence": 0.98,
                "source": "test",
            },
        },
    )
    monkeypatch.setattr(query_retrival, "_resolve_explicit_date_scope", lambda _query: _scope())
    monkeypatch.setattr(query_retrival, "_persist_query_history", lambda **_kwargs: None)
    monkeypatch.setattr(query_retrival, "_fast_sales_day_comparison_query", lambda *_args: None)
    monkeypatch.setattr(
        query_retrival,
        "_cached_schema_search",
        lambda _query: (_ for _ in ()).throw(
            AssertionError("Product-specific sales history must be answered before schema RAG.")
        ),
    )

    response = asyncio.run(
        query_retrival.ask_query(
            query="నా నెయ్యి ఉత్పత్తి అమ్మకాల చరిత్ర మరియు అమ్మిన ధర చెప్పండి",
            language_code="te",
            db=db,
            user_id=7,
        )
    )

    assert response["generated_sql"].startswith("DIRECT_QUERY: product-specific invoice sales history")
    assert response["row_count"] == 1
    assert response["results"][0]["invoice_number"] == "INV-017"
    assert response["translated_query"].startswith("Can you tell me all sales of my ghee")


def test_product_search_terms_remove_question_words_and_keep_multiword_product():
    from query_retrival import _extract_product_sales_search_terms

    assert _extract_product_sales_search_terms(
        "Can you tell me all sales of my Amul Cow Ghee 1L product selling price and sales history?"
    ) == ["amul", "cow", "ghee", "1l"]
