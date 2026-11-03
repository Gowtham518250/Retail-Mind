"""Contract tests for owner-scoped payment detection evidence."""

def test_payment_detection_evidence_routes_are_registered():
    from invoices_billing import router

    routes = {
        (route.path, method)
        for route in router.routes
        for method in (route.methods or set())
    }
    assert ("/api/invoices/payment-detections", "POST") in routes
    assert ("/api/invoices/payment-detections", "GET") in routes


def test_payment_detection_evidence_model_has_per_shop_event_idempotency():
    from models import PaymentDetectionEvent

    table = PaymentDetectionEvent.__table__
    assert {
        "shop_id",
        "event_key",
        "amount",
        "direction",
        "payer_name",
        "payer_phone",
        "detected_source",
        "confidence_score",
        "decision",
        "verification_status",
    } <= set(table.c.keys())
    assert any(
        constraint.name == "uq_payment_detection_shop_event"
        for constraint in table.constraints
    )


def test_payment_detection_evidence_is_untrusted_and_never_auto_verifies():
    from invoices_billing import PaymentDetectionEvidenceCreate

    base = {
        "event_key": "event_0123456789abcdef",
        "amount": "125.50",
        "direction": "credit",
        "detected_source": "notification+sms",
        "decision": "confirmed",
        "verification_status": "provider_verified",
        "confidence_score": "0.98",
    }
    event = PaymentDetectionEvidenceCreate(**base)
    assert event.verification_status == "unverified"


def test_debit_evidence_is_not_a_credit_and_unknown_direction_is_explicit():
    from invoices_billing import PaymentDetectionEvidenceCreate

    common = {
        "event_key": "event_0123456789abcdef",
        "amount": "250",
        "detected_source": "bank_sms",
    }
    debit = PaymentDetectionEvidenceCreate(**common, direction="debit")
    unknown = PaymentDetectionEvidenceCreate(**common, direction="unknown")
    assert debit.direction == "debit"
    assert unknown.direction == "unknown"


def test_detection_evidence_route_does_not_call_financial_payment_writer():
    import inspect
    from invoices_billing import create_payment_detection_evidence

    source = inspect.getsource(create_payment_detection_evidence)
    assert "PaymentDetectionEvent(" in source
    assert "_apply_payment_write(" not in source
    assert "Payment(" not in source
