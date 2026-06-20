"""
Inventory Reconciliation Service
Detects and fixes inventory discrepancies between local cache and backend database.
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

router = APIRouter(prefix="/api/inventory-reconcile", tags=["inventory reconciliation"])
logger = logging.getLogger(__name__)


# ==================== PYDANTIC MODELS ====================

class ReconciliationReport(BaseModel):
    """Complete reconciliation report"""
    user_id: int
    timestamp: datetime
    total_products: int
    discrepancies_found: int
    fixes_applied: int
    discrepancies: List[Dict[str, Any]]
    backend_stock_summary: Dict[str, Any]


class StockCorrectionRequest(BaseModel):
    """Request to manually correct stock"""
    product_id: int
    correct_stock: int
    reason: str


# ==================== RECONCILIATION ENDPOINTS ====================

@router.post("/full-reconciliation", response_model=ReconciliationReport)
def full_inventory_reconciliation(
    local_inventory: List[Dict[str, Any]]=None,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Perform full inventory reconciliation between local cache and backend.
    Detects discrepancies and provides correction recommendations.
    """
    try:
        discrepancies = []
        fixes_applied = 0
        
        # Get all backend products
        backend_products = db.query(Product).filter(
            Product.user_id == user_id,
            Product.is_active == True
        ).all()
        
        backend_dict = {p.id: p for p in backend_products}
        
        # Check each local product against backend
        for local_item in local_inventory:
            product_id = local_item.get('id') or local_item.get('product_id')
            if not product_id:
                continue
            
            local_stock = local_item.get('current_stock', 0)
            
            if product_id not in backend_dict:
                # Product exists locally but not in backend
                discrepancies.append({
                    "product_id": product_id,
                    "product_name": local_item.get('product_name', 'Unknown'),
                    "issue": "ORPHAN_LOCAL_RECORD",
                    "local_stock": local_stock,
                    "backend_stock": None,
                    "action": "DELETE_LOCAL",
                    "severity": "MEDIUM"
                })
                continue
            
            backend_product = backend_dict[product_id]
            backend_stock = backend_product.current_stock
            
            if local_stock != backend_stock:
                # Stock mismatch detected
                difference = backend_stock - local_stock
                severity = "HIGH" if abs(difference) > 10 else "MEDIUM"
                
                discrepancies.append({
                    "product_id": product_id,
                    "product_name": backend_product.product_name,
                    "issue": "STOCK_MISMATCH",
                    "local_stock": local_stock,
                    "backend_stock": backend_stock,
                    "difference": difference,
                    "action": "USE_BACKEND_VALUE",
                    "severity": severity,
                    "last_movement": _get_last_movement_info(db, product_id)
                })
                fixes_applied += 1
        
        # Check for products in backend but missing from local
        backend_ids = set(backend_dict.keys())
        local_ids = set()
        for local_item in local_inventory:
            pid = local_item.get('id') or local_item.get('product_id')
            if pid:
                local_ids.add(int(pid))
        
        missing_local = backend_ids - local_ids
        for pid in missing_local:
            backend_product = backend_dict[pid]
            discrepancies.append({
                "product_id": pid,
                "product_name": backend_product.product_name,
                "issue": "MISSING_LOCAL_RECORD",
                "local_stock": None,
                "backend_stock": backend_product.current_stock,
                "action": "ADD_TO_LOCAL",
                "severity": "LOW"
            })
        
        # Calculate backend stock summary
        total_backend_stock = sum(p.current_stock for p in backend_products)
        total_backend_value = sum(float(p.current_stock * p.unit_price) for p in backend_products)
        
        return ReconciliationReport(
            user_id=user_id,
            timestamp=datetime.utcnow(),
            total_products=len(backend_products),
            discrepancies_found=len(discrepancies),
            fixes_applied=fixes_applied,
            discrepancies=discrepancies,
            backend_stock_summary={
                "total_products": len(backend_products),
                "total_stock_units": total_backend_stock,
                "total_stock_value": total_backend_value,
                "low_stock_count": sum(1 for p in backend_products if p.current_stock <= p.min_stock),
                "out_of_stock_count": sum(1 for p in backend_products if p.current_stock == 0)
            }
        )
        
    except Exception as e:
        logger.error(f"Full reconciliation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")


