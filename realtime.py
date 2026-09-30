"""
Deployment-safe realtime event transport for customer/owner order updates.

Architecture:
- HTTP-authenticated short-lived realtime ticket (2 minutes).
- WebSocket connections are authorized by the ticket.
- Redis Pub/Sub is the cross-worker/process event bus.
- Each FastAPI worker keeps only its local WebSocket connections.
- Customer connections receive only their own order events.
- Owner connections receive events for their own shop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import redis
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from security import (
    ALGORITHM,
    ROLE_CUSTOMER,
    ROLE_OWNER,
    SECRET_KEY,
    get_current_user_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ws", tags=["Realtime"])

REDIS_URL = os.getenv("REDIS_URL")
REALTIME_REDIS_CHANNEL = os.getenv(
    "REALTIME_REDIS_CHANNEL",
    "retail-mind:realtime:events",
)
REALTIME_TICKET_TTL_SECONDS = max(
    30,
    min(int(os.getenv("REALTIME_TICKET_TTL_SECONDS", "120")), 300),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_realtime_ticket(user_id: int, role: str, shop_id: int) -> str:
    """Create a short-lived JWT used only for opening a realtime socket."""
    now = _utc_now()
    payload = {
        "sub": str(user_id),
        "role": role,
        "shop_id": int(shop_id),
        "type": "realtime",
        "iat": now,
        "exp": now + timedelta(seconds=REALTIME_TICKET_TTL_SECONDS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_realtime_ticket(ticket: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(ticket, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired realtime ticket") from exc

    if payload.get("type") != "realtime":
        raise ValueError("Invalid realtime ticket type")

    if not payload.get("sub") or payload.get("role") not in {
        ROLE_OWNER,
        ROLE_CUSTOMER,
    }:
        raise ValueError("Invalid realtime ticket claims")

    return payload


@router.get("/token")
def issue_realtime_token(
    shop_id: int = Query(0, ge=0, description="Owner shop ID; 0 means all customer shops."),
    current_user: dict = Depends(get_current_user_dict),
):
    """Issue a short-lived socket ticket after normal HTTP JWT authentication."""
    user_id = int(current_user["user_id"])
    role = current_user["role"]

    if role == ROLE_OWNER:
        # An owner may only open the realtime stream for their own shop.
        if shop_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Owners can only subscribe to their own shop realtime stream.",
            )
    elif role == ROLE_CUSTOMER:
        # Customers can use shop_id=0 to receive events for all of their shops.
        # The WebSocket layer still filters every event by customer_id.
        if shop_id < 0:
            raise HTTPException(status_code=400, detail="Invalid shop subscription.")
    else:
        raise HTTPException(status_code=403, detail="Realtime access is not enabled for this role.")

    token = create_realtime_ticket(user_id=user_id, role=role, shop_id=shop_id)

    return {
        "token": token,
        "user_id": user_id,
        "role": role,
        "shop_id": shop_id,
        "expires_in": REALTIME_TICKET_TTL_SECONDS,
    }


@dataclass
class _RealtimeConnection:
    websocket: WebSocket
    user_id: int
    role: str
    shop_id: int
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def send(self, payload: Dict[str, Any]) -> bool:
        try:
            async with self.send_lock:
                await self.websocket.send_json(payload)
            return True
        except Exception:
            return False


class _RealtimeManager:
    def __init__(self) -> None:
        self._connections: Dict[int, _RealtimeConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(self, connection: _RealtimeConnection) -> None:
        async with self._lock:
            self._connections[id(connection.websocket)] = connection

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(id(websocket), None)

    @staticmethod
    def _should_deliver(connection: _RealtimeConnection, event: Dict[str, Any]) -> bool:
        try:
            event_shop_id = int(event.get("shop_id", 0))
        except (TypeError, ValueError):
            return False

        # Owner streams are scoped to exactly one shop.
        if connection.role == ROLE_OWNER:
            return event_shop_id == connection.shop_id

        # Customer streams are scoped to their own customer_id. shop_id=0 means
        # all shops for this customer, while a positive shop_id scopes to one shop.
        if connection.role == ROLE_CUSTOMER:
            try:
                event_customer_id = int(event.get("customer_id", -1))
            except (TypeError, ValueError):
                return False
            if event_customer_id != connection.user_id:
                return False
            return connection.shop_id == 0 or event_shop_id == connection.shop_id

        return False

    async def broadcast(self, event: Dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self._connections.values())

        stale = []
        for connection in connections:
            if not self._should_deliver(connection, event):
                continue
            if not await connection.send(event):
                stale.append(connection.websocket)

        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.pop(id(websocket), None)


class _RedisEventBridge:
    """One Redis subscription task per FastAPI worker/process."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task[None]] = None
        self._redis: Optional[aioredis.Redis] = None
        self._start_lock = asyncio.Lock()

    async def start(self) -> None:
        if not REDIS_URL:
            raise RuntimeError("REDIS_URL is not configured; realtime transport is disabled.")

        if self._task and not self._task.done():
            return

        async with self._start_lock:
            if self._task and not self._task.done():
                return
            self._task = asyncio.create_task(
                self._run_forever(),
                name="retail-mind-realtime-redis",
            )

            # Fail fast for the current socket if Redis is unreachable.
            try:
                if self._redis is None:
                    self._redis = aioredis.from_url(
                        REDIS_URL,
                        decode_responses=True,
                        health_check_interval=30,
                    )
                await self._redis.ping()
            except Exception:
                if self._task and not self._task.done():
                    self._task.cancel()
                self._task = None
                raise

    async def _run_forever(self) -> None:
        while True:
            pubsub = None
            try:
                if self._redis is None:
                    self._redis = aioredis.from_url(
                        REDIS_URL or "redis://localhost:6379",
                        decode_responses=True,
                        health_check_interval=30,
                    )

                pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
                await pubsub.subscribe(REALTIME_REDIS_CHANNEL)
                logger.info(
                    "Realtime Redis subscriber ready on channel %s",
                    REALTIME_REDIS_CHANNEL,
                )

                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    raw = message.get("data")
                    if not raw:
                        continue
                    try:
                        event = json.loads(raw)
                    except (TypeError, json.JSONDecodeError):
                        logger.warning("Ignoring malformed realtime event from Redis.")
                        continue
                    if isinstance(event, dict):
                        await realtime_manager.broadcast(event)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Realtime Redis subscriber disconnected: %s", exc)
                await asyncio.sleep(2)
            finally:
                if pubsub is not None:
                    try:
                        await pubsub.close()
                    except Exception:
                        pass


