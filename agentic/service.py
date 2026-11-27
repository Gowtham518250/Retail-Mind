"""Persistence and confirmation services for the Retail Mind agent."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import (
    AgentConversation,
    AgentMessage,
    AgentPendingAction,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    OnlineOrder,
    Payment,
    StockMovement,
    StockMovementType,
)

from .graph import SYSTEM_PROMPT, invoke_agent
from .preview_policy import expired_preview_detail


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso_utc(value: datetime | None) -> str | None:
    """Serialize DB timestamps as unambiguous UTC ISO-8601 values.

    The database stores these columns as naive UTC for legacy compatibility.
    Returning a naive ISO string makes mobile clients interpret it as local
    time, shifting conversation timestamps by the device's UTC offset.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _action_hash(action_id: str, shop_id: int, preview: dict, payload: dict) -> str:
    material = {"action_id": action_id, "shop_id": int(shop_id), "preview": preview, "payload": payload}
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def _message_history(db: Session, conversation_id: str, shop_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(AgentMessage)
        .filter(
            AgentMessage.conversation_id == conversation_id,
            AgentMessage.user_id == shop_id,
            AgentMessage.role.in_(["user", "assistant"]),
        )
        .order_by(AgentMessage.id.desc())
        .limit(12)
        .all()
    )
    rows.reverse()
    return [
        {
            "role": row.role,
            "content": row.content[:6000],
            "created_at": row.created_at,
        }
        for row in rows
    ]


async def run_chat_turn(
    db: Session,
    *,
    shop_id: int,
    message: str,
    conversation_id: str | None = None,
    language_code: str = "auto",
    allow_actions: bool = True,
) -> dict:
    if os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=503, detail="The Retail Mind AI assistant is not enabled on this deployment.")
    if not (os.getenv("GROQ_API_KEY") or "").strip():
        raise HTTPException(status_code=503, detail="The AI provider is not configured.")
    clean_message = " ".join(str(message or "").split())
    if not clean_message:
        raise HTTPException(status_code=422, detail="Enter a message for the assistant.")
    if len(clean_message) > 3000:
        raise HTTPException(status_code=413, detail="Message is too long. Keep it under 3,000 characters.")

    if conversation_id:
        conversation = (
            db.query(AgentConversation)
            .filter(
                AgentConversation.id == conversation_id,
                AgentConversation.user_id == shop_id,
            )
            .first()
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        conversation_id = str(uuid.uuid4())
        conversation = AgentConversation(
            id=conversation_id,
            user_id=shop_id,
            title=clean_message[:160],
        )
        db.add(conversation)
        # Persist the conversation shell before making a provider call. Never
        # hold a PostgreSQL transaction open while waiting on an LLM network call.
        db.commit()

    history_rows = _message_history(db, conversation_id, shop_id)
    # Keep only recent owner-authored turns as optional bill context. Assistant
    # messages are deliberately excluded so an earlier model suggestion can
    # never become a user-confirmed product, quantity or price.
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    recent_user_messages = []
    history = []
    for row in history_rows:
        history.append({"role": row["role"], "content": row["content"]})
        created_at = row.get("created_at")
        if isinstance(created_at, datetime):
            if created_at.tzinfo is not None:
                created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            if row["role"] == "user" and created_at >= cutoff:
                recent_user_messages.append(row["content"][:1200])

    # End the read transaction before calling Groq. Tool executions open their
    # own short transactions and commit their audit/action records individually.
    db.rollback()
    language_code_normalized = str(language_code or "en").strip().lower().split("-", 1)[0]
    language_names = {
        "en": "English", "te": "Telugu", "hi": "Hindi", "ta": "Tamil",
        "kn": "Kannada", "ml": "Malayalam", "bn": "Bengali",
        "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi", "od": "Odia",
    }
    response_language = language_names.get(language_code_normalized, "English")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                f"RESPONSE LANGUAGE: {response_language}. Reply to this owner in "
                f"{response_language} in every conversational answer, question, "
                "confirmation and business explanation. Keep customer and product "
                "names, invoice identifiers, amounts and currency values exact. "
                "Do not switch to English unless the owner asks for English."
            ),
        },
        *history,
    ]
    messages.append({"role": "user", "content": clean_message})

    request_id = str(uuid.uuid4())
    context = {
        "db": db,
        "shop_id": int(shop_id),
        "conversation_id": conversation_id,
        "request_id": request_id,
        "user_text": clean_message,
        "language_code": str(language_code or "auto")[:16],
        "allow_actions": bool(allow_actions),
        "recent_user_messages": recent_user_messages[-5:],
    }

    result = await invoke_agent(messages, context, allow_actions=allow_actions)
    answer = str(result.get("answer") or "").strip()[:6000]
    if not answer:
        answer = "I could not complete that request. Please try again."

    db.add(AgentMessage(
        conversation_id=conversation_id,
        user_id=shop_id,
        role="user",
        content=clean_message,
    ))
    db.add(AgentMessage(
        conversation_id=conversation_id,
        user_id=shop_id,
        role="assistant",
        content=answer,
    ))
    conversation.updated_at = _utcnow()

    pending_actions = []
    for output in result.get("tool_outputs", []):
        tool_result = output.get("result") if isinstance(output, dict) else None
        if (
            isinstance(tool_result, dict)
            and tool_result.get("success")
            and tool_result.get("action_id")
            and tool_result.get("preview_hash")
            and tool_result.get("preview")
            and str(tool_result.get("status") or "PENDING").upper() == "PENDING"
        ):
            pending_actions.append({
                "action_id": tool_result["action_id"],
                "status": tool_result.get("status", "PENDING"),
                "preview_hash": tool_result["preview_hash"],
                "preview": tool_result["preview"],
            })

    return {
        "success": True,
        "conversation_id": conversation_id,
        "request_id": request_id,
        "answer": answer,
        "pending_actions": pending_actions,
        "tool_rounds": int(result.get("tool_rounds", 0)),
    }


