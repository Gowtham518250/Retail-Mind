from decimal import Decimal


def test_rejection_stock_restore_adds_numeric_quantities_safely():
    from online_store import _add_stock_quantity

    # SQLAlchemy Numeric columns are returned as Decimal by PostgreSQL.
    updated = _add_stock_quantity(Decimal("3.125"), 0.875)

    assert updated == Decimal("4.000")
    assert isinstance(updated, Decimal)


def test_rejection_stock_restore_handles_null_stock_and_quantity():
    from online_store import _add_stock_quantity

    assert _add_stock_quantity(None, Decimal("1.250")) == Decimal("1.250")
    assert _add_stock_quantity(Decimal("2.000"), None) == Decimal("2.000")
