def test_ai_query_history_model_and_routes():
    from models import AIQueryHistory
    from query_retrival import app, _fast_business_query

    assert hasattr(AIQueryHistory, "question")
    assert hasattr(AIQueryHistory, "answer")
    assert hasattr(AIQueryHistory, "user_id")

    routes = {(getattr(route, "path", ""), getattr(route, "methods", set())) for route in app.routes}
    assert any(path == "/askquery/history" and "GET" in methods for path, methods in routes)
    assert any(path == "/askquery/history" and "DELETE" in methods for path, methods in routes)
    assert any(path == "/askquery/history/{history_id}" and "DELETE" in methods for path, methods in routes)

    assert callable(_fast_business_query)


def _receivables_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE khata_balances ("
            "id INTEGER PRIMARY KEY, shop_id INTEGER NOT NULL, customer_name TEXT, "
            "customer_phone TEXT, khata_balance NUMERIC, last_transaction TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE customers ("
            "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, customer_name TEXT, phone TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE invoices ("
            "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, customer_id INTEGER, "
            "customer_name TEXT, customer_phone TEXT, invoice_number TEXT, invoice_date TEXT, "
            "due_date TEXT, total_amount NUMERIC, paid_amount NUMERIC, payment_status TEXT, status TEXT)"
        )
    return Session(engine)


def test_fast_receivables_khata_details_are_shop_scoped():
    from query_retrival import _fast_receivables_query, _resolve_explicit_date_scope
    from sqlalchemy import text

    db = _receivables_db()
    try:
        db.execute(
            text(
                "INSERT INTO khata_balances "
                "(id, shop_id, customer_name, customer_phone, khata_balance, last_transaction) "
                "VALUES (:id, :shop_id, :name, :phone, :balance, :last)"
            ),
            [
                {"id": 1, "shop_id": 7, "name": "Alice", "phone": "9000000001", "balance": 120, "last": "2026-10-09"},
                {"id": 2, "shop_id": 7, "name": "Bob", "phone": "9000000002", "balance": 75, "last": "2026-10-08"},
                {"id": 3, "shop_id": 8, "name": "Other shop", "phone": "9000000003", "balance": 999, "last": "2026-10-09"},
                {"id": 4, "shop_id": 7, "name": "Settled", "phone": "9000000004", "balance": 0, "last": "2026-10-01"},
            ],
        )
        db.commit()

        question = "Show all customers with outstanding khata balance"
        result = _fast_receivables_query(
            question, db, user_id=7, date_scope=_resolve_explicit_date_scope(question)
        )

        assert result is not None
        assert [row["customer_name"] for row in result["results"]] == ["Alice", "Bob"]
        assert sum(float(row["outstanding_amount"]) for row in result["results"]) == 195
        assert "Other shop" not in str(result["results"])
    finally:
        db.close()


def test_fast_receivables_unpaid_customers_and_invoice_details():
    from query_retrival import _fast_receivables_query, _resolve_explicit_date_scope
    from sqlalchemy import text

    db = _receivables_db()
    try:
        db.execute(
            text("INSERT INTO customers (id, user_id, customer_name, phone) VALUES (:id, :user_id, :name, :phone)"),
            [
                {"id": 1, "user_id": 7, "name": "Alice", "phone": "9000000001"},
                {"id": 2, "user_id": 7, "name": "Bob", "phone": "9000000002"},
                {"id": 3, "user_id": 8, "name": "Other shop", "phone": "9000000003"},
            ],
        )
        db.execute(
            text(
                "INSERT INTO invoices "
                "(id, user_id, customer_id, customer_name, customer_phone, invoice_number, invoice_date, "
                "due_date, total_amount, paid_amount, payment_status, status) "
                "VALUES (:id, :user_id, :customer_id, :name, :phone, :number, :invoice_date, "
                ":due_date, :total, :paid, :payment_status, :status)"
            ),
            [
                {"id": 1, "user_id": 7, "customer_id": 1, "name": "Alice", "phone": "9000000001",
                 "number": "INV-001", "invoice_date": "2026-10-01", "due_date": "2026-10-15",
                 "total": 100, "paid": 0, "payment_status": "UNPAID", "status": "SENT"},
                {"id": 2, "user_id": 7, "customer_id": 1, "name": "Alice", "phone": "9000000001",
                 "number": "INV-002", "invoice_date": "2026-10-02", "due_date": "2026-10-16",
                 "total": 50, "paid": 0, "payment_status": "UNPAID", "status": "SENT"},
                {"id": 3, "user_id": 7, "customer_id": 2, "name": "Bob", "phone": "9000000002",
                 "number": "INV-003", "invoice_date": "2026-10-02", "due_date": "2026-10-16",
                 "total": 200, "paid": 200, "payment_status": "PAID", "status": "SENT"},
                {"id": 4, "user_id": 8, "customer_id": 3, "name": "Other shop", "phone": "9000000003",
                 "number": "INV-OTHER", "invoice_date": "2026-10-02", "due_date": "2026-10-16",
                 "total": 900, "paid": 0, "payment_status": "UNPAID", "status": "SENT"},
                {"id": 5, "user_id": 7, "customer_id": 2, "name": "Bob", "phone": "9000000002",
                 "number": "INV-PART", "invoice_date": "2026-10-02", "due_date": "2026-10-16",
                 "total": 200, "paid": 50, "payment_status": "PARTIAL", "status": "SENT"},
            ],
        )
        db.commit()

        customer_question = "Show all unpaid customer details"
        customers = _fast_receivables_query(
            customer_question, db, user_id=7,
            date_scope=_resolve_explicit_date_scope(customer_question),
        )
        assert customers is not None
        assert len(customers["results"]) == 1
        assert customers["results"][0]["customer_name"] == "Alice"
        assert customers["results"][0]["unpaid_invoice_count"] == 2
        assert float(customers["results"][0]["outstanding_amount"]) == 150
        assert "Other shop" not in str(customers["results"])

        invoice_question = "Show all unpaid invoice details"
        invoices = _fast_receivables_query(
            invoice_question, db, user_id=7,
            date_scope=_resolve_explicit_date_scope(invoice_question),
        )
        assert invoices is not None
        assert {row["invoice_number"] for row in invoices["results"]} == {"INV-001", "INV-002"}
        assert all("outstanding_amount" in row for row in invoices["results"])
    finally:
        db.close()
