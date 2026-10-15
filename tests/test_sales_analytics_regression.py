from datetime import datetime, timezone
from types import SimpleNamespace

from invoices_billing import _invoice_event_timestamp, _parse_client_timestamp
from growth_suite import growth_analytics


class FakeQuery:
    def __init__(self, *, first=None, scalar=None, rows=None):
        self.first_value = first
        self.scalar_value = scalar
        self.rows = rows or []
        self.outer_join_calls = 0

    def filter(self, *conditions):
        return self

    def join(self, *args, **kwargs):
        return self

    def outerjoin(self, *args, **kwargs):
        self.outer_join_calls += 1
        return self

    def group_by(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_value

    def scalar(self):
        return self.scalar_value

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, queries):
        self.queries = list(queries)
        self.query_calls = 0

    def query(self, *entities):
        query = self.queries[self.query_calls]
        self.query_calls += 1
        return query


def test_sale_event_timestamp_preserves_client_time_as_naive_utc():
    timestamp = _parse_client_timestamp("2026-10-15T17:45:32+05:30")

    assert timestamp == datetime(2026, 10, 15, 12, 15, 32)
    invoice = SimpleNamespace(created_at=timestamp)
    assert _invoice_event_timestamp(invoice) == datetime(2026, 10, 15, 12, 15, 32)


def test_sale_event_timestamp_normalizes_aware_datetime_to_utc():
    invoice = SimpleNamespace(
        created_at=datetime(2026, 10, 15, 17, 45, tzinfo=timezone.utc)
    )

    assert _invoice_event_timestamp(invoice) == datetime(2026, 10, 15, 17, 45)


def test_growth_analytics_keeps_unlinked_custom_items_in_top_revenue():
    line_without_product = SimpleNamespace(
        product_id=None,
        product_name="Custom Grocery Bundle",
        qty=2,
        revenue=240.0,
    )
    top_query = FakeQuery(rows=[line_without_product])
    db = FakeDB([
        FakeQuery(first=(400.0, 2)),  # invoice revenue and count
        FakeQuery(scalar=20.0),       # expense aggregate
        FakeQuery(first=(0.0, 0)),    # online aggregate
        top_query,                    # top product revenue
    ])

    result = growth_analytics(days=30, branch_id=None, user_id=7, db=db)

    assert result["top_products"] == [{
        "product_id": None,
        "product_name": "Custom Grocery Bundle",
        "quantity": 2.0,
        "revenue": 240.0,
    }]
    assert top_query.outer_join_calls == 1
