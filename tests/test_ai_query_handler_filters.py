"""Deterministic /ask handlers answer whole-shop questions only.

A qualifier (product, category, customer, branch, custom number) is a filter the fixed SQL
cannot apply; answering anyway returns a confident wrong number. Such questions must fall
through (handler returns None) to the schema-grounded SQL path.
"""
import pytest

import query_retrival as qr


class _Claimed(Exception):
    """Raised by the fake DB: the handler accepted the question and went to SQL."""


class _Db:
    def execute(self, *a, **k):
        raise _Claimed()

    def __getattr__(self, name):
        raise _Claimed()


def _run(handler: str, question: str):
    scope = qr._resolve_explicit_date_scope(question)
    db = _Db()
    call = {
        "profit": lambda: qr._fast_profit_query(question, db, 1, scope),
        "low_stock": lambda: qr._fast_low_stock_query(question, db, 1),
        "sold": lambda: qr._fast_sold_products_query(question, db, 1, scope),
        "receivables": lambda: qr._fast_receivables_query(question, db, 1, scope),
    }[handler]
    try:
        return call()
    except _Claimed:
        return "claimed"


PURE = [
    ("profit", "what is my profit today"),
    ("profit", "net profit this month"),
    ("profit", "show profit and loss last week"),
    ("profit", "how much profit did I make yesterday"),
    ("low_stock", "low stock items"),
    ("low_stock", "show me low stock products"),
    ("low_stock", "which items are running low"),
    ("low_stock", "what products are below minimum stock"),
    ("low_stock", "reorder list"),
    ("sold", "which products were sold today"),
    ("sold", "list products sold this week"),
    ("sold", "show items sold last month"),
    ("receivables", "who owes me money"),
    ("receivables", "list customers with unpaid invoices"),
    ("receivables", "show outstanding khata balances"),
    ("receivables", "how many customers have pending dues"),
    ("receivables", "which customers have overdue bills this week"),
    ("receivables", "top customers with highest udhar"),
]

FILTERED = [
    ("profit", "profit on rice today"),
    ("profit", "profit this month from soap"),
    ("low_stock", "low stock items in dairy category"),
    ("low_stock", "low stock rice"),
    ("low_stock", "low stock below 5"),
    ("sold", "products sold to ravi yesterday"),
    ("sold", "which products did ramesh buy today"),
    ("receivables", "who owes me money from ramesh"),
    ("receivables", "unpaid bills of ravi"),
    ("receivables", "customers with dues in guntur"),
]


@pytest.mark.parametrize("handler,question", PURE)
def test_pure_whole_shop_questions_still_use_the_deterministic_handler(handler, question):
    assert _run(handler, question) == "claimed"


@pytest.mark.parametrize("handler,question", FILTERED)
def test_filtered_questions_fall_through_instead_of_returning_a_shop_wide_answer(handler, question):
    assert _run(handler, question) is None