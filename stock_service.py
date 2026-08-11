from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import Product, StockMovement, Notification


class StockService:
    """Centralized stock mutation logic for inventory safety and auditability."""

    @staticmethod
    def apply_stock_change(
        db: Session,
        *,
        product_id: int,
        user_id: int,
        quantity: int,
        movement_type: str,
        reason: Optional[str] = None,
        reference_id: Optional[str] = None,
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

        if quantity < 0:
            raise HTTPException(status_code=400, detail="Quantity must be non-negative")

        previous_stock = product.current_stock or 0
        if normalized_type == "IN":
            product.current_stock = previous_stock + quantity
        elif normalized_type == "OUT":
            if not allow_negative and previous_stock < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock. Available: {previous_stock}, Requested: {quantity}",
                )
            product.current_stock = previous_stock - quantity
        else:
            product.current_stock = quantity

        movement = StockMovement(
            product_id=product.id,
            movement_type=normalized_type,
            quantity=quantity,
            reason=reason,
            reference_id=reference_id,
        )
        db.add(movement)

        if product.current_stock <= product.min_stock:
            db.add(
                Notification(
                    notification_type="LOW_STOCK",
                    channel="EMAIL",
                    recipient=f"admin@store.com",
                    message=(
                        f"Product {product.product_name} (SKU: {product.sku}) is below minimum stock level. "
                        f"Current: {product.current_stock}, Minimum: {product.min_stock}"
                    ),
                    status="PENDING",
                )
            )

        return product, movement
