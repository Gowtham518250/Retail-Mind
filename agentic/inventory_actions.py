"""Owner-confirmed inventory stock movements using the canonical stock service."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import AgentPendingAction, Product
from stock_service import StockService

_ACTION_TYPE = "INVENTORY_STOCK_MOVEMENT"
_MAX_QUANTITY = Decimal("100000000.000")


def _quantity(value: Any, *, allow_zero: bool) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Enter a valid stock quantity") from exc
    if not amount.is_finite():
        raise ValueError("Enter a valid stock quantity")
    amount = amount.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    if amount < 0 or (amount == 0 and not allow_zero) or amount > _MAX_QUANTITY:
        raise ValueError("Stock quantity is outside the supported range")
    return amount


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(action_id: str, shop_id: int, preview: dict, payload: dict) -> str:
    material = {
        "action_id": action_id,
        "shop_id": int(shop_id),
        "preview": preview,
        "payload": payload,
    }
    return hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()


def prepare_inventory_stock_movement(
    db: Session,
    *,
    shop_id: int,
    conversation_id: str,
    request_text: str,
    product_id: int,
    movement_type: str,
    quantity: Any,
    reason: str | None = None,
) -> dict:
    movement = str(movement_type or "").strip().upper()
    if movement not in {"IN", "OUT", "ADJUSTMENT"}:
        raise ValueError("Choose IN, OUT or ADJUSTMENT")
    if not conversation_id:
        raise ValueError("A saved conversation is required to prepare a stock movement")
    amount = _quantity(quantity, allow_zero=(movement == "ADJUSTMENT"))
    clean_reason = " ".join(str(reason or "").split())[:180]
    clean_reason = clean_reason or {
        "IN": "Agent-confirmed stock received",
        "OUT": "Agent-confirmed stock removed",
        "ADJUSTMENT": "Agent-confirmed stock count correction",
    }[movement]

    product = db.query(Product).filter(
        Product.id == int(product_id),
        Product.user_id == int(shop_id),
        Product.is_active.is_(True),
    ).first()
    if product is None:
        raise ValueError("The selected active product was not found in this shop")

    current = Decimal(str(product.current_stock or 0)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
    if movement == "OUT" and amount > current:
        raise ValueError(f"Cannot remove {amount} units; only {current} are available")
    resulting = current + amount if movement == "IN" else current - amount if movement == "OUT" else amount
    if resulting < 0 or resulting > _MAX_QUANTITY:
        raise ValueError("The resulting stock is outside the supported range")

    payload = {
        "product_id": int(product.id),
        "movement_type": movement,
        "quantity": str(amount),
        "reason": clean_reason,
        "expected_stock": str(current),
    }
    normalized_request = " ".join(str(request_text or "").split()).casefold()[:1000]
    key = hashlib.sha256(_canonical({
        "shop_id": int(shop_id),
        "conversation_id": conversation_id,
        "request_text": normalized_request,
        "payload": payload,
    }).encode("utf-8")).hexdigest()
    prior = db.query(AgentPendingAction).filter(
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.idempotency_key == key,
    ).first()
    if prior:
        if prior.status in {"PENDING", "EXECUTING", "COMPLETED"}:
            return {
                "success": True,
                "duplicate_request": True,
                "action_id": prior.id,
                "status": prior.status,
                "preview_hash": prior.preview_hash,
                "preview": prior.preview,
                "message": "This stock movement already has a confirmation action. No second preview was created.",
            }
        return {
            "success": False,
            "needs_clarification": True,
            "message": "This stock movement request expired or failed. Prepare it again.",
        }

    action_id = str(uuid.uuid4())
    preview = {
        "operation": "RESTOCK" if movement == "IN" else "STOCK_OUT" if movement == "OUT" else "STOCK_COUNT_ADJUSTMENT",
        "product_id": int(product.id),
        "product_name": str(product.product_name or "Product")[:120],
        "sku": str(product.sku or "")[:80],
        "movement_type": movement,
        "quantity": float(amount),
        "stock_before": float(current),
        "stock_after": float(resulting),
        "unit": str(getattr(product, "unit", "") or "units")[:20],
        "reason": clean_reason,
        "requires_owner_confirmation": True,
        "expires_in_seconds": 300,
        "warning": (
            "Stock changes only. This does not create a purchase invoice, supplier payable or sales invoice."
            if movement == "IN"
            else "This records stock leaving inventory; it does not create a refund or customer credit."
            if movement == "OUT"
            else "This sets the on-hand count to the target quantity shown. It does not create a sale or purchase."
        ),
    }
    digest = _digest(action_id, shop_id, preview, payload)
    db.add(AgentPendingAction(
        id=action_id,
        user_id=shop_id,
        conversation_id=conversation_id,
        action_type=_ACTION_TYPE,
        status="PENDING",
        idempotency_key=key,
        preview=preview,
        payload=payload,
        preview_hash=digest,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5),
    ))
    db.flush()
    return {
        "success": True,
        "action_id": action_id,
        "status": "PENDING",
        "preview_hash": digest,
        "preview": preview,
        "message": "Stock movement preview prepared. Inventory has not changed. Review and confirm this exact movement in Retail Mind.",
    }


def confirm_inventory_stock_movement(
    db: Session,
    *,
    shop_id: int,
    action_id: str,
    supplied_preview_hash: str,
) -> dict:
    action = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.action_type == _ACTION_TYPE,
    ).with_for_update().first()
    if action is None:
        raise HTTPException(status_code=404, detail="Stock movement preview not found.")
    expected_hash = _digest(action.id, shop_id, action.preview, action.payload)
    if (
        not supplied_preview_hash
        or not hmac.compare_digest(action.preview_hash, supplied_preview_hash)
        or not hmac.compare_digest(action.preview_hash, expected_hash)
    ):
        raise HTTPException(status_code=409, detail="The stock movement preview changed. Prepare it again.")
    if action.status == "COMPLETED":
        return {**(action.result or {}), "duplicate_confirmation": True}
    if action.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This stock movement cannot be confirmed in state {action.status}.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if action.expires_at <= now:
        action.status = "EXPIRED"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=410, detail="The stock movement preview expired. Prepare it again.")

    payload = action.payload
    product = db.query(Product).filter(
        Product.id == int(payload["product_id"]),
        Product.user_id == int(shop_id),
        Product.is_active.is_(True),
    ).with_for_update().first()
    if product is None:
        action.status = "FAILED"
        action.error_code = "PRODUCT_NOT_FOUND"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=404, detail="The product is no longer active in this shop.")

    current = Decimal(str(product.current_stock or 0)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
    expected = Decimal(str(payload["expected_stock"])).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
    if current != expected:
        action.status = "FAILED"
        action.error_code = "STOCK_CHANGED_AFTER_PREVIEW"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=409, detail="The product stock changed after preview. Refresh inventory and prepare a new movement.")

    amount = _quantity(payload["quantity"], allow_zero=(payload["movement_type"] == "ADJUSTMENT"))
    reference_id = f"AGENT-STOCK-{action.id}"
    try:
        updated_product, stock_movement = StockService.apply_stock_change(
            db,
            product_id=int(product.id),
            user_id=int(shop_id),
            quantity=amount,
            movement_type=str(payload["movement_type"]),
            reason=str(payload["reason"])[:180],
            reference_id=reference_id,
            allow_negative=False,
        )
        # This stable movement key is unique in stock_movements, so retries of
        # the same confirmed action cannot apply the change twice.
        stock_movement.idempotency_key = f"agent-stock-{action.id}"
        from inventory import _queue_inventory_change
        from realtime import publish_realtime_event

        sync_event = _queue_inventory_change(
            db,
            shop_id,
            "stock_movement",
            product_id=int(product.id),
            movement_type=str(payload["movement_type"]),
            quantity=float(amount),
            current_stock=float(updated_product.current_stock),
            reason=str(payload["reason"])[:180],
            reference_id=reference_id,
            idempotency_key=stock_movement.idempotency_key,
            agent_action_id=action.id,
        )
        result = {
            "success": True,
            "verified": True,
            "action_id": action.id,
            "product_id": int(product.id),
            "product_name": str(product.product_name or "Product"),
            "movement_type": str(payload["movement_type"]),
            "quantity": float(amount),
            "current_stock": float(updated_product.current_stock),
            "reference_id": reference_id,
            "message": "Inventory stock updated successfully.",
        }
        action.status = "COMPLETED"
        action.result = result
        action.completed_at = now
        action.updated_at = now
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="The stock movement could not be safely saved. Refresh inventory before retrying.") from exc

    persisted = db.query(Product).filter(
        Product.id == int(payload["product_id"]),
        Product.user_id == int(shop_id),
    ).first()
    if persisted is None or Decimal(str(persisted.current_stock)).quantize(Decimal("0.001")) != Decimal(str(result["current_stock"])).quantize(Decimal("0.001")):
        raise HTTPException(status_code=503, detail="The movement was saved but the resulting stock could not be verified. Refresh inventory.")
    try:
        publish_realtime_event(sync_event)
    except Exception:
        # The durable sync event was committed with the stock movement.
        pass
    return result
