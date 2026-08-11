"""
PRODUCTION FIXES - BACKEND IDEMPOTENCY & DUPLICATE PREVENTION
===============================================================

This module implements idempotency checking for all critical operations.
Prevents duplicate sales, invoices, and stock deductions.
"""

from functools import wraps
from datetime import datetime, timedelta
from typing import Any, Dict, Callable
import json
import hashlib
from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_
import os

# Use Redis if available, fall back to in-memory cache
try:
    import redis
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        decode_responses=True
    )
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    # In-memory cache fallback
    _memory_cache: Dict[str, Dict[str, Any]] = {}


class IdempotencyManager:
    """Manages idempotent operations to prevent duplicates"""
    
    CACHE_EXPIRY = 3600  # 1 hour
    
    @staticmethod
    def get_cache_key(idempotency_key: str, operation_type: str) -> str:
        """Generate cache key"""
        return f"idempotency:{operation_type}:{idempotency_key}"
    
    @staticmethod
    def set_cached_response(
        idempotency_key: str,
        operation_type: str,
        response: Dict[str, Any]
    ) -> None:
        """Cache response for idempotent replay"""
        cache_key = IdempotencyManager.get_cache_key(idempotency_key, operation_type)
        cached_data = {
            'response': response,
            'timestamp': datetime.utcnow().isoformat(),
            'ttl': IdempotencyManager.CACHE_EXPIRY
        }
        
        if REDIS_AVAILABLE:
            try:
                redis_client.setex(
                    cache_key,
                    IdempotencyManager.CACHE_EXPIRY,
                    json.dumps(cached_data)
                )
            except Exception as e:
                print(f"⚠️ Redis cache failed: {e}, falling back to memory")
                _memory_cache[cache_key] = cached_data
        else:
            _memory_cache[cache_key] = cached_data
    
    @staticmethod
    def get_cached_response(
        idempotency_key: str,
        operation_type: str
    ) -> Dict[str, Any] | None:
        """Retrieve cached response if exists"""
        cache_key = IdempotencyManager.get_cache_key(idempotency_key, operation_type)
        
        if REDIS_AVAILABLE:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    return json.loads(cached).get('response')
            except:
                pass
        
        # Check memory cache
        if cache_key in _memory_cache:
            return _memory_cache[cache_key].get('response')
        
        return None
    
    @staticmethod
    def clear_cache(idempotency_key: str, operation_type: str) -> None:
        """Clear cache after operation confirmed"""
        cache_key = IdempotencyManager.get_cache_key(idempotency_key, operation_type)
        
        if REDIS_AVAILABLE:
            try:
                redis_client.delete(cache_key)
            except:
                pass
        
        if cache_key in _memory_cache:
            del _memory_cache[cache_key]


