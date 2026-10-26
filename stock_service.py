from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Product, StockMovement, Notification


def _stable_stock_key(
    *,
    user_id: int,
    product_id: int,
    movement_type: str,
    idempotency_key: Optional[str],
    reference_id: Optional[str],
) -> Optional[str]:
    """Return a tenant-scoped replay key when the caller supplies stable identity.

    Explicit request keys are preferred. Legacy callers that already attach a
    business reference get a deterministic per-product/per-direction key. The
    quantity is intentionally excluded so a changed-quantity retry is rejected
    as a conflict instead of applying another movement.
    """
    supplied = (idempotency_key or "").strip()
    reference = (reference_id or "").strip()
    identity = f"request:{supplied}" if supplied else (f"reference:{reference}" if reference else "")
    if not identity:
        return None
    digest = hashlib.sha256(
        f"{user_id}|{identity}|{product_id}|{movement_type}".encode("utf-8")
    ).hexdigest()
    return f"stock_{digest}"


def _movement_matches(
    movement: StockMovement,
    *,
    product_id: int,
    quantity: Decimal,
    movement_type: str,
    reason: Optional[str],
    reference_id: Optional[str],
) -> bool:
    existing_type = getattr(movement.movement_type, "value", movement.movement_type)
    try:
        existing_quantity = Decimal(str(movement.quantity or 0))
    except (TypeError, ValueError):
        return False
    return (
        int(movement.product_id) == int(product_id)
        and str(existing_type).upper() == movement_type
        and existing_quantity == quantity
        and (movement.reason or None) == (reason or None)
        and (movement.reference_id or None) == (reference_id or None)
    )


class StockService:
    """Centralized stock mutation logic for inventory safety and auditability."""

    @staticmethod
    def apply_stock_change(
        db: Session,
        *,
        product_id: int,
        user_id: int,
        quantity,
        movement_type: str,
        reason: Optional[str] = None,
        reference_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        allow_negative: bool = False,
    ) -> tuple[Product, StockMovement]:
        product = (
            db.query(Product)
            .filter(Product.id == product_id, Product.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        normalized_type = (movement_type or "IN").upper()
        if normalized_type not in {"IN", "OUT", "ADJUSTMENT"}:
            raise HTTPException(status_code=400, detail="Invalid movement_type")

        try:
            normalized_quantity = Decimal(str(quantity))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid quantity")
        if not normalized_quantity.is_finite() or normalized_quantity < 0:
            raise HTTPException(status_code=400, detail="Quantity must be finite and non-negative")

        stable_key = _stable_stock_key(
            user_id=user_id,
            product_id=product_id,
            movement_type=normalized_type,
            idempotency_key=idempotency_key,
            reference_id=reference_id,
        )
        if stable_key:
            existing = (
                db.query(StockMovement)
                .filter(StockMovement.idempotency_key == stable_key)
                .first()
            )
            if existing is not None:
                if not _movement_matches(
                    existing,
                    product_id=product_id,
                    quantity=normalized_quantity,
                    movement_type=normalized_type,
                    reason=reason,
                    reference_id=reference_id,
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="This stock operation key was already used with different movement details.",
                    )
                setattr(existing, "_idempotent_replay", True)
                return product, existing

        previous_stock = Decimal(str(product.current_stock or 0))
        if normalized_type == "IN":
            product.current_stock = previous_stock + normalized_quantity
        elif normalized_type == "OUT":
            if not allow_negative and previous_stock < normalized_quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock. Available: {previous_stock}, Requested: {normalized_quantity}",
                )
            product.current_stock = previous_stock - normalized_quantity
        else:
            product.current_stock = normalized_quantity

        movement = StockMovement(
            product_id=product.id,
            movement_type=normalized_type,
            quantity=normalized_quantity,
            reason=reason,
            reference_id=reference_id,
            idempotency_key=stable_key,
        )
        setattr(movement, "_idempotent_replay", False)
        db.add(movement)

        if product.current_stock <= Decimal(str(product.min_stock or 0)):
            db.add(
                Notification(
                    notification_type="LOW_STOCK",
                    channel="EMAIL",
                    recipient="admin@store.com",
                    message=(
                        f"Product {product.product_name} (SKU: {product.sku}) is below minimum stock level. "
                        f"Current: {product.current_stock}, Minimum: {product.min_stock}"
                    ),
                    status="PENDING",
                )
            )

        return product, movement