def list_conversations(db: Session, *, shop_id: int, limit: int = 30) -> dict:
    bounded_limit = max(1, min(int(limit), 50))
    rows = (
        db.query(AgentConversation)
        .filter(AgentConversation.user_id == shop_id)
        .order_by(AgentConversation.updated_at.desc())
        .limit(bounded_limit)
        .all()
    )
    return {
        "conversations": [
            {
                "conversation_id": row.id,
                "title": row.title,
                "created_at": _iso_utc(row.created_at),
                "updated_at": _iso_utc(row.updated_at),
            }
            for row in rows
        ]
    }


def get_conversation_messages(
    db: Session, *, shop_id: int, conversation_id: str, limit: int = 50
) -> dict:
    exists = db.query(AgentConversation.id).filter(
        AgentConversation.id == conversation_id,
        AgentConversation.user_id == shop_id,
    ).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    rows = (
        db.query(AgentMessage)
        .filter(
            AgentMessage.conversation_id == conversation_id,
            AgentMessage.user_id == shop_id,
        )
        .order_by(AgentMessage.id.desc())
        .limit(max(1, min(int(limit), 100)))
        .all()
    )
    rows.reverse()
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "role": row.role,
                "content": row.content,
                "created_at": _iso_utc(row.created_at),
            }
            for row in rows
        ],
    }


def delete_conversation(db: Session, *, shop_id: int, conversation_id: str) -> dict:
    conversation = db.query(AgentConversation).filter(
        AgentConversation.id == conversation_id,
        AgentConversation.user_id == shop_id,
    ).with_for_update().first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    running = db.query(AgentPendingAction.id).filter(
        AgentPendingAction.conversation_id == conversation_id,
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.status == "EXECUTING",
    ).first()
    if running:
        raise HTTPException(status_code=409, detail="This conversation has an action being processed. Try again after it finishes.")
    db.query(AgentPendingAction).filter(
        AgentPendingAction.conversation_id == conversation_id,
        AgentPendingAction.user_id == shop_id,
    ).delete(synchronize_session=False)
    db.query(AgentMessage).filter(
        AgentMessage.conversation_id == conversation_id,
        AgentMessage.user_id == shop_id,
    ).delete(synchronize_session=False)
    db.delete(conversation)
    db.flush()
    return {"success": True, "conversation_id": conversation_id, "message": "Conversation and its pending previews were deleted."}


