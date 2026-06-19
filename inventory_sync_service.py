"""
Inventory Sync Service - Single Source of Truth Implementation
Makes PostgreSQL backend the ONLY authority for inventory data.
Frontend can cache but never modify stock without backend confirmation.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from db import get_db
from models import Product, StockMovement, Invoice, InvoiceLineItem
from security import get_current_user as check_current_user

router = APIRouter(prefix="/api/inventory-sync", tags=["inventory sync"])
logger = logging.getLogger(__name__)


# ==================== PYDANTIC MODELS ====================

class StockDeductionRequest(BaseModel):
    """Request to deduct stock with idempotency"""
    product_id: int
    quantity: int = Field(..., gt=0)
    reason: str = "SALE"
    reference_id: str  # invoice_number or sale_id
    idempotency_key: str  # Prevent duplicate deductions


class StockDeductionResponse(BaseModel):
    """Response with updated stock and sync status"""
    success: bool
    product_id: int
    previous_stock: int
    new_stock: int
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

@router.post("/deduct-stock", response_model=StockDeductionResponse)
def deduct_stock_with_idempotency(
    request: StockDeductionRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Deduct stock with idempotency protection.
    This is the SINGLE SOURCE OF TRUTH for stock deduction.
    Frontend MUST call this for every stock change.
    """
    try:
        # Check idempotency - prevent duplicate deductions
        existing_movement = db.query(StockMovement).filter(
            and_(
                StockMovement.product_id == request.product_id,
                StockMovement.reference_id == request.reference_id,
                StockMovement.movement_type == "OUT",
                StockMovement.reason == request.reason
            )
        ).first()
        
        if existing_movement:
            # Already processed - return current state
            product = db.query(Product).filter(
                Product.id == request.product_id,
                Product.user_id == user_id
            ).first()
            
            return StockDeductionResponse(
                success=True,
                product_id=request.product_id,
                previous_stock=product.current_stock + request.quantity,
                new_stock=product.current_stock,
                message="Already processed (idempotent)",
                sync_timestamp=existing_movement.created_at
            )
        
        # Get product
        product = db.query(Product).filter(
            Product.id == request.product_id,
            Product.user_id == user_id
        ).first()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        previous_stock = product.current_stock
        
        # Check sufficient stock
        if product.current_stock < request.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient stock. Available: {product.current_stock}, Requested: {request.quantity}"
            )
        
        # Deduct stock
        product.current_stock -= request.quantity
        
        # Create stock movement record
        movement = StockMovement(
            product_id=request.product_id,
            movement_type="OUT",
            quantity=request.quantity,
            reason=request.reason,
            reference_id=request.reference_id
        )
        db.add(movement)
        
        # Check for low stock alert
        if product.current_stock <= product.min_stock:
            background_tasks.add_task(
                _trigger_low_stock_alert,
                product_id=product.id,
                product_name=product.product_name,
                current_stock=product.current_stock,
                min_stock=product.min_stock,
                user_id=user_id
            )
        
        db.commit()
        db.refresh(product)
        
        logger.info(f"Stock deducted: Product {product.id}, Qty: {request.quantity}, New Stock: {product.current_stock}")
        
        return StockDeductionResponse(
            success=True,
            product_id=request.product_id,
            previous_stock=previous_stock,
            new_stock=product.current_stock,
            message="Stock deducted successfully",
            sync_timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Stock deduction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stock deduction failed: {str(e)}")


@router.post("/deduct-stock-batch")
def deduct_stock_batch(
    request: BatchStockUpdateRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Batch stock deduction for multiple products in a single transaction.
    Used for invoice sync with multiple line items.
    """
    try:
        results = []
        failed_items = []
        
        for item in request.updates:
            try:
                # Process each item
                existing_movement = db.query(StockMovement).filter(
                    and_(
                        StockMovement.product_id == item.product_id,
                        StockMovement.reference_id == item.reference_id,
                        StockMovement.movement_type == "OUT",
                        StockMovement.reason == item.reason
                    )
                ).first()
                
                if existing_movement:
                    product = db.query(Product).filter(
                        Product.id == item.product_id,
                        Product.user_id == user_id
                    ).first()
                    
                    results.append({
                        "product_id": item.product_id,
                        "success": True,
                        "message": "Already processed (idempotent)",
                        "new_stock": product.current_stock
                    })
                    continue
                
                product = db.query(Product).filter(
                    Product.id == item.product_id,
                    Product.user_id == user_id
                ).first()
                
                if not product:
                    failed_items.append({
                        "product_id": item.product_id,
                        "error": "Product not found"
                    })
                    continue
                
                if product.current_stock < item.quantity:
                    failed_items.append({
                        "product_id": item.product_id,
                        "error": f"Insufficient stock: {product.current_stock} < {item.quantity}"
                    })
                    continue
                
                previous_stock = product.current_stock
                product.current_stock -= item.quantity
                
                movement = StockMovement(
                    product_id=item.product_id,
                    movement_type="OUT",
                    quantity=item.quantity,
                    reason=item.reason,
                    reference_id=item.reference_id
                )
                db.add(movement)
                
                results.append({
                    "product_id": item.product_id,
                    "success": True,
                    "previous_stock": previous_stock,
                    "new_stock": product.current_stock,
                    "message": "Stock deducted"
                })
                
            except Exception as e:
                failed_items.append({
                    "product_id": item.product_id,
                    "error": str(e)
                })
        
        db.commit()
        
        return {
            "success": len(failed_items) == 0,
            "total_items": len(request.updates),
            "successful": len(results),
            "failed": len(failed_items),
            "results": results,
            "failed_items": failed_items
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Batch stock deduction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch deduction failed: {str(e)}")


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
                    "product_name": p.product_name,
                    "sku": p.sku,
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
