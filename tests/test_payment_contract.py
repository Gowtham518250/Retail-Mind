def test_invoice_payment_write_routes_exist():
    from invoices_billing import router

    routes = {
        (route.path, method)
        for route in router.routes
        for method in (route.methods or set())
    }

    assert ("/api/invoices/payments", "POST") in routes
    assert ("/api/invoices/update_payment", "PUT") in routes


def test_payment_write_request_has_idempotency_and_invoice_binding_fields():
    from invoices_billing import PaymentWriteRequest

    fields = getattr(
        PaymentWriteRequest,
        "model_fields",
        getattr(PaymentWriteRequest, "__fields__", {}),
    )
    assert "invoice_id" in fields
    assert "invoice_number" in fields
    assert "idempotency_key" in fields
    assert "reference_id" in fields



def test_payment_writer_supports_joining_an_outer_transaction():
    import inspect
    from invoices_billing import _apply_payment_write

    signature = inspect.signature(_apply_payment_write)
    assert "commit_transaction" in signature.parameters
    assert signature.parameters["commit_transaction"].default is True

    # Transaction-owning callers must defer commit, audit logging, and realtime
    # publishing until their surrounding business operation commits.
    source = inspect.getsource(_apply_payment_write)
    assert "if commit_transaction:" in source
    assert '"events": [] if commit_transaction else payment_events' in source



def test_manual_bill_payment_state_comes_from_recorded_paid_amount():
    from types import SimpleNamespace
    from models import InvoiceStatus, PaymentStatus
    from invoices_billing import _normalize_new_invoice_payment_state

    # Simulate the old request-schema default: status says PAID, amount says none received.
    invoice = SimpleNamespace(
        total_amount=50.0,
        paid_amount=0.0,
        payment_status=PaymentStatus.PAID,
        status=InvoiceStatus.PAID,
    )

    result = _normalize_new_invoice_payment_state(invoice)

    assert result == PaymentStatus.UNPAID
    assert invoice.payment_status == PaymentStatus.UNPAID
    assert invoice.status == InvoiceStatus.SENT


def test_manual_bill_payment_state_supports_partial_and_full_payment():
    from types import SimpleNamespace
    from models import InvoiceStatus, PaymentStatus
    from invoices_billing import _normalize_new_invoice_payment_state

    partial = SimpleNamespace(total_amount=50.0, paid_amount=20.0, payment_status=None, status=None)
    assert _normalize_new_invoice_payment_state(partial) == PaymentStatus.PARTIAL
    assert partial.payment_status == PaymentStatus.PARTIAL
    assert partial.status == InvoiceStatus.PARTIAL

    paid = SimpleNamespace(total_amount=50.0, paid_amount=50.0, payment_status=None, status=None)
    assert _normalize_new_invoice_payment_state(paid) == PaymentStatus.PAID
    assert paid.payment_status == PaymentStatus.PAID
    assert paid.status == InvoiceStatus.PAID


def test_invoice_api_exposes_payment_method_and_source_for_transaction_tabs():
    from invoices_billing import InvoiceResponse, InvoiceSyncCreate

    response_fields = getattr(
        InvoiceResponse,
        "model_fields",
        getattr(InvoiceResponse, "__fields__", {}),
    )
    request_fields = getattr(
        InvoiceSyncCreate,
        "model_fields",
        getattr(InvoiceSyncCreate, "__fields__", {}),
    )
    assert "payment_method" in response_fields
    assert "source" in response_fields
    assert "payment_method" in request_fields


def test_payment_methods_normalize_cash_delivery_and_upi_for_invoice_display():
    from invoices_billing import _normalize_invoice_payment_method

    assert _normalize_invoice_payment_method("COD") == "CASH"
    assert _normalize_invoice_payment_method("Cash on delivery") == "CASH"
    assert _normalize_invoice_payment_method("UPI") == "ONLINE"
    assert _normalize_invoice_payment_method("Online") == "ONLINE"