def _invoice_verification(db: Session, *, shop_id: int, action: AgentPendingAction) -> dict | None:
    invoice = db.query(Invoice).filter(
        Invoice.user_id == shop_id,
        Invoice.invoice_number == action.invoice_number,
    ).first()
    if not invoice:
        return None

    # An identical invoice number alone is not enough to reconcile a possibly
    # interrupted retry; verify it belongs to this exact AI preview.
    if f"Action {action.id}" not in str(invoice.notes or ""):
        return None

    line_rows = db.query(InvoiceLineItem).filter(
        InvoiceLineItem.invoice_id == invoice.id
    ).all()
    expected_lines = action.payload.get("line_items") or []
    if len(line_rows) != len(expected_lines):
        return None

    def _line_signature(line: dict) -> tuple:
        quantity = Decimal(str(line["quantity"])).quantize(Decimal("0.001"))
        unit_price = Decimal(str(line["unit_price"])).quantize(Decimal("0.01"))
        discount = Decimal(str(line.get("discount_amount") or "0")).quantize(Decimal("0.01"))
        line_total = (quantity * unit_price - discount).quantize(Decimal("0.01"))
        return (
            int(line["product_id"]) if line.get("product_id") is not None else -1,
            " ".join(str(line.get("product_name") or "").split()).casefold(),
            quantity,
            unit_price,
            discount,
            line_total,
        )

    def _stored_line_signature(line: InvoiceLineItem) -> tuple:
        return (
            int(line.product_id) if line.product_id is not None else -1,
            " ".join(str(line.description or "").split()).casefold(),
            Decimal(str(line.quantity)).quantize(Decimal("0.001")),
            Decimal(str(line.unit_price)).quantize(Decimal("0.01")),
            Decimal(str(line.discount_amount or 0)).quantize(Decimal("0.01")),
            Decimal(str(line.line_total)).quantize(Decimal("0.01")),
        )

    if sorted(_line_signature(line) for line in expected_lines) != sorted(
        _stored_line_signature(line) for line in line_rows
    ):
        return None

    expected_stock: dict[int, Decimal] = {}
    for line in expected_lines:
        if line.get("product_id") is not None:
            product_id = int(line["product_id"])
            expected_stock[product_id] = expected_stock.get(product_id, Decimal("0")) + Decimal(str(line["quantity"]))

    for product_id, expected_quantity in expected_stock.items():
        movements = db.query(StockMovement).filter(
            StockMovement.product_id == product_id,
            StockMovement.reference_id == action.invoice_number,
            StockMovement.movement_type == StockMovementType.OUT,
        ).all()
        recorded_quantity = sum(Decimal(str(row.quantity or 0)) for row in movements)
        if recorded_quantity != expected_quantity:
            return None

    expected_total = Decimal(str(action.payload["total_amount"])).quantize(Decimal("0.01"))
    actual_total = Decimal(str(invoice.total_amount or 0)).quantize(Decimal("0.01"))
    if actual_total != expected_total:
        return None
    if Decimal(str(invoice.paid_amount or 0)).quantize(Decimal("0.01")) != Decimal("0.00"):
        return None
    if Decimal(str(invoice.tax or 0)).quantize(Decimal("0.01")) != Decimal(
        str(action.payload.get("tax") or "0")
    ).quantize(Decimal("0.01")):
        return None

    return {
        "success": True,
        "invoice_id": int(invoice.id),
        "invoice_number": str(invoice.invoice_number),
        "total_amount": float(actual_total),
        "paid_amount": float(invoice.paid_amount or 0),
        "status": str(getattr(invoice.status, "value", invoice.status)),
        "payment_status": str(getattr(invoice.payment_status, "value", invoice.payment_status)),
        "line_items_count": len(line_rows),
        "verified": True,
        "message": "Invoice and required stock movements were found in the database.",
    }


