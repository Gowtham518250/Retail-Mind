from query_answering import format_query_answer


def test_single_invoice_total_amount_is_not_reported_as_shop_total():
    answer = format_query_answer(
        [{"id": 17, "total_amount": 300.0}],
        {"intent": "general", "metric": "other"},
        "SELECT i.id, i.total_amount FROM invoices i WHERE i.user_id = :user_id",
    )
    assert "one matching record" in answer.lower()
    assert "₹300.00" not in answer
    assert "no total has been inferred" in answer.lower().lower()


def test_scalar_sales_aggregate_is_summarized_from_the_actual_result():
    answer = format_query_answer(
        [{"total_sales_amount": 1250.5}],
        {"intent": "aggregate", "metric": "sales_amount"},
        "SELECT COALESCE(SUM(i.total_amount), 0) AS total_sales_amount "
        "FROM invoices i WHERE i.user_id = :user_id",
    )
    assert answer == "Total billed sales: ₹1,250.50."


def test_grouped_results_are_not_misrepresented_as_a_global_total():
    answer = format_query_answer(
        [
            {"product_name": "Rice", "total_sales_amount": 900.0},
            {"product_name": "Oil", "total_sales_amount": 500.0},
        ],
        {"intent": "aggregate", "metric": "sales_amount"},
        "SELECT p.product_name, SUM(ili.line_total) AS total_sales_amount "
        "FROM invoices i JOIN invoice_line_items ili ON ili.invoice_id = i.id "
        "JOIN products p ON p.id = ili.product_id "
        "WHERE i.user_id = :user_id AND p.user_id = :user_id "
        "GROUP BY p.product_name",
    )
    assert "2 matching records" in answer
    assert "overall total has been inferred" in answer
    assert "₹900.00" not in answer


def test_count_alias_is_summarized_as_a_count_only():
    answer = format_query_answer(
        [{"count": 3}],
        {"intent": "aggregate", "metric": "sales_count"},
        "SELECT COUNT(*) AS count FROM invoices WHERE user_id = :user_id",
    )
    assert answer == "Number of sales: 3."