def test_canonical_payment_writer_suppresses_duplicate_delivery_trigger_record():
    import inspect
    from invoices_billing import _apply_payment_write

    source = inspect.getsource(_apply_payment_write)
    assert "retail_mind.payment_write_invoice_id" in source
    assert "set_config" in source
    # Use a raw connection for the transaction-local flag so the guard is set
    # before the ORM flush can fire the PostgreSQL trigger.
    assert "db.connection().execute" in source


def test_manual_create_route_normalizes_payment_from_amount_instead_of_schema_default():
    import inspect
    from invoices_billing import create_invoice

    source = inspect.getsource(create_invoice)
    assert "_normalize_new_invoice_payment_state(invoice)" in source
    assert "paid_amount cannot exceed total_amount" in source


def test_sqlalchemy_text_is_available_for_payment_transaction_guard():
    import invoices_billing
    from sqlalchemy.sql.elements import TextClause

    statement = invoices_billing.text(
        "SELECT set_config('retail_mind.payment_write_invoice_id', :invoice_id, true)"
    )

    assert isinstance(statement, TextClause)



def test_upi_ledger_reports_only_confirmed_collections():
    from datetime import date, datetime
    from decimal import Decimal

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from models import UpiLedger, UpiStatus
    from upi_ledger_service import UpiLedgerService

    # Isolated SQLite table keeps this regression test independent of production data.
    engine = create_engine("sqlite:///:memory:")
    UpiLedger.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    today = date.today()
    with Session() as db:
        records = [
            ("confirmed", Decimal("100.00"), UpiStatus.CONFIRM),
            ("pending", Decimal("200.00"), UpiStatus.PENDING),
            ("failed", Decimal("300.00"), UpiStatus.FAILED),
            ("refunded", Decimal("400.00"), UpiStatus.REFUND),
        ]
        for name, amount, status in records:
            db.add(UpiLedger(
                shop_id=42,
                invoice_id=None,
                upi_id=f"merchant-{name}",
                amount=amount,
                upi_reference=f"{today.isoformat()}-{name}",
                status=status,
                payment_date=datetime(today.year, today.month, today.day, 12, 0, 0),
            ))
        db.commit()

        daily = UpiLedgerService.get_today_upi_summary(db, 42)
        assert daily["today_upi_total"] == 100.0
        assert daily["confirmed_upi_total"] == 100.0
        assert daily["pending_upi_total"] == 200.0
        assert daily["failed_upi_total"] == 300.0
        assert daily["refunded_upi_total"] == 400.0
        assert daily["confirmed_transactions"] == 1
        assert daily["pending_transactions"] == 1
        assert daily["failed_transactions"] == 1
        assert daily["refunded_transactions"] == 1

        breakdown = UpiLedgerService.get_upi_by_id(db, 42)["upi_breakdown"]
        assert breakdown == [{
            "upi_id": "merchant-confirmed",
            "amount": 100.0,
            "transaction_count": 1,
        }]

        monthly = UpiLedgerService.get_monthly_upi_report(db, 42, today.year, today.month)
        assert monthly["total_upi"] == 100.0
        assert monthly["transaction_count"] == 1
        assert monthly["avg_transaction"] == 100.0
        assert monthly["pending_upi_total"] == 200.0
        assert monthly["failed_upi_total"] == 300.0
        assert monthly["refunded_upi_total"] == 400.0
        assert monthly["pending_transactions"] == 1
        assert monthly["failed_transactions"] == 1
        assert monthly["refunded_transactions"] == 1

    UpiLedger.__table__.drop(engine)
    engine.dispose()


def test_payment_idempotency_model_has_a_matching_versioned_migration():
    from pathlib import Path
    from models import Payment

    assert "idempotency_key" in Payment.__table__.c
    assert any(
        index.unique and [column.name for column in index.columns] == ["idempotency_key"]
        for index in Payment.__table__.indexes
    )

    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "039_payment_idempotency_key.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "039_payment_idempotency_key"' in migration
    assert 'down_revision = "038_legacy_startup_schema_repairs"' in migration
    # Keep the contract independent of whether the call is formatted on one
    # line or across multiple lines.
    import re

    assert re.search(r"""op\.add_column\(\s*["']payments["']""", migration)
    assert '"ix_payments_idempotency_key"' in migration