def _complete_action(db: Session, action: AgentPendingAction, result: dict) -> dict:
    action.status = "COMPLETED"
    action.completed_at = _utcnow()
    action.updated_at = _utcnow()
    action.result = result
    action.error_code = None
    db.commit()
    return result


def _agent_action_matches_preview(
    action: AgentPendingAction,
    shop_id: int,
    supplied_preview_hash: str,
) -> bool:
    calculated_hash = _action_hash(action.id, shop_id, action.preview, action.payload)
    return bool(
        supplied_preview_hash
        and hmac.compare_digest(action.preview_hash, supplied_preview_hash)
        and hmac.compare_digest(action.preview_hash, calculated_hash)
    )


def _find_agent_payment(db: Session, shop_id: int, action: AgentPendingAction):
    return (
        db.query(Payment, Invoice)
        .join(Invoice, Invoice.id == Payment.invoice_id)
        .filter(
            Payment.idempotency_key == action.payload.get("idempotency_key"),
            Invoice.user_id == shop_id,
            Invoice.id == int(action.payload["invoice_id"]),
        )
        .first()
    )


def confirm_khata_payment_action(
    db: Session,
    *,
    shop_id: int,
    action_id: str,
    supplied_preview_hash: str,
) -> dict:
    from khata_router import PaymentRecordRequest, record_khata_payment

    action = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.action_type == "KHATA_PAYMENT",
    ).with_for_update().first()
    if not action:
        raise HTTPException(status_code=404, detail="Payment preview not found.")
    if not _agent_action_matches_preview(action, shop_id, supplied_preview_hash):
        raise HTTPException(status_code=409, detail="The payment preview changed. Prepare and review it again.")

    existing = _find_agent_payment(db, shop_id, action)
    if action.status == "COMPLETED":
        if existing:
            return {**(action.result or {}), "duplicate_confirmation": True}
        raise HTTPException(status_code=503, detail="The previous payment entry needs manual verification.")
    now = _utcnow()
    if action.status == "EXECUTING":
        if existing:
            payment, invoice = existing
            result = {
                "success": True,
                "verified": True,
                "payment_id": int(payment.id),
                "invoice_id": int(invoice.id),
                "invoice_number": str(invoice.invoice_number),
                "payment_amount": float(payment.amount),
                "outstanding_after": float(
                    max(Decimal("0"), Decimal(str(invoice.total_amount or 0)) - Decimal(str(invoice.paid_amount or 0)))
                ),
                "message": "The owner-confirmed payment entry is present in the database.",
            }
            return _complete_action(db, action, result)
        if action.started_at and action.started_at > now - timedelta(minutes=2):
            raise HTTPException(status_code=409, detail="This payment is already being processed. Check the invoice before retrying.")
        action.status = "PENDING"
        action.started_at = None
        action.updated_at = now
        db.commit()
        action = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).with_for_update().first()

    if action.status == "EXPIRED":
        raise HTTPException(
            status_code=410,
            detail=expired_preview_detail(action_id, "payment"),
        )
    if action.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This payment preview cannot be confirmed in state {action.status}.")
    if action.expires_at <= now:
        action.status = "EXPIRED"
        action.updated_at = now
        db.commit()
        raise HTTPException(
            status_code=410,
            detail=expired_preview_detail(action_id, "payment"),
        )

    payload = action.payload
    invoice = db.query(Invoice).filter(
        Invoice.id == int(payload["invoice_id"]),
        Invoice.user_id == shop_id,
        Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]),
    ).with_for_update().first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice is no longer available in this shop.")
    outstanding = max(Decimal("0.00"), Decimal(str(invoice.total_amount or 0)) - Decimal(str(invoice.paid_amount or 0)))
    payment_amount = Decimal(str(payload["amount"]))
    if payment_amount <= 0 or payment_amount > outstanding:
        raise HTTPException(status_code=409, detail="The invoice balance changed. Prepare a new payment preview.")

    action.status = "EXECUTING"
    action.started_at = now
    action.updated_at = now
    db.commit()
    try:
        data = PaymentRecordRequest(
            invoice_id=int(payload["invoice_id"]),
            amount=float(payment_amount),
            payment_method=str(payload["payment_method"]),
            notes=str(payload["notes"]),
            idempotency_key=str(payload["idempotency_key"]),
        )
        record_khata_payment(data, user_id=shop_id, db=db)
    except HTTPException:
        db.rollback()
        fresh = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).first()
        if fresh:
            prior_payment = _find_agent_payment(db, shop_id, fresh)
            if prior_payment:
                payment, refreshed_invoice = prior_payment
                result = {
                    "success": True,
                    "verified": True,
                    "payment_id": int(payment.id),
                    "invoice_id": int(refreshed_invoice.id),
                    "invoice_number": str(refreshed_invoice.invoice_number),
                    "payment_amount": float(payment.amount),
                    "message": "The payment entry is present in the database.",
                }
                return _complete_action(db, fresh, result)
            fresh.status = "FAILED"
            fresh.error_code = "KHATA_PAYMENT_REJECTED"
            fresh.updated_at = _utcnow()
            db.commit()
        raise
    except Exception as exc:
        db.rollback()
        import logging
        logging.getLogger(__name__).exception("Agent Khata payment failed for action %s", action_id)
        fresh = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).first()
        if fresh:
            prior_payment = _find_agent_payment(db, shop_id, fresh)
            if prior_payment:
                payment, refreshed_invoice = prior_payment
                result = {
                    "success": True,
                    "verified": True,
                    "payment_id": int(payment.id),
                    "invoice_id": int(refreshed_invoice.id),
                    "invoice_number": str(refreshed_invoice.invoice_number),
                    "payment_amount": float(payment.amount),
                    "message": "The payment entry is present in the database.",
                }
                return _complete_action(db, fresh, result)
            fresh.status = "FAILED"
            fresh.error_code = "KHATA_PAYMENT_FAILED"
            fresh.updated_at = _utcnow()
            db.commit()
        raise HTTPException(status_code=503, detail="The payment entry could not be verified. Check the invoice before retrying.") from exc

    db.expire_all()
    fresh = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
    ).with_for_update().first()
    saved = _find_agent_payment(db, shop_id, fresh) if fresh else None
    if not saved:
        if fresh:
            fresh.status = "NEEDS_REVIEW"
            fresh.error_code = "PAYMENT_POST_WRITE_VERIFICATION_FAILED"
            fresh.updated_at = _utcnow()
            db.commit()
        raise HTTPException(status_code=503, detail="The payment was submitted but its database record could not be verified.")
    payment, refreshed_invoice = saved
    if Decimal(str(payment.amount)).quantize(Decimal("0.01")) != payment_amount.quantize(Decimal("0.01")):
        raise HTTPException(status_code=503, detail="The saved payment amount differs from the confirmed preview.")
    result = {
        "success": True,
        "verified": True,
        "payment_id": int(payment.id),
        "invoice_id": int(refreshed_invoice.id),
        "invoice_number": str(refreshed_invoice.invoice_number),
        "payment_amount": float(payment.amount),
        "outstanding_after": float(
            max(Decimal("0"), Decimal(str(refreshed_invoice.total_amount or 0)) - Decimal(str(refreshed_invoice.paid_amount or 0)))
        ),
        "payment_status": str(getattr(refreshed_invoice.payment_status, "value", refreshed_invoice.payment_status)),
        "message": "The owner-confirmed payment was recorded and verified.",
    }
    return _complete_action(db, fresh, result)


