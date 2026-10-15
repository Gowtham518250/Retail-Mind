from decimal import Decimal


class _FakeMappings:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return _FakeMappings(self.rows)


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, statement, params):
        self.sql = str(statement)
        self.params = dict(params)
        return _FakeResult(self.rows)


def test_low_stock_question_uses_deterministic_tenant_scoped_query():
    import query_retrival

    db = _FakeDb([{
        "product_id": 8,
        "product_name": "Rice",
        "sku": "RICE-1",
        "current_stock": Decimal("3"),
        "min_stock": 5,
        "reorder_level": 20,
    }])

    result = query_retrival._fast_low_stock_query(
        "What products are low in stock?", db, user_id=42
    )

    assert result is not None
    assert result["results"] == [{
        "product_id": 8,
        "product_name": "Rice",
        "sku": "RICE-1",
        "current_stock": 3.0,
        "min_stock": 5.0,
        "reorder_level": 20.0,
    }]
    assert "FROM products p" in db.sql
    assert "p.user_id = :user_id" in db.sql
    assert "p.current_stock <= p.min_stock" in db.sql
    assert db.params == {"user_id": 42}
    assert "Rice" in result["answer"]
    assert "minimum 5" in result["answer"]


def test_low_stock_question_with_no_matches_returns_clear_answer():
    import query_retrival

    db = _FakeDb([])

    result = query_retrival._fast_low_stock_query(
        "Which products are below the minimum stock level?", db, user_id=5
    )

    assert result is not None
    assert result["results"] == []
    assert "no products" in result["answer"].lower()
    assert db.params == {"user_id": 5}


def test_normal_stock_lookup_does_not_trigger_low_stock_handler():
    import query_retrival

    class _NoQueryDb:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("An ordinary stock lookup must not hit the low-stock handler.")

    assert query_retrival._fast_low_stock_query(
        "What is the current stock of rice?", _NoQueryDb(), user_id=5
    ) is None