def test_payment_write_defaults_to_pending_and_requires_explicit_merchant_confirmation():
    import pytest
    from fastapi import HTTPException
    from invoices_billing import PaymentWriteRequest, _validate_payment_verification

    pending = PaymentWriteRequest(invoice_id=1, amount=10)
    with pytest.raises(HTTPException) as exc:
        _validate_payment_verification(pending)
    assert exc.value.status_code == 409
    assert "pending verification" in exc.value.detail.lower()

    confirmed = PaymentWriteRequest(
        invoice_id=1,
        amount=10,
        verification_status="MERCHANT_CONFIRMED",
        verification_method="MERCHANT_CONFIRMATION",
    )
    assert _validate_payment_verification(confirmed) == (
        "MERCHANT_CONFIRMED",
        "MERCHANT_CONFIRMATION",
    )


def test_public_payment_write_cannot_claim_provider_verification():
    import pytest
    from fastapi import HTTPException
    from invoices_billing import PaymentWriteRequest, _validate_payment_verification

    request = PaymentWriteRequest(
        invoice_id=1,
        amount=10,
        verification_status="PROVIDER_VERIFIED",
        verification_method="PROVIDER_API",
    )
    with pytest.raises(HTTPException) as exc:
        _validate_payment_verification(request)
    assert exc.value.status_code == 403


def test_payment_model_persists_verification_provenance():
    from models import Payment

    columns = Payment.__table__.c
    assert "verification_status" in columns
    assert "verification_method" in columns
    assert "verification_actor_id" in columns


def test_payment_verification_migration_is_versioned_and_fail_closed():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "040_payment_verification_provenance.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "040_payment_verification_provenance"' in migration
    assert 'down_revision = "039_payment_idempotency_key"' in migration
    assert '"LEGACY_UNVERIFIED"' in migration
    assert '"LEGACY_UNKNOWN"' in migration


def test_payment_writer_validates_verification_before_changing_invoice_balance():
    import inspect
    from invoices_billing import _apply_payment_write

    source = inspect.getsource(_apply_payment_write)
    guard = source.index("_validate_payment_verification(data)")
    balance_change = source.index("invoice.paid_amount = new_paid")
    assert guard < balance_change
    assert "verification_actor_id=verification_actor_id" in source


def test_payment_confirmation_actor_uses_authenticated_token_subject():
    from invoices_billing import _payment_actor_id

    assert _payment_actor_id({"user_id": 23, "role": "OWNER"}) == 23
    assert _payment_actor_id({"sub": "24", "role": "WORKER"}) == 24
    assert _payment_actor_id({"role": "OWNER"}) is None


def test_idempotency_replay_must_match_invoice_amount_and_reference():
    from types import SimpleNamespace
    from invoices_billing import PaymentWriteRequest, _payment_retry_matches

    existing = SimpleNamespace(amount=25.00, reference_number="UTR123")
    invoice = SimpleNamespace(id=7, invoice_number="BILL-0007")
    matching = PaymentWriteRequest(
        invoice_id=7,
        invoice_number="BILL-0007",
        amount=25,
        reference_id="UTR123",
        idempotency_key="same-key",
        verification_status="MERCHANT_CONFIRMED",
        verification_method="MERCHANT_CONFIRMATION",
    )
    assert _payment_retry_matches(
        existing=existing, existing_invoice=invoice, data=matching, mode="delta"
    )

    different_amount = matching.copy(update={"amount": 26})
    assert not _payment_retry_matches(
        existing=existing, existing_invoice=invoice, data=different_amount, mode="delta"
    )

    different_invoice = matching.copy(update={"invoice_id": 8})
    assert not _payment_retry_matches(
        existing=existing, existing_invoice=invoice, data=different_invoice, mode="delta"
    )

    different_reference = matching.copy(update={"reference_id": "UTR999"})
    assert not _payment_retry_matches(
        existing=existing, existing_invoice=invoice, data=different_reference, mode="delta"
    )
