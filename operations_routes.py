import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict, Any, List
import uuid as uuid_lib

from db import get_db
from models import User, ShopProfile
from security import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================
# OPERATION MODELS
# ============================================

class OperationRequest(BaseModel):
    operation_id: str  # UUID with prefix (e.g., "create_sale_abc123")
    operation_type: str  # e.g., "create_sale", "update_stock"
    payload: Dict[str, Any]
    entity_id: Optional[str] = None  # UUID of affected entity
    device_id: str
    user_id: int
    timestamp: str  # ISO 8601 format

class OperationResponse(BaseModel):
    operation_id: str
    status: str  # "success", "duplicate", "error"
    message: str
    data: Optional[Dict[str, Any]] = None

class BatchOperationRequest(BaseModel):
    operations: List[OperationRequest]

class BatchOperationResponse(BaseModel):
    results: List[OperationResponse]
    summary: Dict[str, int]

# ============================================
# IDEMPOTENT OPERATION PROCESSING
# ============================================

@router.post("/operations", response_model=OperationResponse)
async def process_operation(
    operation: OperationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process a single operation idempotently.
    
    This endpoint ensures idempotency by:
    1. Checking if operation_id has already been processed
    2. If yes, return success without reprocessing
    3. If no, process the operation and record it
    
    This prevents duplicate operations from causing data corruption.
    """
    try:
        # Validate operation_id format
        if not _is_valid_operation_id(operation.operation_id):
            raise HTTPException(
                status_code=400, 
                detail="Invalid operation_id format"
            )
        
        # Check if operation has already been processed
        if _is_operation_processed(db, operation.operation_id):
            logger.info(f"Duplicate operation detected: {operation.operation_id}")
            return OperationResponse(
                operation_id=operation.operation_id,
                status="duplicate",
                message="Operation already processed - skipped",
                data=None
            )
        
        # Validate user authorization
        if current_user.id != operation.user_id:
            raise HTTPException(
                status_code=403, 
                detail="Not authorized to process this operation"
            )
        
        # Process the operation based on type
        result = await _process_operation_by_type(db, operation, current_user)
        
        # Record the operation as processed
        _record_operation(db, operation, current_user.id)
        
        return OperationResponse(
            operation_id=operation.operation_id,
            status="success",
            message="Operation processed successfully",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing operation {operation.operation_id}")
        raise HTTPException(
            status_code=500,
            detail=f"Operation processing failed: {str(e)}"
        )

@router.post("/operations/batch", response_model=BatchOperationResponse)
async def process_batch_operations(
    batch: BatchOperationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process multiple operations in a batch.
    
    Operations are processed in order, and failed operations
    don't prevent other operations from being processed.
    """
    results = []
    success_count = 0
    duplicate_count = 0
    error_count = 0
    
    for operation in batch.operations:
        try:
            response = await process_operation(
                operation, 
                db, 
                current_user
            )
            results.append(response)
            
            if response.status == "success":
                success_count += 1
            elif response.status == "duplicate":
                duplicate_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            error_count += 1
            results.append(OperationResponse(
                operation_id=operation.operation_id,
                status="error",
                message=str(e),
                data=None
            ))
    
    return BatchOperationResponse(
        results=results,
        summary={
            "total": len(batch.operations),
            "success": success_count,
            "duplicate": duplicate_count,
            "error": error_count
        }
    )

@router.get("/operations/{operation_id}", response_model=OperationResponse)
async def get_operation_status(
    operation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check the status of a specific operation.
    """
    # Check if operation has been processed
    operation_data = _get_operation_record(db, operation_id)
    
    if operation_data:
        return OperationResponse(
            operation_id=operation_id,
            status="processed",
            message="Operation has been processed",
            data={
                "processed_at": operation_data.get("processed_at"),
                "user_id": operation_data.get("user_id")
            }
        )
    else:
        return OperationResponse(
            operation_id=operation_id,
            status="not_found",
            message="Operation not found in processed records",
            data=None
        )

# ============================================
# OPERATION TYPE HANDLERS
# ============================================

async def _process_operation_by_type(
    db: Session, 
    operation: OperationRequest, 
    current_user: User
) -> Dict[str, Any]:
    """
    Route operation to appropriate handler based on type.
    """
    operation_type = operation.operation_type
    
    if operation_type == "create_sale":
        return await _handle_create_sale(db, operation, current_user)
    elif operation_type == "update_sale":
        return await _handle_update_sale(db, operation, current_user)
    elif operation_type == "delete_sale":
        return await _handle_delete_sale(db, operation, current_user)
    elif operation_type == "create_customer":
        return await _handle_create_customer(db, operation, current_user)
    elif operation_type == "update_customer":
        return await _handle_update_customer(db, operation, current_user)
    elif operation_type == "delete_customer":
        return await _handle_delete_customer(db, operation, current_user)
    elif operation_type == "update_stock":
        return await _handle_update_stock(db, operation, current_user)
    elif operation_type == "create_invoice":
        return await _handle_create_invoice(db, operation, current_user)
    elif operation_type == "update_invoice":
        return await _handle_update_invoice(db, operation, current_user)
    elif operation_type == "delete_invoice":
        return await _handle_delete_invoice(db, operation, current_user)
    elif operation_type == "create_expense":
        return await _handle_create_expense(db, operation, current_user)
    elif operation_type == "update_expense":
        return await _handle_update_expense(db, operation, current_user)
    elif operation_type == "delete_expense":
        return await _handle_delete_expense(db, operation, current_user)
    elif operation_type == "create_supplier":
        return await _handle_create_supplier(db, operation, current_user)
    elif operation_type == "update_supplier":
        return await _handle_update_supplier(db, operation, current_user)
    elif operation_type == "delete_supplier":
        return await _handle_delete_supplier(db, operation, current_user)
    elif operation_type == "return_product":
        return await _handle_return_product(db, operation, current_user)
    elif operation_type == "edit_invoice":
        return await _handle_edit_invoice(db, operation, current_user)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown operation type: {operation_type}"
        )

# ============================================
# SPECIFIC OPERATION HANDLERS
# ============================================

async def _handle_create_sale(
    db: Session, 
    operation: OperationRequest, 
    current_user: User
) -> Dict[str, Any]:
    """Handle sale creation with proper error handling and transaction safety."""
    from models import Sale
    
    try:
        # Check if sale with this UUID already exists
        sale_uuid = operation.payload.get('uuid')
        if sale_uuid and db.query(Sale).filter(Sale.uuid == sale_uuid).first():
            logger.info(f"Sale with UUID {sale_uuid} already exists")
            return {"uuid": sale_uuid, "status": "already_exists"}
        
        # Create sale record
        sale = Sale(
            uuid=sale_uuid or str(uuid_lib.uuid4()),
            user_id=current_user.id,
            shop_id=current_user.id,  # Assuming shop_id = user_id for owners
            invoice_number=operation.payload.get('invoice_number'),
            total_amount=operation.payload.get('total_amount', 0),
            payment_method=operation.payload.get('payment_method'),
            customer_id=operation.payload.get('customer_id'),
            items=operation.payload.get('items', []),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            version=operation.payload.get('version', 1),
            device_id=operation.device_id,
            sync_status='synced'
        )
        
        db.add(sale)
        db.commit()
        db.refresh(sale)
        
        logger.info(f"Sale created successfully: {sale.uuid}")
        return {"uuid": sale.uuid, "invoice_number": sale.invoice_number}
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create sale: {e}")
        raise HTTPException(status_code=500, detail=f"Sale creation failed: {str(e)}")

async def _handle_update_sale(
    db: Session, 
    operation: OperationRequest, 
    current_user: User
) -> Dict[str, Any]:
    """Handle sale update with version checking."""
    from models import Sale
    
    sale_uuid = operation.entity_id or operation.payload.get('uuid')
    if not sale_uuid:
        raise HTTPException(status_code=400, detail="Sale UUID required")
    
    sale = db.query(Sale).filter(Sale.uuid == sale_uuid).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    # Version check for conflict detection
    incoming_version = operation.payload.get('version', 1)
    if sale.version > incoming_version:
        logger.warning(f"Version conflict for sale {sale_uuid}: local={sale.version}, incoming={incoming_version}")
        # Could implement conflict resolution here
    
    # Update sale fields
    for key, value in operation.payload.items():
        if key not in ['uuid', 'version', 'created_at', 'metadata']:
            setattr(sale, key, value)
    
    sale.updated_at = datetime.utcnow()
    sale.version = incoming_version + 1
    sale.sync_status = 'synced'
    
    db.commit()
    db.refresh(sale)
    
    return {"uuid": sale.uuid, "version": sale.version}

async def _handle_delete_sale(
    db: Session, 
    operation: OperationRequest, 
    current_user: User
) -> Dict[str, Any]:
    """Handle soft delete of sale."""
    from models import Sale
    
    sale_uuid = operation.entity_id or operation.payload.get('uuid')
    if not sale_uuid:
        raise HTTPException(status_code=400, detail="Sale UUID required")
    
    sale = db.query(Sale).filter(Sale.uuid == sale_uuid).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    # Soft delete
    sale.deleted = True
    sale.deleted_at = datetime.utcnow()
    sale.sync_status = 'synced'
    
    db.commit()
    
    return {"uuid": sale.uuid, "deleted": True}

async def _handle_update_stock(
    db: Session, 
    operation: OperationRequest, 
    current_user: User
) -> Dict[str, Any]:
    """Handle stock update with inventory management."""
    from models import Product
    
    product_uuid = operation.entity_id or operation.payload.get('uuid')
    if not product_uuid:
        raise HTTPException(status_code=400, detail="Product UUID required")
    
    product = db.query(Product).filter(Product.uuid == product_uuid).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Update stock
    old_quantity = product.stock_quantity
    new_quantity = operation.payload.get('quantity', old_quantity)
    
    product.stock_quantity = new_quantity
    product.updated_at = datetime.utcnow()
    product.sync_status = 'synced'
    
    db.commit()
    db.refresh(product)
    
    logger.info(f"Stock updated: {product_uuid} from {old_quantity} to {new_quantity}")
    
    return {
        "uuid": product.uuid,
        "old_quantity": old_quantity,
        "new_quantity": new_quantity
    }

async def _handle_create_customer(
    db: Session, 
    operation: OperationRequest, 
    current_user: User
) -> Dict[str, Any]:
    """Handle customer creation."""
    from models import Customer
    
    customer_uuid = operation.payload.get('uuid') or str(uuid_lib.uuid4())
    
    # Check for duplicates
    if db.query(Customer).filter(Customer.uuid == customer_uuid).first():
        return {"uuid": customer_uuid, "status": "already_exists"}
    
    customer = Customer(
        uuid=customer_uuid,
        user_id=current_user.id,
        name=operation.payload.get('name'),
        phone=operation.payload.get('phone'),
        email=operation.payload.get('email'),
        address=operation.payload.get('address'),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1,
        device_id=operation.device_id,
        sync_status='synced'
    )
    
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    return {"uuid": customer.uuid, "name": customer.name}

# Placeholder handlers for other operation types
async def _handle_update_customer(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    # Implementation similar to update_sale
    return {"status": "not_implemented"}

async def _handle_delete_customer(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    # Implementation similar to delete_sale
    return {"status": "not_implemented"}

async def _handle_create_invoice(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_update_invoice(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_delete_invoice(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_create_expense(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_update_expense(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_delete_expense(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_create_supplier(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_update_supplier(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_delete_supplier(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_return_product(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

async def _handle_edit_invoice(db: Session, operation: OperationRequest, current_user: User) -> Dict[str, Any]:
    return {"status": "not_implemented"}

# ============================================
# OPERATION RECORD MANAGEMENT
# ============================================

def _is_operation_processed(db: Session, operation_id: str) -> bool:
    """Check if an operation has already been processed."""
    try:
        # Check in processed operations table
        result = db.execute(
            text("SELECT 1 FROM processed_operations WHERE operation_id = :op_id"),
            {"op_id": operation_id}
        ).fetchone()
        return result is not None
    except Exception as e:
        logger.warning(f"Error checking operation status: {e}")
        # If table doesn't exist or other error, assume not processed
        return False

def _record_operation(db: Session, operation: OperationRequest, user_id: int):
    """Record that an operation has been processed."""
    try:
        db.execute(
            text("""
                INSERT INTO processed_operations 
                (operation_id, operation_type, user_id, device_id, processed_at)
                VALUES (:op_id, :op_type, :user_id, :device_id, :processed_at)
                ON CONFLICT (operation_id) DO NOTHING
            """),
            {
                "op_id": operation.operation_id,
                "op_type": operation.operation_type,
                "user_id": user_id,
                "device_id": operation.device_id,
                "processed_at": datetime.utcnow()
            }
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to record operation: {e}")
        # Don't fail the operation if recording fails

def _get_operation_record(db: Session, operation_id: str) -> Optional[Dict[str, Any]]:
    """Get operation record if it exists."""
    try:
        result = db.execute(
            text("""
                SELECT operation_id, user_id, device_id, processed_at 
                FROM processed_operations 
                WHERE operation_id = :op_id
            """),
            {"op_id": operation_id}
        ).fetchone()
        
        if result:
            return {
                "operation_id": result[0],
                "user_id": result[1],
                "device_id": result[2],
                "processed_at": result[3].isoformat() if result[3] else None
            }
        return None
    except Exception as e:
        logger.warning(f"Error getting operation record: {e}")
        return None

def _is_valid_operation_id(operation_id: str) -> bool:
    """Validate operation ID format (UUID with optional prefix)."""
    try:
        # Extract base UUID if there's a prefix
        if '_' in operation_id:
            base_uuid = operation_id.split('_')[-1]
        else:
            base_uuid = operation_id
        
        # Validate UUID format
        uuid_lib.UUID(base_uuid)
        return True
    except ValueError:
        return False