def _order_transition_result(db: Session, shop_id: int, action: AgentPendingAction) -> dict | None:
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == int(action.payload["order_id"]),
        OnlineOrder.shop_id == shop_id,
    ).first()
    if not order:
        return None
    current = str(getattr(order.order_status, "value", order.order_status) or "").upper()
    target = str(action.payload["expected_status"]).upper()
    later_states = {
        "ACCEPTED": {"ACCEPTED", "DISPATCHED", "DELIVERED"},
        "DISPATCHED": {"DISPATCHED", "DELIVERED"},
        "REJECTED": {"REJECTED"},
    }
    if current not in later_states.get(target, {target}):
        return None
    return {
        "success": True,
        "verified": True,
        "order_id": int(order.id),
        "action": str(action.payload["action"]),
        "order_status": current,
        "total_amount": float(order.total_amount or 0),
        "message": f"Order #{order.id} transition was persisted. Current state: {current}.",
    }


def confirm_order_transition_action(
    db: Session,
    *,
    shop_id: int,
    current_user: dict,
    action_id: str,
    supplied_preview_hash: str,
) -> dict:
    from online_store import update_order_status

    action = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.action_type == "ORDER_TRANSITION",
    ).with_for_update().first()
    if not action:
        raise HTTPException(status_code=404, detail="Order transition preview not found.")
    if not _agent_action_matches_preview(action, shop_id, supplied_preview_hash):
        raise HTTPException(status_code=409, detail="The order preview changed. Prepare and review it again.")

    if action.status == "COMPLETED":
        verified = _order_transition_result(db, shop_id, action)
        if verified:
            return {**(action.result or verified), "duplicate_confirmation": True}
        raise HTTPException(status_code=503, detail="The previous order transition needs manual verification.")

    now = _utcnow()
    if action.status == "EXECUTING":
        verified = _order_transition_result(db, shop_id, action)
        if verified:
            return _complete_action(db, action, verified)
        if action.started_at and action.started_at > now - timedelta(minutes=2):
            raise HTTPException(status_code=409, detail="This order is already being processed. Refresh the order screen before retrying.")
        action.status = "PENDING"
        action.started_at = None
        action.updated_at = now
        db.commit()
        action = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).with_for_update().first()

    if action.status == "EXPIRED":
        raise HTTPException(
            status_code=410,
            detail=expired_preview_detail(action_id, "order"),
        )
    if action.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This order preview cannot be confirmed in state {action.status}.")
    if action.expires_at <= now:
        action.status = "EXPIRED"
        action.updated_at = now
        db.commit()
        raise HTTPException(
            status_code=410,
            detail=expired_preview_detail(action_id, "order"),
        )

    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == int(action.payload["order_id"]),
        OnlineOrder.shop_id == shop_id,
    ).with_for_update().first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    current = str(getattr(order.order_status, "value", order.order_status) or "").upper()
    if current != action.payload["expected_current_status"]:
        raise HTTPException(status_code=409, detail="The order status changed since the preview. Refresh and prepare a new action.")

    action.status = "EXECUTING"
    action.started_at = now
    action.updated_at = now
    db.commit()
    try:
        update_order_status(
            order_id=int(action.payload["order_id"]),
            action=str(action.payload["action"]),
            data=None,
            db=db,
            current_user=current_user,
        )
    except HTTPException:
        db.rollback()
        fresh = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).first()
        verified = _order_transition_result(db, shop_id, fresh) if fresh else None
        if fresh and verified:
            return _complete_action(db, fresh, verified)
        if fresh:
            fresh.status = "FAILED"
            fresh.error_code = "ORDER_TRANSITION_REJECTED"
            fresh.updated_at = _utcnow()
            db.commit()
        raise
    except Exception as exc:
        db.rollback()
        import logging
        logging.getLogger(__name__).exception("Agent order transition failed for action %s", action_id)
        fresh = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).first()
        verified = _order_transition_result(db, shop_id, fresh) if fresh else None
        if fresh and verified:
            return _complete_action(db, fresh, verified)
        if fresh:
            fresh.status = "FAILED"
            fresh.error_code = "ORDER_TRANSITION_FAILED"
            fresh.updated_at = _utcnow()
            db.commit()
        raise HTTPException(status_code=503, detail="The order transition could not be verified. Refresh the order screen before retrying.") from exc

    db.expire_all()
    fresh = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
    ).with_for_update().first()
    verified = _order_transition_result(db, shop_id, fresh) if fresh else None
    if not fresh or not verified:
        if fresh:
            fresh.status = "NEEDS_REVIEW"
            fresh.error_code = "ORDER_POST_WRITE_VERIFICATION_FAILED"
            fresh.updated_at = _utcnow()
            db.commit()
        raise HTTPException(status_code=503, detail="Order status was submitted but could not be verified.")
    return _complete_action(db, fresh, verified)


