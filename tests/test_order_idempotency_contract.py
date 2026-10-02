def test_online_order_models_and_schemas_have_idempotency_key():
    from models import OnlineOrder
    from online_store import PlaceOrder, GuestOrder

    assert hasattr(OnlineOrder, "idempotency_key")
    assert "idempotency_key" in PlaceOrder.model_fields
    assert "idempotency_key" in GuestOrder.model_fields