def require_idempotency_key(operation_type: str):
    """
    Decorator to enforce idempotency on API endpoints
    Usage:
        @router.post("/api/invoices/sync")
        @require_idempotency_key("invoice_create")
        async def sync_invoice(payload: InvoiceCreate, db: Session):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(
            *args,
            idempotency_key: str = Header(None),
            **kwargs
        ):
            # 1. Check if idempotency key is provided
            if not idempotency_key:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "MISSING_IDEMPOTENCY_KEY",
                        "message": "Idempotency-Key header is required"
                    }
                )
            
            # 2. Check if request was already processed
            cached_response = IdempotencyManager.get_cached_response(
                idempotency_key,
                operation_type
            )
            
            if cached_response:
                print(f"✅ Returning cached response for idempotency key: {idempotency_key}")
                return {
                    **cached_response,
                    "status": "CACHED_RESPONSE",
                    "idempotency_key": idempotency_key
                }
            
            # 3. Execute the actual operation
            try:
                response = await func(*args, **kwargs)
                
                # 4. Cache the response
                IdempotencyManager.set_cached_response(
                    idempotency_key,
                    operation_type,
                    response
                )
                
                response['idempotency_key'] = idempotency_key
                return response
                
            except Exception as e:
                # Don't cache errors - allow retry
                raise
        
        return wrapper
    
    return decorator


class OfflineIdempotencyManager:
    """
    Manages offline_id based idempotency for invoice/sale operations
    offline_id format: "{timestamp}_{millisecond}_{random}"
    """
    
    @staticmethod
    def check_duplicate_offline_id(offline_id: str, db: Session) -> Dict[str, Any] | None:
        """
        Check if offline_id already exists in database
        If yes, return existing invoice to prevent duplicate creation
        """
        from models import Invoice
        
        try:
            existing_invoice = db.query(Invoice).filter(
                Invoice.offline_id == offline_id
            ).first()
            
            if existing_invoice:
                return {
                    "already_exists": True,
                    "invoice_id": existing_invoice.id,
                    "invoice_number": existing_invoice.invoice_number,
                    "created_at": existing_invoice.created_at.isoformat() if existing_invoice.created_at else None,
                    "message": f"Invoice already created with this offline_id"
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Error checking duplicate offline_id: {e}")
            return None
    
    @staticmethod
    def mark_invoice_synced(
        invoice_id: int,
        offline_id: str,
        db: Session
    ) -> bool:
        """Mark invoice as synced to prevent re-processing"""
        from models import Invoice
        
        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if invoice:
                invoice.sync_status = 'SYNCED'
                invoice.synced_at = datetime.utcnow()
                db.commit()
                return True
        except Exception as e:
            print(f"❌ Error marking invoice as synced: {e}")
        
        return False


# ============================================================================
# DATABASE MIGRATIONS FOR IDEMPOTENCY
# ============================================================================

IDEMPOTENCY_MIGRATION_SQL = """
-- Add offline_id column to invoices table for idempotency
ALTER TABLE invoices 
ADD COLUMN offline_id VARCHAR(100) DEFAULT NULL;

-- Add UNIQUE constraint on offline_id to prevent duplicates
ALTER TABLE invoices 
ADD CONSTRAINT unique_offline_id UNIQUE(offline_id);

-- Add index for faster lookups
CREATE INDEX idx_invoices_offline_id ON invoices(offline_id);

-- Add sync tracking
ALTER TABLE invoices 
ADD COLUMN sync_status VARCHAR(20) DEFAULT 'PENDING' 
  CHECK (sync_status IN ('PENDING', 'SYNCED', 'FAILED', 'CONFLICT'));

ALTER TABLE invoices 
ADD COLUMN synced_at TIMESTAMP DEFAULT NULL;

-- Track synced sales separately for additional redundancy
CREATE TABLE IF NOT EXISTS synced_sales (
    id SERIAL PRIMARY KEY,
    sale_id VARCHAR(100) UNIQUE NOT NULL,
    invoice_id INTEGER NOT NULL,
    offline_id VARCHAR(100),
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shop_id INTEGER,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id),
    FOREIGN KEY (shop_id) REFERENCES shops(id)
);

CREATE INDEX idx_synced_sales_sale_id ON synced_sales(sale_id);
CREATE INDEX idx_synced_sales_offline_id ON synced_sales(offline_id);

