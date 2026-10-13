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
