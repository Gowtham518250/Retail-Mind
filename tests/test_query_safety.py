from query_safety import validate_read_only_tenant_sql


CATALOG = {
    "invoices": {"content": "TABLE: invoices\nCOLUMNS:\n- user_id (integer): tenant scope"},
    "customers": {"content": "TABLE: customers\nCOLUMNS:\n- user_id (integer): tenant scope"},
    "invoice_line_items": {"content": "TABLE: invoice_line_items\nRELATIONSHIPS:\n- invoice_id -> invoices.id"},
}


def test_accepts_simple_scoped_read_query():
    assert validate_read_only_tenant_sql(
        "SELECT i.id, i.total_amount FROM invoices i WHERE i.user_id = :user_id",
        CATALOG,
    ) == (True, "ok")


def test_rejects_join_where_one_tenant_table_is_not_scoped():
    valid, reason = validate_read_only_tenant_sql(
        "SELECT i.id, c.name FROM invoices i "
        "JOIN customers c ON c.id = i.customer_id "
        "WHERE i.user_id = :user_id",
        CATALOG,
    )
    assert not valid
    assert reason == "tenant_scope_missing_or_bypassable"


def test_accepts_join_only_when_each_tenant_relation_is_scoped():
    assert validate_read_only_tenant_sql(
        "SELECT i.id, c.name FROM invoices i "
        "JOIN customers c ON c.id = i.customer_id "
        "WHERE i.user_id = :user_id AND c.user_id = :user_id",
        CATALOG,
    ) == (True, "ok")


def test_rejects_or_branch_that_bypasses_tenant_filter():
    valid, reason = validate_read_only_tenant_sql(
        "SELECT i.id FROM invoices i "
        "WHERE i.user_id = :user_id OR i.status = 'PUBLIC'",
        CATALOG,
    )
    assert not valid
    assert reason == "tenant_scope_missing_or_bypassable"


def test_rejects_indirect_child_without_verified_parent_join():
    valid, reason = validate_read_only_tenant_sql(
        "SELECT ili.quantity FROM invoice_line_items ili "
        "WHERE ili.quantity > 0 AND :user_id = :user_id",
        CATALOG,
    )
    assert not valid
    assert reason == "indirect_relation_without_scoped_parent_join"


def test_accepts_invoice_lines_joined_to_a_scoped_invoice():
    assert validate_read_only_tenant_sql(
        "SELECT ili.quantity FROM invoices i "
        "JOIN invoice_line_items ili ON ili.invoice_id = i.id "
        "WHERE i.user_id = :user_id",
        CATALOG,
    ) == (True, "ok")


def test_rejects_unknown_tables_and_write_queries():
    assert not validate_read_only_tenant_sql(
        "SELECT email FROM user_details WHERE id = :user_id",
        CATALOG,
    )[0]
    assert not validate_read_only_tenant_sql(
        "DELETE FROM invoices WHERE user_id = :user_id",
        CATALOG,
    )[0]


def test_accepts_scoped_cte_and_ignores_its_name_as_a_physical_table():
    assert validate_read_only_tenant_sql(
        "WITH scoped_invoices AS ("
        "SELECT i.id FROM invoices i WHERE i.user_id = :user_id"
        ") SELECT * FROM scoped_invoices",
        CATALOG,
    ) == (True, "ok")
