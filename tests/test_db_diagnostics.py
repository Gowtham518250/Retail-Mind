from db import _sql_statement_summary


def test_sql_summary_includes_table_but_not_bound_values():
    summary = _sql_statement_summary(
        "SELECT seq FROM sync_clocks WHERE shop_id = :shop_id"
    )
    assert summary == "SELECT tables=sync_clocks"
    assert "shop_id" not in summary
    assert ":shop_id" not in summary


def test_sql_summary_handles_updates_without_emitting_full_sql():
    summary = _sql_statement_summary(
        "UPDATE online_orders SET payment_status = :status WHERE id = :order_id"
    )
    assert summary == "UPDATE tables=online_orders"
    assert ":status" not in summary
    assert ":order_id" not in summary