realtime_manager = _RealtimeManager()
redis_event_bridge = _RedisEventBridge()

_publisher: Optional[redis.Redis] = None


def _get_sync_publisher() -> redis.Redis:
    global _publisher
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL is not configured; realtime transport is disabled.")
    if _publisher is None:
        _publisher = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            health_check_interval=30,
        )
    return _publisher


def publish_realtime_event(event: Dict[str, Any]) -> bool:
    """
    Publish a single JSON event after the DB transaction has committed.

    This is intentionally synchronous because the current ERP routes are
    synchronous FastAPI handlers. The Redis connection pool is reused.
    """
    if not REDIS_URL:
        logger.warning("Realtime event dropped because REDIS_URL is not configured.")
        return False

    payload = dict(event)
    payload.setdefault("version", 1)
    payload.setdefault("occurred_at", _utc_now().isoformat())

    try:
        message = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        delivered = _get_sync_publisher().publish(REALTIME_REDIS_CHANNEL, message)
        logger.debug(
            "Published realtime event type=%s event_id=%s subscribers=%s",
            payload.get("type"),
            payload.get("event_id"),
            delivered,
        )
        return True
    except Exception as exc:
        logger.error(
            "Realtime publish failed type=%s event_id=%s: %s",
            payload.get("type"),
            payload.get("event_id"),
            exc,
        )
        return False


@router.websocket("/live/{user_id}/{shop_id}")
async def realtime_socket(
    websocket: WebSocket,
    user_id: int,
    shop_id: int,
    ticket: str = Query(...),
):
    """Authenticated realtime socket used by the mobile app and customer web."""
    try:
        payload = _decode_realtime_ticket(ticket)
        token_user_id = int(payload["sub"])
        token_shop_id = int(payload.get("shop_id", 0))
        role = payload["role"]

        if token_user_id != int(user_id):
            raise ValueError("Realtime ticket user mismatch")
        if token_shop_id != int(shop_id):
            raise ValueError("Realtime ticket shop mismatch")

        if role == ROLE_OWNER and shop_id != user_id:
            raise ValueError("Owner realtime scope mismatch")
        if role == ROLE_CUSTOMER and shop_id < 0:
            raise ValueError("Customer realtime scope mismatch")

        await redis_event_bridge.start()
    except (ValueError, RuntimeError) as exc:
        await websocket.close(code=1008, reason=str(exc))
        return
    except Exception:
        await websocket.close(code=1013, reason="Realtime service unavailable")
        return

    await websocket.accept()

    connection = _RealtimeConnection(
        websocket=websocket,
        user_id=user_id,
        role=role,
        shop_id=shop_id,
    )
    await realtime_manager.connect(connection)

    await connection.send(
        {
            "type": "realtime.ready",
            "version": 1,
            "role": role,
            "shop_id": shop_id,
            "occurred_at": _utc_now().isoformat(),
        }
    )

    try:
        while True:
            message = await websocket.receive_json()
            action = str(message.get("action", "")).strip().lower()

            if action == "ping":
                await connection.send(
                    {
                        "type": "realtime.pong",
                        "occurred_at": _utc_now().isoformat(),
                    }
                )
            elif action == "subscribe":
                # Subscription is currently implicit in the signed ticket.
                # Keep this acknowledgement for backwards compatibility with
                # the Flutter client, while ignoring client-supplied channels.
                await connection.send(
                    {
                        "type": "realtime.subscribed",
                        "channel": "all",
                        "occurred_at": _utc_now().isoformat(),
                    }
                )
            else:
                await connection.send(
                    {
                        "type": "realtime.error",
                        "code": "unsupported_action",
                        "message": "Supported actions: ping, subscribe",
                    }
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("Realtime socket ended: %s", exc)
    finally:
        await realtime_manager.disconnect(websocket)