def confirm_invoice_action(
    db: Session,
    *,
    shop_id: int,
    current_user: dict,
    action_id: str,
    supplied_preview_hash: str,
) -> dict:
    from invoices_billing import (
        InvoiceLineItemCreate,
        InvoiceSyncCreate,
        create_invoice,
    )

    action = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.action_type == "CREATE_INVOICE",
    ).with_for_update().first()
    if not action:
        raise HTTPException(status_code=404, detail="Bill preview not found.")

    calculated_hash = _action_hash(action.id, shop_id, action.preview, action.payload)
    if (
        not supplied_preview_hash
        or not hmac.compare_digest(action.preview_hash, supplied_preview_hash)
        or not hmac.compare_digest(action.preview_hash, calculated_hash)
    ):
        raise HTTPException(status_code=409, detail="The bill preview changed. Prepare and review it again.")

    if action.status == "COMPLETED":
        verified = _invoice_verification(db, shop_id=shop_id, action=action)
        if verified:
            return {**verified, "duplicate_confirmation": True}
        raise HTTPException(status_code=503, detail="The previous bill needs manual verification. No duplicate invoice was created.")

    now = _utcnow()
    if action.status == "EXECUTING":
        existing = _invoice_verification(db, shop_id=shop_id, action=action)
        if existing:
            return _complete_action(db, action, existing)
        if action.started_at and action.started_at > now - timedelta(minutes=2):
            raise HTTPException(status_code=409, detail="This bill is already being processed. Check the invoice list before retrying.")
        # A previous process may have crashed before the invoice commit. The
        # deterministic per-action invoice number makes a retry idempotent.
        action.status = "PENDING"
        action.started_at = None
        action.updated_at = now
        db.commit()
        action = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).with_for_update().first()

    if action.status == "EXPIRED":
        raise HTTPException(
            status_code=410,
            detail=expired_preview_detail(action_id, "bill"),
        )
    if action.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This preview cannot be confirmed in state {action.status}.")

    if action.expires_at <= now:
        action.status = "EXPIRED"
        action.updated_at = now
        db.commit()
        raise HTTPException(
            status_code=410,
            detail=expired_preview_detail(action_id, "bill"),
        )

    # A client may retry after the invoice committed but before the action status
    # was updated. Reconcile by the action's unique invoice number first.
    existing = _invoice_verification(db, shop_id=shop_id, action=action)
    if existing:
        return _complete_action(db, action, existing)

    action.status = "EXECUTING"
    action.started_at = now
    action.updated_at = now
    db.commit()

    payload = action.payload
    line_items = [
        InvoiceLineItemCreate(
            product_id=line.get("product_id"),
            product_name=str(line["product_name"]),
            stock_tracked=bool(line.get("stock_tracked", True)),
            quantity=Decimal(str(line["quantity"])),
            unit_price=Decimal(str(line["unit_price"])),
            discount_amount=Decimal(str(line.get("discount_amount") or "0")),
            discount_reason=line.get("discount_reason"),
            discount_source=line.get("discount_source"),
        )
        for line in (payload.get("line_items") or [])
    ]
    data = InvoiceSyncCreate(
        invoice_number=str(payload["invoice_number"]),
        customer_phone=payload.get("customer_phone"),
        customer_name=payload.get("customer_name"),
        total_amount=float(payload["total_amount"]),
        paid_amount=float(payload.get("paid_amount") or 0),
        tax=float(payload.get("tax") or 0),
        payment_status="UNPAID",
        payment_method="CASH",
        line_items=line_items,
        invoice_date=str(payload["invoice_date"]),
        due_date=str(payload["due_date"]),
        notes=str(payload.get("notes") or ""),
    )

    try:
        # Reuse the production invoice route's validation, discount, stock,
        # transaction, durable-sync and realtime logic. Never write stock here.
        create_invoice(data, db=db, current_user=current_user)
    except HTTPException as exc:
        db.rollback()
        fresh = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).first()
        found = _invoice_verification(db, shop_id=shop_id, action=fresh) if fresh else None
        if found and fresh:
            return _complete_action(db, fresh, found)
        if fresh:
            fresh.status = "FAILED"
            fresh.error_code = f"INVOICE_ROUTE_{exc.status_code}"
            fresh.updated_at = _utcnow()
            db.commit()
        raise
    except Exception as exc:
        db.rollback()
        import logging
        logging.getLogger(__name__).exception(
            "AI bill confirmation failed for action_id=%s (%s)",
            action_id,
            type(exc).__name__,
        )
        fresh = db.query(AgentPendingAction).filter(
            AgentPendingAction.id == action_id,
            AgentPendingAction.user_id == shop_id,
        ).first()
        found = _invoice_verification(db, shop_id=shop_id, action=fresh) if fresh else None
        if found and fresh:
            return _complete_action(db, fresh, found)
        if fresh:
            fresh.status = "FAILED"
            fresh.error_code = "INVOICE_EXECUTION_FAILED"
            fresh.updated_at = _utcnow()
            db.commit()
        raise HTTPException(status_code=503, detail="The bill could not be verified. Check the invoice list before trying again.") from exc

    db.expire_all()
    fresh = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
    ).with_for_update().first()
    verified = _invoice_verification(db, shop_id=shop_id, action=fresh) if fresh else None
    if not verified or not fresh:
        if fresh:
            fresh.status = "NEEDS_REVIEW"
            fresh.error_code = "POST_WRITE_VERIFICATION_FAILED"
            fresh.updated_at = _utcnow()
            db.commit()
        raise HTTPException(status_code=503, detail="The invoice was submitted but its records could not be fully verified. Contact support before retrying.")
    return _complete_action(db, fresh, verified)


