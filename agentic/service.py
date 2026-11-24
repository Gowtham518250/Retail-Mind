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
    StockMovement,
    StockMovementType,
)

from .graph import SYSTEM_PROMPT, invoke_agent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _action_hash(action_id: str, shop_id: int, preview: dict, payload: dict) -> str:
    material = {"action_id": action_id, "shop_id": int(shop_id), "preview": preview, "payload": payload}
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def _message_history(db: Session, conversation_id: str, shop_id: int) -> list[dict[str, str]]:
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
    return [{"role": row.role, "content": row.content[:6000]} for row in rows]


async def run_chat_turn(
    db: Session,
    *,
    shop_id: int,
    message: str,
    conversation_id: str | None = None,
    language_code: str = "auto",
) -> dict:
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
        db.flush()

    history = _message_history(db, conversation_id, shop_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    messages.append({"role": "user", "content": clean_message})

    request_id = str(uuid.uuid4())
    context = {
        "db": db,
        "shop_id": int(shop_id),
        "conversation_id": conversation_id,
        "request_id": request_id,
        "user_text": clean_message,
        "language_code": str(language_code or "auto")[:16],
    }

    result = await invoke_agent(messages, context)
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
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
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
                "created_at": row.created_at.isoformat() if row.created_at else None,
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
        if recorded_quantity < expected_quantity:
            return None

    expected_total = Decimal(str(action.payload["total_amount"])).quantize(Decimal("0.01"))
    actual_total = Decimal(str(invoice.total_amount or 0)).quantize(Decimal("0.01"))
    if actual_total != expected_total:
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

    if action.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This preview cannot be confirmed in state {action.status}.")

    if action.expires_at <= now:
        action.status = "EXPIRED"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=410, detail="The bill preview expired. Prepare a new bill for confirmation.")

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