@router.post("/correct-stock")
def correct_stock_manually(
    correction: StockCorrectionRequest,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually correct stock for a product.
    Creates a stock movement record for audit trail.
    """
    try:
        product = db.query(Product).filter(
            Product.id == correction.product_id,
            Product.user_id == user_id
        ).first()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        previous_stock = product.current_stock
        difference = correction.correct_stock - previous_stock
        
        # Update stock
        product.current_stock = correction.correct_stock
        
        # Create stock movement record
        movement = StockMovement(
            product_id=correction.product_id,
            movement_type="ADJUSTMENT",
            quantity=abs(difference),
            reason=f"MANUAL_CORRECTION: {correction.reason}",
            reference_id=f"RECONCILIATION_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        db.add(movement)
        
        db.commit()
        db.refresh(product)
        
        logger.info(f"Stock corrected: Product {correction.product_id}, {previous_stock} -> {correction.correct_stock}")
        
        return {
            "success": True,
            "product_id": correction.product_id,
            "previous_stock": previous_stock,
            "new_stock": correction.correct_stock,
            "difference": difference,
            "reason": correction.reason,
            "timestamp": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Stock correction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Correction failed: {str(e)}")


@router.get("/audit-trail/{product_id}")
def get_stock_audit_trail(
    product_id: int,
    days: int = 30,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete audit trail for a product's stock movements.
    """
    try:
        product = db.query(Product).filter(
            Product.id == product_id,
            Product.user_id == user_id
        ).first()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        movements = db.query(StockMovement).filter(
            and_(
                StockMovement.product_id == product_id,
                StockMovement.created_at >= cutoff_date
            )
        ).order_by(desc(StockMovement.created_at)).all()
        
        return {
            "product_id": product_id,
            "product_name": product.product_name,
            "current_stock": product.current_stock,
            "audit_period_days": days,
            "total_movements": len(movements),
            "movements": [
                {
                    "id": m.id,
                    "type": m.movement_type,
                    "quantity": m.quantity,
                    "reason": m.reason,
                    "reference_id": m.reference_id,
                    "timestamp": m.created_at
                }
                for m in movements
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audit trail retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Audit retrieval failed: {str(e)}")


@router.post("/auto-fix-discrepancies")
def auto_fix_discrepancies(
    local_inventory: List[Dict[str, Any]],
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Automatically fix detected discrepancies by updating local cache with backend values.
    This endpoint returns the corrected inventory data that should replace local cache.
    """
    try:
        # Get all backend products (source of truth)
        backend_products = db.query(Product).filter(
            Product.user_id == user_id,
            Product.is_active == True
        ).all()
        
        corrected_inventory = []
        fixes_count = 0
        
        for product in backend_products:
            corrected_inventory.append({
                "id": product.id,
                "product_id": product.id,
                "product_name": product.product_name,
                "sku": product.sku,
                "current_stock": product.current_stock,  # Backend value
                "stock": product.current_stock,  # For compatibility
                "min_stock": product.min_stock,
                "max_stock": product.max_stock,
                "unit_price": float(product.unit_price),
                "category": product.category,
                "_corrected": True
            })
            fixes_count += 1
        
        return {
            "success": True,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "total_products_corrected": fixes_count,
            "corrected_inventory": corrected_inventory,
            "message": "Local cache should be replaced with this data"
        }
        
    except Exception as e:
        logger.error(f"Auto-fix failed: {e}")
        raise HTTPException(status_code=500, detail=f"Auto-fix failed: {str(e)}")


# ==================== HELPER FUNCTIONS ====================

def _get_last_movement_info(db: Session, product_id: int) -> Optional[Dict[str, Any]]:
    """Get information about the last stock movement for a product"""
    try:
        last_movement = db.query(StockMovement).filter(
            StockMovement.product_id == product_id
        ).order_by(desc(StockMovement.created_at)).first()
        
        if last_movement:
            return {
                "type": last_movement.movement_type,
                "quantity": last_movement.quantity,
                "reason": last_movement.reason,
                "reference_id": last_movement.reference_id,
                "timestamp": last_movement.created_at
            }
        return None
    except Exception:
        return None