def confirm_agent_action(
    db: Session,
    *,
    shop_id: int,
    current_user: dict,
    action_id: str,
    supplied_preview_hash: str,
) -> dict:
    action_type = db.query(AgentPendingAction.action_type).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
    ).scalar()
    if action_type == "CREATE_INVOICE":
        return confirm_invoice_action(
            db, shop_id=shop_id, current_user=current_user,
            action_id=action_id, supplied_preview_hash=supplied_preview_hash,
        )
    if action_type == "KHATA_PAYMENT":
        return confirm_khata_payment_action(
            db, shop_id=shop_id, action_id=action_id,
            supplied_preview_hash=supplied_preview_hash,
        )
    if action_type == "KHATA_LEDGER_MOVEMENT":
        from .khata_actions import confirm_khata_ledger_movement
        return confirm_khata_ledger_movement(
            db,
            shop_id=shop_id,
            action_id=action_id,
            supplied_preview_hash=supplied_preview_hash,
        )
    if action_type == "ATTENDANCE_RECORD":
        from .attendance_actions import confirm_attendance_record
        return confirm_attendance_record(
            db,
            shop_id=shop_id,
            action_id=action_id,
            supplied_preview_hash=supplied_preview_hash,
        )
    if action_type == "INVENTORY_STOCK_MOVEMENT":
        from .inventory_actions import confirm_inventory_stock_movement
        return confirm_inventory_stock_movement(
            db,
            shop_id=shop_id,
            action_id=action_id,
            supplied_preview_hash=supplied_preview_hash,
        )
    if action_type == "ORDER_TRANSITION":
        return confirm_order_transition_action(
            db, shop_id=shop_id, current_user=current_user,
            action_id=action_id, supplied_preview_hash=supplied_preview_hash,
        )
    raise HTTPException(status_code=409, detail="This action type is not available for confirmation.")