-- Track stock deduction operations for idempotency
CREATE TABLE IF NOT EXISTS stock_movements_log (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    quantity_change INTEGER NOT NULL,
    reference_id VARCHAR(100) UNIQUE NOT NULL,
    operation_type VARCHAR(20) NOT NULL,  -- SALE, ADJUSTMENT, RETURN
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX idx_stock_movements_reference ON stock_movements_log(reference_id);
"""


# ============================================================================
# EXAMPLE USAGE IN INVOICE ENDPOINT
# ============================================================================

"""
@router.post("/api/invoices/sync")
@require_idempotency_key("invoice_create")
async def sync_invoice_production_safe(
    payload: InvoiceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(None),
):
    '''
    Production-safe invoice creation with full idempotency protection
    
    Required Headers:
    - Authorization: Bearer {token}
    - Idempotency-Key: {unique_key}
    
    Payload must include:
    - offline_id: Unique identifier from mobile app
    - invoice_number: Client-generated invoice number
    - customer_name: Name or "Cash Customer"
    - total_amount, paid_amount
    - line_items: List of products
    '''
    
    print(f"📦 Processing invoice with offline_id: {payload.offline_id}")
    
    # 1. Check for duplicate offline_id
    existing = OfflineIdempotencyManager.check_duplicate_offline_id(
        payload.offline_id,
        db
    )
    
    if existing and existing.get('already_exists'):
        print(f"⚠️ Invoice already exists: {existing['invoice_number']}")
        return {
            "status": "DUPLICATE",
            "message": "Invoice already processed",
            "invoice_id": existing['invoice_id'],
            "invoice_number": existing['invoice_number'],
        }
    
    try:
        # 2. Validate all stock is available
        insufficient_items = []
        for item in payload.line_items:
            product = db.query(Product).filter(
                Product.id == item.product_id
            ).first()
            
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
            
            if product.current_stock < item.quantity:
                insufficient_items.append({
                    'product_id': item.product_id,
                    'product_name': product.name,
                    'requested': item.quantity,
                    'available': product.current_stock
                })
        
        if insufficient_items:
            return {
                "status": "INSUFFICIENT_STOCK",
                "message": "Not enough inventory for all items",
                "insufficient_items": insufficient_items
            }
        
        # 3. Create invoice (will fail with constraint violation if offline_id duplicate)
        invoice = Invoice(
            invoice_number=payload.invoice_number,
            offline_id=payload.offline_id,  # UNIQUE constraint protects
            customer_name=payload.customer_name or "Cash Customer",
            customer_phone=payload.customer_phone,
            total_amount=payload.total_amount,
            paid_amount=payload.paid_amount,
            tax_amount=payload.tax or 0.0,
            payment_status=_determine_payment_status(payload.paid_amount, payload.total_amount),
            invoice_date=datetime.utcnow(),
            shop_id=current_user.shop_id,
            created_at=datetime.utcnow(),
        )
        
        db.add(invoice)
        db.flush()  # Get the invoice ID without committing
        
        # 4. Deduct stock for each item (idempotent via reference_id)
        for item in payload.line_items:
            # Check if this stock movement already recorded
            existing_movement = db.query(StockMovementLog).filter(
                StockMovementLog.reference_id == f"{invoice.offline_id}_{item.product_id}"
            ).first()
            
            if not existing_movement:
                # Record stock movement
                stock_log = StockMovementLog(
                    product_id=item.product_id,
                    quantity_change=-item.quantity,
                    reference_id=f"{invoice.offline_id}_{item.product_id}",
                    operation_type="SALE",
                    created_at=datetime.utcnow()
                )
                db.add(stock_log)
                
                # Update product stock
                product = db.query(Product).filter(
                    Product.id == item.product_id
                ).first()
                product.current_stock -= item.quantity
        
        # 5. Create invoice line items
        for item in payload.line_items:
            line = InvoiceLineItem(
                invoice_id=invoice.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.quantity * item.unit_price
            )
            db.add(line)
        
        # 6. Commit all changes
        db.commit()
        
        # 7. Mark as synced
        OfflineIdempotencyManager.mark_invoice_synced(
            invoice.id,
            invoice.offline_id,
            db
        )
        
        print(f"✅ Invoice created successfully: {invoice.invoice_number}")
        
        return {
            "status": "SUCCESS",
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "offline_id": invoice.offline_id,
            "message": "Invoice created and stock deducted"
        }
        
    except IntegrityError as e:
        db.rollback()
        
        # Handle duplicate offline_id
        if "unique_offline_id" in str(e).lower():
            existing = db.query(Invoice).filter(
                Invoice.offline_id == payload.offline_id
            ).first()
            
            print(f"🔄 Duplicate offline_id, returning existing invoice")
            return {
                "status": "DUPLICATE",
                "message": "Invoice already processed",
                "invoice_id": existing.id if existing else None,
                "offline_id": payload.offline_id,
            }
        
        raise HTTPException(status_code=409, detail=f"Database conflict: {str(e)}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Invoice creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating invoice: {str(e)}")


def _determine_payment_status(paid_amount: float, total_amount: float) -> str:
    '''Helper to determine payment status'''
    if paid_amount >= total_amount - 0.5:
        return "PAID"
    elif paid_amount > 0:
        return "PARTIAL"
    else:
        return "UNPAID"
"""

print("✅ Idempotency module loaded - Production-safe duplicate prevention active")
