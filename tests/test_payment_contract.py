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
