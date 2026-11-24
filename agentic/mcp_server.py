"""Opt-in MCP Streamable HTTP adapter for Retail Mind's existing agent tools.

This endpoint reuses Retail Mind owner access JWTs. It is deliberately disabled
unless explicitly configured. MCP can prepare business actions, but confirmation
remains an authenticated owner-app action and is not exposed as an MCP tool.
"""
from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import uuid
from typing import Any

from fastapi.responses import JSONResponse
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.orm import Session

from db import SessionLocal
from models import AgentConversation, AgentMessage
from security import ROLE_OWNER, _validated_access_user_id, decode_token

from .tools import dispatch_tool

logger = logging.getLogger(__name__)
_current_shop_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "retail_mind_mcp_shop_id", default=None
)

mcp_server = MCPServer(
    "Retail Mind",
    instructions=(
        "Retail Mind tools for an authenticated shop owner. Use live tool results only. "
        "Business changes are previews only; the owner must confirm them in the Retail Mind app."
    ),
)
_mcp_asgi_app = None
_mcp_exit_stack: contextlib.AsyncExitStack | None = None


def _enabled() -> bool:
    enabled_values = {"1", "true", "yes", "on"}
    # MCP is an additional transport for the agent, not a separate feature
    # entitlement. Both switches must be enabled by an operator.
    return (
        os.getenv("RETAIL_MIND_MCP_ENABLED", "false").strip().lower() in enabled_values
        and os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() in enabled_values
    )


def _current_shop() -> int:
    shop_id = _current_shop_id.get()
    if not shop_id:
        raise PermissionError("An authenticated Retail Mind owner is required.")
    return int(shop_id)


async def _run_tool(name: str, arguments: dict[str, Any], *, user_text: str = "") -> dict:
    shop_id = _current_shop()
    db: Session = SessionLocal()
    needs_pending_action = name in {
        "prepare_bill_from_current_message",
        "prepare_invoice_payment",
        "prepare_online_order_transition",
        "prepare_khata_ledger_movement",
    }
    conversation_id = str(uuid.uuid4()) if needs_pending_action else None
    request_id = str(uuid.uuid4())
    try:
        # Only operations that create a pending action need a durable
        # conversation FK. Read-only MCP calls use a NULL audit conversation
        # reference and do not create an unbounded history row per tool call.
        if conversation_id:
            db.add(AgentConversation(
                id=conversation_id,
                user_id=shop_id,
                title=f"MCP: {name}"[:180],
            ))
            if user_text:
                db.add(AgentMessage(
                    conversation_id=conversation_id,
                    user_id=shop_id,
                    role="user",
                    content=user_text[:3000],
                ))
            db.commit()

        result = await dispatch_tool(
            name,
            json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
            {
                "db": db,
                "shop_id": shop_id,
                "conversation_id": conversation_id,
                "request_id": request_id,
                "user_text": user_text[:3000],
                "language_code": "auto",
            },
        )
        if conversation_id and user_text:
            db.add(AgentMessage(
                conversation_id=conversation_id,
                user_id=shop_id,
                role="assistant",
                content=(
                    "MCP tool result: " + json.dumps(result, ensure_ascii=False, default=str)
                )[:6000],
            ))
            db.commit()
        return result
    except Exception:
        db.rollback()
        logger.exception("Retail Mind MCP tool failed: %s", name)
        raise
    finally:
        db.close()


@mcp_server.tool()
async def search_inventory(query: str = "") -> dict:
    """Search the authenticated shop's catalogue and stock. Empty query returns low-stock items."""
    return await _run_tool("search_inventory", {"query": query})


@mcp_server.tool()
async def search_customers(query: str) -> dict:
    """Find customers in the authenticated shop. Phone numbers are masked to the last four digits."""
    return await _run_tool("search_customers", {"query": query})


@mcp_server.tool()
async def get_sales_summary(start_date: str | None = None, end_date: str | None = None) -> dict:
    """Read a bounded sales/payment summary for up to 180 days in the authenticated shop."""
    arguments = {}
    if start_date:
        arguments["start_date"] = start_date
    if end_date:
        arguments["end_date"] = end_date
    return await _run_tool("get_sales_summary", arguments)


@mcp_server.tool()
async def get_attendance_summary(attendance_date: str | None = None) -> dict:
    """Read attendance for one date in the authenticated shop."""
    arguments = {"attendance_date": attendance_date} if attendance_date else {}
    return await _run_tool("get_attendance_summary", arguments)


@mcp_server.tool()
async def get_khata_summary() -> dict:
    """Read invoice-derived receivables. This tool cannot create credit or record repayments."""
    return await _run_tool("get_khata_summary", {})


