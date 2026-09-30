"""
Retail Mind realtime event hub.

Provides authenticated WebSocket channels for:
- owners: inventory/order events for a shop
- customers: order status events for their account

The hub is intentionally in-process and dependency-free. It degrades safely when
no WebSocket clients are connected. For multi-instance deployments, Redis/pubsub
can be added later without changing event payloads.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from security import decode_token, ROLE_OWNER, ROLE_CUSTOMER

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Realtime"])


class RealtimeEventHub:
    def __init__(self) -> None:
        self._owner_clients: dict[int, set[WebSocket]] = defaultdict(set)
        self._customer_clients: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect_owner(self, shop_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._owner_clients[shop_id].add(websocket)

    async def connect_customer(self, customer_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._customer_clients[customer_id].add(websocket)

    async def disconnect_owner(self, shop_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._owner_clients[shop_id].discard(websocket)
            if not self._owner_clients[shop_id]:
                self._owner_clients.pop(shop_id, None)

    async def disconnect_customer(self, customer_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._customer_clients[customer_id].discard(websocket)
            if not self._customer_clients[customer_id]:
                self._customer_clients.pop(customer_id, None)

    async def _broadcast(self, clients: set[WebSocket], payload: dict[str, Any]) -> None:
        if not clients:
            return
        stale: list[WebSocket] = []
        for websocket in list(clients):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    clients.discard(websocket)

    async def owner_event(self, shop_id: int, payload: dict[str, Any]) -> None:
        await self._broadcast(self._owner_clients.get(shop_id, set()), payload)

    async def customer_event(self, customer_id: int, payload: dict[str, Any]) -> None:
        await self._broadcast(self._customer_clients.get(customer_id, set()), payload)


event_hub = RealtimeEventHub()


def _authenticate_websocket(websocket: WebSocket, expected_role: str, expected_user_id: int) -> None:
    token = websocket.query_params.get("token")
    if not token:
        raise ValueError("Missing token")

    payload = decode_token(token)
    actual_role = payload.get("role")
    actual_user_id = int(payload.get("sub", 0))
    if actual_role != expected_role or actual_user_id != expected_user_id:
        raise ValueError("WebSocket identity mismatch")


@router.websocket("/ws/owner/{shop_id}")
async def owner_realtime(websocket: WebSocket, shop_id: int) -> None:
    try:
        _authenticate_websocket(websocket, ROLE_OWNER, shop_id)
        await event_hub.connect_owner(shop_id, websocket)
        await websocket.send_json({
            "type": "connected",
            "channel": "owner",
            "shop_id": shop_id,
        })
        while True:
            # Client heartbeat. Messages are intentionally ignored.
            await websocket.receive_text()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as exc:
        logger.info("Owner websocket rejected/closed for shop %s: %s", shop_id, exc)
        try:
            await websocket.close(code=1008)
        except Exception:
            pass
    finally:
        await event_hub.disconnect_owner(shop_id, websocket)


@router.websocket("/ws/customer/{customer_id}")
async def customer_realtime(websocket: WebSocket, customer_id: int) -> None:
    try:
        _authenticate_websocket(websocket, ROLE_CUSTOMER, customer_id)
        await event_hub.connect_customer(customer_id, websocket)
        await websocket.send_json({
            "type": "connected",
            "channel": "customer",
            "customer_id": customer_id,
        })
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as exc:
        logger.info("Customer websocket rejected/closed for customer %s: %s", customer_id, exc)
        try:
            await websocket.close(code=1008)
        except Exception:
            pass
    finally:
        await event_hub.disconnect_customer(customer_id, websocket)
