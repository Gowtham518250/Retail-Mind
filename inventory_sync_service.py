"""
Inventory Sync Service - Single Source of Truth Implementation
Makes PostgreSQL backend the ONLY authority for inventory data.
Frontend can cache but never modify stock without backend confirmation.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, func, desc
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import logging

from db import get_db
from realtime import publish_realtime_event
from durable_sync import append_sync_event
from models import Product, StockMovement, Invoice, InvoiceLineItem
from security import get_current_user as check_current_user
from audit_logging import AuditAction, AuditService

router = APIRouter(prefix="/api/inventory-sync", tags=["inventory sync"])
logger = logging.getLogger(__name__)


# ==================== PYDANTIC MODELS ====================

class StockDeductionRequest(BaseModel):
    """Request to deduct stock with idempotency."""
    product_id: int
    quantity: Decimal = Field(..., gt=0, max_digits=12, decimal_places=3)
    reason: str = Field(default="SALE", min_length=1, max_length=200)
    reference_id: str = Field(..., min_length=1, max_length=100)
    idempotency_key: str = Field(..., min_length=1, max_length=128)


class StockDeductionResponse(BaseModel):
    """Response with updated stock and sync status"""
    success: bool
    product_id: int
    previous_stock: Decimal
    new_stock: Decimal
    message: str
    sync_timestamp: datetime


class BatchStockUpdateRequest(BaseModel):
    """Batch stock update for multiple products"""
    updates: List[StockDeductionRequest]


class InventoryReconciliationRequest(BaseModel):
    """Request to reconcile inventory between local cache and backend"""
    local_inventory: List[Dict[str, Any]]


class InventoryReconciliationResponse(BaseModel):
    """Reconciliation results"""
    reconciled: bool
    discrepancies_found: int
    fixes_applied: int
    details: List[Dict[str, Any]]


# ==================== INVENTORY SYNC ENDPOINTS ====================

def _stock_movement_matches_request(existing_movement, request: StockDeductionRequest) -> bool:
    """Return whether a persisted stock movement represents this exact request."""
    try:
        existing_quantity = Decimal(str(existing_movement.quantity)).quantize(Decimal("0.001"))
        requested_quantity = Decimal(str(request.quantity)).quantize(Decimal("0.001"))
    except Exception:
        return False

    return (
        int(existing_movement.product_id) == int(request.product_id)
        and str(existing_movement.reference_id or "").strip() == str(request.reference_id or "").strip()
        and str(existing_movement.reason or "").strip().casefold() == str(request.reason or "").strip().casefold()
        and existing_quantity == requested_quantity
        and str(getattr(existing_movement.movement_type, "value", existing_movement.movement_type)).upper() == "OUT"
    )


def _duplicate_stock_response(product, existing_movement) -> StockDeductionResponse:
    # The original before-stock level cannot be reconstructed from current stock
    # alone after later movements; do not fabricate it by adding this request's
    # quantity. The duplicate response reports the current canonical balance.
    current_stock = product.current_stock
    return StockDeductionResponse(
        success=True,
        product_id=product.id,
        previous_stock=current_stock,
        new_stock=current_stock,
        message="Already processed (idempotent)",
        sync_timestamp=existing_movement.created_at or datetime.utcnow(),
    )


@router.post("/deduct-stock", response_model=StockDeductionResponse)
def deduct_stock_with_idempotency(
    request: StockDeductionRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    """Deduct stock once, using a durable idempotency key and legacy replay guard."""
    product = (
        db.query(Product)
        .filter(Product.id == request.product_id, Product.user_id == user_id)
        .with_for_update()
        .first()
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    request.idempotency_key = request.idempotency_key.strip()
    request.reference_id = request.reference_id.strip()
    request.reason = request.reason.strip().upper()
    if not request.idempotency_key or not request.reference_id or not request.reason:
        raise HTTPException(status_code=422, detail="idempotency_key, reference_id and reason are required")

    try:
        # The key is authoritative. A reused key with a changed payload is a
        # conflict, never a successful no-op.
        existing_by_key = (
            db.query(StockMovement)
            .filter(StockMovement.idempotency_key == request.idempotency_key)
            .first()
        )
        if existing_by_key is not None:
            if not _stock_movement_matches_request(existing_by_key, request):
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency key was already used for a different stock movement.",
                )
            return _duplicate_stock_response(product, existing_by_key)

        # Backward compatibility for stock movements created before this column
        # existed or by old clients that did not persist a request key.
        existing_legacy = (
            db.query(StockMovement)
            .filter(
                StockMovement.product_id == product.id,
                StockMovement.reference_id == request.reference_id,
                StockMovement.movement_type == "OUT",
                func.upper(StockMovement.reason) == request.reason,
            )
            .first()
        )
        if existing_legacy is not None:
            if not _stock_movement_matches_request(existing_legacy, request):
                raise HTTPException(
                    status_code=409,
                    detail="A stock movement already exists for this reference with different quantity or details.",
                )
            return _duplicate_stock_response(product, existing_legacy)

        previous_stock = product.current_stock
        if previous_stock < request.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock. Available: {previous_stock}, Requested: {request.quantity}",
            )

        product.current_stock -= request.quantity
        movement = StockMovement(
            product_id=product.id,
            movement_type="OUT",
            quantity=request.quantity,
            reason=request.reason,
            reference_id=request.reference_id,
            idempotency_key=request.idempotency_key,
        )
        db.add(movement)

        sync_event = append_sync_event(db, {
            "event_id": str(uuid4()),
            "type": "inventory.changed",
            "shop_id": user_id,
            "product_id": product.id,
            "reference_id": request.reference_id,
            "reason": request.reason,
            "quantity": float(request.quantity),
            "new_stock": float(product.current_stock),
        })
        db.commit()
        db.refresh(product)
        db.refresh(movement)

        try:
            AuditService.log_action(
                db=db,
                user_id=user_id,
                action=AuditAction.UPDATE,
                table_name="products",
                record_id=product.id,
                old_values={"current_stock": float(previous_stock)},
                new_values={
                    "current_stock": float(product.current_stock),
                    "quantity": float(request.quantity),
                    "reason": request.reason,
                    "reference_id": request.reference_id,
                    "idempotency_key": request.idempotency_key,
                },
                description=f"Inventory stock deducted for product {product.id}",
            )
        except Exception as audit_error:
            logger.warning("Inventory audit logging failed after commit: %s", audit_error)

        if product.current_stock <= product.min_stock:
            background_tasks.add_task(
                _trigger_low_stock_alert,
                product_id=product.id,
                product_name=product.product_name,
                current_stock=product.current_stock,
                min_stock=product.min_stock,
                user_id=user_id,
            )

        publish_realtime_event(sync_event)
        logger.info(
            "Stock deducted for product_id=%s reference_id=%s quantity=%s",
            product.id, request.reference_id, request.quantity,
        )
        return StockDeductionResponse(
            success=True,
            product_id=product.id,
            previous_stock=previous_stock,
            new_stock=product.current_stock,
            message="Stock deducted successfully",
            sync_timestamp=movement.created_at or datetime.utcnow(),
        )
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        # A concurrent retry may have committed the same request first.
        existing = (
            db.query(StockMovement)
            .filter(StockMovement.idempotency_key == request.idempotency_key)
            .first()
        )
        current_product = (
            db.query(Product)
            .filter(Product.id == request.product_id, Product.user_id == user_id)
            .first()
        )
        if existing is not None and current_product is not None:
            if _stock_movement_matches_request(existing, request):
                return _duplicate_stock_response(current_product, existing)
        raise HTTPException(status_code=409, detail="Conflicting stock movement; refresh inventory and retry.")
    except Exception:
        db.rollback()
        logger.exception(
            "Stock deduction failed for product_id=%s reference_id=%s",
            request.product_id, request.reference_id,
        )
        raise HTTPException(status_code=500, detail="Stock deduction failed. Please retry safely.")


@router.post("/deduct-stock-batch")
def deduct_stock_batch(
    request: BatchStockUpdateRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    """Apply stock updates with the same durable idempotency rules as single writes."""
    results = []
    failed_items = []
    inventory_changes = []
    low_stock_alerts = []
    seen_keys = {}

    try:
        for item in request.updates:
            # Pydantic has already validated bounds. Normalize inputs so old and
            # new clients use the same canonical comparison values.
            item.idempotency_key = item.idempotency_key.strip()
            item.reference_id = item.reference_id.strip()
            item.reason = item.reason.strip().upper()
            if not item.idempotency_key or not item.reference_id or not item.reason:
                failed_items.append({
                    "product_id": item.product_id,
                    "error": "idempotency_key, reference_id and reason are required",
                })
                continue

            # Reject key collisions within a single request before any mutation.
            fingerprint = (
                item.product_id,
                item.reference_id,
                item.reason.casefold(),
                str(Decimal(str(item.quantity)).quantize(Decimal("0.001"))),
            )
            previous_fingerprint = seen_keys.get(item.idempotency_key)
            if previous_fingerprint is not None and previous_fingerprint != fingerprint:
                failed_items.append({
                    "product_id": item.product_id,
                    "error": "Idempotency key is reused for different items in this batch.",
                })
                continue
            seen_keys[item.idempotency_key] = fingerprint

            product = (
                db.query(Product)
                .filter(Product.id == item.product_id, Product.user_id == user_id)
                .with_for_update()
                .first()
            )
            if product is None:
                failed_items.append({
                    "product_id": item.product_id,
                    "error": "Product not found",
                })
                continue

            existing_by_key = (
                db.query(StockMovement)
                .filter(StockMovement.idempotency_key == item.idempotency_key)
                .first()
            )
            if existing_by_key is not None:
                if not _stock_movement_matches_request(existing_by_key, item):
                    failed_items.append({
                        "product_id": item.product_id,
                        "error": "Idempotency key was already used for a different stock movement.",
                    })
                    continue
                results.append({
                    "product_id": item.product_id,
                    "success": True,
                    "message": "Already processed (idempotent)",
                    "new_stock": product.current_stock,
                    "duplicate": True,
                })
                continue

            # Compatibility with movements written before idempotency keys
            # were added. Conflicting replay payloads must not appear successful.
            existing_legacy = (
                db.query(StockMovement)
                .filter(
                    StockMovement.product_id == item.product_id,
                    StockMovement.reference_id == item.reference_id,
                    StockMovement.movement_type == "OUT",
                    func.upper(StockMovement.reason) == item.reason,
                )
                .first()
            )
            if existing_legacy is not None:
                if not _stock_movement_matches_request(existing_legacy, item):
                    failed_items.append({
                        "product_id": item.product_id,
                        "error": "A stock movement already exists for this reference with different quantity or details.",
                    })
                    continue
                results.append({
                    "product_id": item.product_id,
                    "success": True,
                    "message": "Already processed (legacy idempotent match)",
                    "new_stock": product.current_stock,
                    "duplicate": True,
                })
                continue

            if product.current_stock < item.quantity:
                failed_items.append({
                    "product_id": item.product_id,
                    "error": f"Insufficient stock: {product.current_stock} < {item.quantity}",
                })
                continue

            previous_stock = product.current_stock
            product.current_stock -= item.quantity
            movement = StockMovement(
                product_id=item.product_id,
                movement_type="OUT",
                quantity=item.quantity,
                reason=item.reason,
                reference_id=item.reference_id,
                idempotency_key=item.idempotency_key,
            )
            db.add(movement)

            results.append({
                "product_id": item.product_id,
                "success": True,
                "previous_stock": previous_stock,
                "new_stock": product.current_stock,
                "message": "Stock deducted",
                "duplicate": False,
            })
            change = {
                "product_id": item.product_id,
                "reference_id": item.reference_id,
                "reason": item.reason,
                "quantity": float(item.quantity),
                "new_stock": float(product.current_stock),
                "idempotency_key": item.idempotency_key,
            }
            inventory_changes.append(change)

            if product.current_stock <= product.min_stock:
                low_stock_alerts.append({
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "current_stock": product.current_stock,
                    "min_stock": product.min_stock,
                })

        sync_event = None
        if inventory_changes:
            sync_event = append_sync_event(db, {
                "event_id": str(uuid4()),
                "type": "inventory.changed",
                "shop_id": user_id,
                "changes": inventory_changes,
            })

        # Stock values, movement records and durable event commit together.
        db.commit()

        for change in inventory_changes:
            try:
                AuditService.log_action(
                    db=db,
                    user_id=user_id,
                    action=AuditAction.UPDATE,
                    table_name="products",
                    record_id=int(change["product_id"]),
                    new_values=change,
                    description=f"Batch inventory deduction for product {change['product_id']}",
                )
            except Exception as audit_error:
                logger.warning(
                    "Batch inventory audit logging failed for product_id=%s (%s)",
                    change.get("product_id"),
                    type(audit_error).__name__,
                )

        for alert in low_stock_alerts:
            background_tasks.add_task(
                _trigger_low_stock_alert,
                product_id=alert["product_id"],
                product_name=alert["product_name"],
                current_stock=alert["current_stock"],
                min_stock=alert["min_stock"],
                user_id=user_id,
            )

        if sync_event is not None:
            publish_realtime_event(sync_event)

        return {
            "success": len(failed_items) == 0,
            "total_items": len(request.updates),
            "successful": sum(1 for result in results if result["success"]),
            "failed": len(failed_items),
            "results": results,
            "failed_items": failed_items,
        }
    except IntegrityError:
        db.rollback()
        logger.warning("Batch stock write hit an idempotency constraint for shop_id=%s", user_id)
        raise HTTPException(
            status_code=409,
            detail="A concurrent stock update conflicted. Refresh inventory and retry the batch.",
        )
    except Exception as exc:
        db.rollback()
        logger.error(
            "Batch stock deduction failed for shop_id=%s (%s)",
            user_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="Batch stock deduction failed. Please retry safely.",
        )


@router.post("/reconcile", response_model=InventoryReconciliationResponse)
def reconcile_inventory(
    request: InventoryReconciliationRequest,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Reconcile local inventory cache with backend database.
    Detects discrepancies and provides correct values from backend.
    """
    try:
        discrepancies = []
        fixes_applied = 0
        
        for local_item in request.local_inventory:
            product_id = local_item.get('id') or local_item.get('product_id')
            if not product_id:
                continue
            
            # Get backend truth
            backend_product = db.query(Product).filter(
                Product.id == product_id,
                Product.user_id == user_id
            ).first()
            
            if not backend_product:
                discrepancies.append({
                    "product_id": product_id,
                    "product_name": local_item.get('product_name', 'Unknown'),
                    "issue": "Product not found in backend",
                    "local_stock": local_item.get('current_stock', 0),
                    "backend_stock": None,
                    "action": "DELETE_LOCAL"
                })
                continue
            
            local_stock = local_item.get('current_stock', 0)
            backend_stock = backend_product.current_stock
            
            if local_stock != backend_stock:
                discrepancies.append({
                    "product_id": product_id,
                    "product_name": backend_product.product_name,
                    "issue": "Stock mismatch",
                    "local_stock": local_stock,
                    "backend_stock": backend_stock,
                    "difference": backend_stock - local_stock,
                    "action": "USE_BACKEND_VALUE"
                })
                fixes_applied += 1
        
        return InventoryReconciliationResponse(
            reconciled=True,
            discrepancies_found=len(discrepancies),
            fixes_applied=fixes_applied,
            details=discrepancies
        )
        
    except Exception as e:
        logger.error(f"Inventory reconciliation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")