@mcp_server.tool()
async def get_online_order_summary(status: str | None = None) -> dict:
    """Read order status counts and recent online orders. This tool cannot mutate order states."""
    arguments = {"status": status} if status else {}
    return await _run_tool("get_online_order_summary", arguments)


@mcp_server.tool()
async def prepare_bill_from_text(message: str) -> dict:
    """Prepare a five-minute invoice preview. No invoice or stock movement is created.

    The owner must confirm the exact preview in the Retail Mind app.
    """
    return await _run_tool("prepare_bill_from_current_message", {}, user_text=message)


@mcp_server.tool()
async def prepare_invoice_payment(
    invoice_id: int,
    amount: float,
    payment_method: str = "CASH",
) -> dict:
    """Prepare a payment preview against one invoice. Does not record a payment."""
    return await _run_tool(
        "prepare_invoice_payment",
        {"invoice_id": invoice_id, "amount": amount, "payment_method": payment_method},
    )


@mcp_server.tool()
async def prepare_online_order_transition(order_id: int, action: str) -> dict:
    """Prepare ACCEPT, DISPATCH or REJECT for one order. DELIVERY requires customer OTP and is unavailable."""
    return await _run_tool(
        "prepare_online_order_transition",
        {"order_id": order_id, "action": action},
    )


@mcp_server.tool()
async def prepare_khata_ledger_movement(
    operation: str,
    customer_phone: str,
    amount: float,
    customer_name: str | None = None,
    description: str | None = None,
) -> dict:
    """Prepare a legacy Khata credit/repayment preview. Owner confirmation remains in the Retail Mind app."""
    return await _run_tool(
        "prepare_khata_ledger_movement",
        {
            "operation": operation,
            "customer_phone": customer_phone,
            "amount": amount,
            "customer_name": customer_name,
            "description": description,
        },
        user_text=f"{operation} Khata movement for customer ending {str(customer_phone)[-4:]}",
    )


class RetailMindOwnerJWTMiddleware:
    """Verify the same signed access JWT and OWNER role as the native API."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        authorization = headers.get("authorization", "")
        if not authorization.lower().startswith("bearer "):
            response = JSONResponse(
                {"detail": "A Retail Mind owner access token is required."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        token = authorization[7:].strip()
        try:
            payload = decode_token(token)
            shop_id = _validated_access_user_id(payload)
            role = str(payload.get("role") or "").strip().upper()
            if role != ROLE_OWNER:
                response = JSONResponse(
                    {"detail": "MCP access is restricted to shop owners."},
                    status_code=403,
                )
                await response(scope, receive, send)
                return
        except Exception:
            response = JSONResponse(
                {"detail": "Invalid or expired Retail Mind owner access token."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        token_context = _current_shop_id.set(shop_id)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_shop_id.reset(token_context)


def mount_mcp_server(api) -> bool:
    """Mount MCP only after explicit configuration and host/origin allowlists."""
    global _mcp_asgi_app
    if not _enabled():
        logger.info("Retail Mind MCP endpoint disabled by configuration")
        return False

    hosts = [
        item.strip()
        for item in os.getenv("RETAIL_MIND_MCP_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    ]
    origins = [
        item.strip()
        for item in os.getenv("RETAIL_MIND_MCP_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    ]
    if not hosts or not origins:
        raise RuntimeError(
            "RETAIL_MIND_MCP_ENABLED requires explicit RETAIL_MIND_MCP_ALLOWED_HOSTS "
            "and RETAIL_MIND_MCP_ALLOWED_ORIGINS."
        )

    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )
    _mcp_asgi_app = mcp_server.streamable_http_app(
        host="0.0.0.0",
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        max_request_body_size=1024 * 1024,
        transport_security=transport_security,
    )
    api.mount("/mcp", RetailMindOwnerJWTMiddleware(_mcp_asgi_app))

    async def _startup() -> None:
        global _mcp_exit_stack
        if _mcp_exit_stack is not None:
            return
        _mcp_exit_stack = contextlib.AsyncExitStack()
        await _mcp_exit_stack.__aenter__()
        await _mcp_exit_stack.enter_async_context(mcp_server.session_manager.run())
        logger.info("Retail Mind MCP Streamable HTTP server started")

    async def _shutdown() -> None:
        global _mcp_exit_stack
        if _mcp_exit_stack is not None:
            await _mcp_exit_stack.aclose()
            _mcp_exit_stack = None
            logger.info("Retail Mind MCP Streamable HTTP server stopped")

    api.add_event_handler("startup", _startup)
    api.add_event_handler("shutdown", _shutdown)
    logger.info("Retail Mind MCP endpoint mounted at /mcp")
    return True
