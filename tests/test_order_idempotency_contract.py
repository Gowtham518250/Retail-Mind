def test_online_order_models_and_schemas_have_idempotency_key():
    from models import OnlineOrder
    from online_store import PlaceOrder, GuestOrder

    assert hasattr(OnlineOrder, "idempotency_key")
    assert "idempotency_key" in PlaceOrder.model_fields
    assert "idempotency_key" in GuestOrder.model_fields
    index_names = {index.name for index in OnlineOrder.__table__.indexes}
    assert "uq_online_order_request_idempotency" in index_names
    assert "uq_online_order_shop_payment_key" in index_names



def test_online_order_payment_state_and_request_contract():
    from models import OnlineOrder
    from online_store import GuestOrder, PlaceOrder, router

    assert hasattr(OnlineOrder, "payment_method")
    assert hasattr(OnlineOrder, "payment_status")
    assert hasattr(OnlineOrder, "payment_reference")
    assert hasattr(OnlineOrder, "payment_detection_key")
    assert PlaceOrder.model_fields["payment_method"].default == "COD"
    assert GuestOrder.model_fields["payment_method"].default == "COD"

    routes = {
        getattr(route, "path", "")
        for route in router.routes
    }
    assert "/store/owner/orders/match-notification-payment" in routes


def test_payment_notification_match_requires_reference_confidence_and_idempotency():
    import pytest
    from pydantic import ValidationError
    from online_store import PaymentNotificationMatch

    valid = PaymentNotificationMatch(
        amount=125.00,
        payment_reference="UTR12345",
        idempotency_key="payment-event-fingerprint",
        confidence_score=0.95,
        decision="CONFIRMED",
    )
    assert valid.amount == 125.00
    assert valid.confidence_score == 0.95

    with pytest.raises(ValidationError):
        PaymentNotificationMatch(
            amount=125.00,
            payment_reference="x",
            idempotency_key="short",
            confidence_score=0.95,
            decision="CONFIRMED",
        )



def test_cod_delivery_records_payment_in_the_delivery_transaction():
    import inspect
    from online_store import update_order_status

    source = inspect.getsource(update_order_status)
    assert 'payment_method="CASH"' in source
    assert "commit_transaction=False" in source
    assert "pending_payment_events.extend(payment_result.get(\"events\", []))" in source
    assert "cod_payment_key" in source
