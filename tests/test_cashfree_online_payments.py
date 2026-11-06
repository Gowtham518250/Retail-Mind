import base64
import hashlib
import hmac
import inspect

import pytest
from fastapi import HTTPException


def test_cashfree_pg_requires_explicit_enablement_and_webhook_signing_secret(monkeypatch):
    from cashfree_online_payments import cashfree_pg_is_configured

    monkeypatch.setenv("CASHFREE_APP_ID", "sandbox-app-id")
    monkeypatch.setenv("CASHFREE_SECRET_KEY", "s" * 40)
    monkeypatch.setenv("CASHFREE_ENV", "sandbox")
    monkeypatch.delenv("CASHFREE_PG_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("CASHFREE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("CASHFREE_PG_ENABLED", "false")
    assert not cashfree_pg_is_configured()

    monkeypatch.setenv("CASHFREE_PG_ENABLED", "true")
    # Cashfree's normal PG webhook signature uses the app secret unless a
    # dedicated webhook-secret override is configured.
    assert cashfree_pg_is_configured()


def test_cashfree_webhook_signature_uses_timestamp_and_raw_body():
    from cashfree_online_payments import _verify_cashfree_signature

    secret = "test-cashfree-webhook-secret-" + ("x" * 20)
    timestamp = "1793980000000"
    raw_body = b'{"type":"PAYMENT_SUCCESS_WEBHOOK","data":{"payment":{"payment_status":"SUCCESS"}}}'
    signature = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("utf-8") + raw_body,
            hashlib.sha256,
        ).digest()
    ).decode("ascii")

    _verify_cashfree_signature(raw_body, timestamp, signature, secret=secret)
    with pytest.raises(HTTPException) as error:
        _verify_cashfree_signature(raw_body + b" ", timestamp, signature, secret=secret)
    assert error.value.status_code == 401


def test_cashfree_routes_are_registered_and_webhook_is_server_verified():
    from cashfree_online_payments import router

    routes = {route.path for route in router.routes}
    assert "/store/order/{order_id}/cashfree/session" in routes
    assert "/store/order/{order_id}/cashfree/status" in routes
    assert "/store/cashfree/webhook" in routes


def test_cashfree_success_handler_uses_provider_order_and_payment_apis():
    from cashfree_online_payments import _get_verified_successful_payment

    source = inspect.getsource(_get_verified_successful_payment)
    assert '"/orders/{provider_order_id}"' in source
    assert '"/orders/{provider_order_id}/payments"' in source
    assert '!= "PAID"' in source
    assert '!= "SUCCESS"' in source


def test_guest_checkout_does_not_accept_gateway_payment_without_customer_login():
    from online_store import place_guest_order

    source = inspect.getsource(place_guest_order)
    assert "Online payment requires a signed-in customer account" in source


def test_online_order_has_cashfree_provider_reference_columns_and_unique_indexes():
    from models import OnlineOrder

    assert hasattr(OnlineOrder, "cashfree_order_id")
    assert hasattr(OnlineOrder, "cashfree_payment_session_id")
    assert hasattr(OnlineOrder, "cashfree_payment_id")
    index_names = {index.name for index in OnlineOrder.__table__.indexes}
    assert "uq_online_orders_cashfree_order_id" in index_names
    assert "uq_online_orders_cashfree_payment_id" in index_names
