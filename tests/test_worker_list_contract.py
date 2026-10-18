from datetime import date
from decimal import Decimal
from types import SimpleNamespace


class _WorkerQuery:
    def __init__(self, row):
        self.row = row
        self.filter_expression = None
        self.ordering = None

    def filter(self, expression):
        self.filter_expression = expression
        return self

    def order_by(self, expression):
        self.ordering = expression
        return self

    def all(self):
        return [self.row]


class _WorkerDb:
    def __init__(self, row):
        self.row = row
        self.selected_columns = None
        self.query_result = None
        self.rollbacks = 0

    def query(self, *columns):
        self.selected_columns = columns
        self.query_result = _WorkerQuery(self.row)
        return self.query_result

    def rollback(self):
        self.rollbacks += 1


def test_worker_list_returns_stable_json_fields_and_numeric_salary():
    from attendance import get_workers
    from models import Worker

    row = SimpleNamespace(
        id=8,
        shopkeeper_id=42,
        name="Ravi",
        phone="9876543210",
        address="Kadapa",
        salary=Decimal("23500.50"),
        assigned_work="Billing",
        position="Cashier",
        join_date=date(2026, 10, 1),
        status="active",
        pin="1234",
    )
    db = _WorkerDb(row)
    result = get_workers(user_id=42, db=db)

    assert result == [{
        "id": 8,
        "shopkeeper_id": 42,
        "name": "Ravi",
        "phone": "9876543210",
        "address": "Kadapa",
        "salary": 23500.5,
        "assigned_work": "Billing",
        "position": "Cashier",
        "join_date": "2026-10-01",
        "status": "active",
        "pin": "1234",
    }]
    assert Worker.shopkeeper_id in db.selected_columns
    assert Worker.pin in db.selected_columns
    assert db.query_result.filter_expression is not None
    assert db.query_result.ordering is not None
    assert db.rollbacks == 0


def test_worker_schema_boot_repair_creates_missing_table_and_columns(monkeypatch):
    import db
    import production_boot

    statements = []

    class _Connection:
        def execute(self, statement):
            statements.append(str(statement))

    class _Begin:
        def __enter__(self):
            return _Connection()

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Engine:
        def begin(self):
            return _Begin()

    monkeypatch.setattr(db, "engine", _Engine())
    production_boot._ensure_workers_table_schema()

    joined = "\n".join(statements)
    assert "CREATE TABLE IF NOT EXISTS workers" in joined
    assert "ADD COLUMN IF NOT EXISTS pin VARCHAR(10)" in joined
    assert "ADD COLUMN IF NOT EXISTS shopkeeper_id INTEGER" in joined
    assert "ix_workers_shopkeeper_id" in joined
    # Preserve data when both legacy ownership columns exist: rows missing
    # user_id must still get a chance to backfill from shop_id.
    assert "UPDATE workers SET shopkeeper_id = user_id WHERE shopkeeper_id IS NULL" in joined
    assert "UPDATE workers SET shopkeeper_id = shop_id WHERE shopkeeper_id IS NULL" in joined
    assert "ELSIF EXISTS" not in joined
