import os

os.environ.setdefault("SECRET_KEY", "ci-realtime-secret-key-for-tests-only-1234567890")

from realtime import (
    _RealtimeConnection,
    _RealtimeManager,
    _decode_realtime_ticket,
    create_realtime_ticket,
)
from security import ROLE_CUSTOMER, ROLE_OWNER


def _connection(user_id: int, role: str, shop_id: int) -> _RealtimeConnection:
    return _RealtimeConnection(
        websocket=object(),  # type: ignore[arg-type]
        user_id=user_id,
        role=role,
        shop_id=shop_id,
    )


def test_realtime_ticket_round_trip():
    token = create_realtime_ticket(user_id=42, role=ROLE_CUSTOMER, shop_id=0)
    payload = _decode_realtime_ticket(token)

    assert payload["sub"] == "42"
    assert payload["role"] == ROLE_CUSTOMER
    assert payload["shop_id"] == 0
    assert payload["type"] == "realtime"


def test_owner_receives_only_own_shop_events():
    manager = _RealtimeManager()
    owner = _connection(user_id=7, role=ROLE_OWNER, shop_id=7)

    assert manager._should_deliver(
        owner,
        {"shop_id": 7, "customer_id": 21, "type": "order.status_changed"},
    )
    assert not manager._should_deliver(
        owner,
        {"shop_id": 8, "customer_id": 21, "type": "order.status_changed"},
    )


def test_customer_receives_only_own_order_events():
    manager = _RealtimeManager()
    customer = _connection(user_id=42, role=ROLE_CUSTOMER, shop_id=0)

    assert manager._should_deliver(
        customer,
        {"shop_id": 7, "customer_id": 42, "type": "order.status_changed"},
    )
    assert not manager._should_deliver(
        customer,
        {"shop_id": 7, "customer_id": 99, "type": "order.status_changed"},
    )


def test_customer_shop_scope_can_be_restricted():
    manager = _RealtimeManager()
    customer = _connection(user_id=42, role=ROLE_CUSTOMER, shop_id=7)

    assert manager._should_deliver(
        customer,
        {"shop_id": 7, "customer_id": 42, "type": "order.status_changed"},
    )
    assert not manager._should_deliver(
        customer,
        {"shop_id": 8, "customer_id": 42, "type": "order.status_changed"},
    )


def test_owner_receives_inventory_events_for_own_shop():
    manager = _RealtimeManager()
    owner = _connection(user_id=7, role=ROLE_OWNER, shop_id=7)

    event = {
        "shop_id": 7,
        "type": "inventory.changed",
        "product_id": 123,
        "new_stock": 4,
    }

    assert manager._should_deliver(owner, event)
    assert not manager._should_deliver(
        _connection(user_id=8, role=ROLE_OWNER, shop_id=8),
        event,
    )


def test_customer_does_not_receive_shop_inventory_events():
    manager = _RealtimeManager()
    customer = _connection(user_id=42, role=ROLE_CUSTOMER, shop_id=0)

    assert not manager._should_deliver(
        customer,
        {
            "shop_id": 7,
            "type": "inventory.changed",
            "product_id": 123,
            "new_stock": 4,
        },
    )