@router.get("/current-stock/{product_id}")
def get_current_stock(
    product_id: int,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current stock from backend (single source of truth).
    Frontend should call this to refresh cache after any operation.
    """
    try:
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.user_id == user_id
        ).first()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get recent stock movements
        recent_movements = db.query(StockMovement).filter(
            StockMovement.product_id == product_id
        ).order_by(desc(StockMovement.created_at)).limit(10).all()
        
        return {
            "product_id": product.id,
            "product_name": product.product_name,
            "current_stock": product.current_stock,
            "min_stock": product.min_stock,
            "max_stock": product.max_stock,
            "last_updated": datetime.utcnow(),
            "recent_movements": [
                {
                    "type": m.movement_type,
                    "quantity": m.quantity,
                    "reason": m.reason,
                    "reference_id": m.reference_id,
                    "timestamp": m.created_at
                }
                for m in recent_movements
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current stock: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stock: {str(e)}")


@router.get("/all-stock")
def get_all_stock(
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all products with current stock from backend.
    Frontend should call this to refresh entire inventory cache.
    """
    try:
        products = db.query(Product).filter(
            Product.user_id == user_id,
            Product.is_active == True
        ).all()
        
        return {
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "total_products": len(products),
            "products": [
                {
                    "id": p.id,
                    "product_id": p.id,
                    "product_name": p.product_name,
                    # The frontend historically called this field "barcode".
                    # SKU is the canonical product barcode in the inventory model,
                    # so expose both names to keep clients consistent.
                    "sku": p.sku,
                    "barcode": p.sku,
                    "current_stock": p.current_stock,
                    "min_stock": p.min_stock,
                    "max_stock": p.max_stock,
                    "unit_price": float(p.unit_price),
                    "category": p.category
                }
                for p in products
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get all stock: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get inventory: {str(e)}")


# ==================== HELPER FUNCTIONS ====================

def _trigger_low_stock_alert(
    product_id: int,
    product_name: str,
    current_stock: int,
    min_stock: int,
    user_id: int
):
    """Background task to trigger low stock alert"""
    try:
        # Here you would implement email/SMS notification logic
        logger.warning(f"Low stock alert: {product_name} (ID: {product_id}) - Stock: {current_stock}, Min: {min_stock}")
        # TODO: Integrate with notification service
    except Exception as e:
        logger.error(f"Failed to trigger low stock alert: {e}")