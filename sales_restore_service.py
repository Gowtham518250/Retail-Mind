"""
Sales Restore Service - Complete Sales Recovery After App Reinstall
Restores: invoices, invoice items, stock impact, customer history, payment status
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from db import get_db
from models import Invoice, InvoiceLineItem, Customer, Product, StockMovement
from security import get_current_user as check_current_user

router = APIRouter(prefix="/api/sales-restore", tags=["sales restoration"])
logger = logging.getLogger(__name__)


# ==================== PYDANTIC MODELS ====================

class SalesRestoreResponse(BaseModel):
    """Complete sales restoration response"""
    user_id: int
    timestamp: datetime
    total_invoices_restored: int
    total_line_items_restored: int
    customers_restored: int
    stock_impact_applied: bool
    invoices: List[Dict[str, Any]]
    summary: Dict[str, Any]


class SalesRestoreRequest(BaseModel):
    """Request to restore sales with optional date range"""
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None  # YYYY-MM-DD
    include_stock_impact: bool = True


# ==================== SALES RESTORATION ENDPOINTS ====================

@router.post("/restore-all", response_model=SalesRestoreResponse)
def restore_all_sales(
    request: SalesRestoreRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Restore complete sales history from backend.
    This is called after app reinstall to recover all data.
    """
    try:
        logger.info(f"Starting sales restoration for user {user_id}")
        
        # Build query with date filters
        query = db.query(Invoice).filter(Invoice.user_id == user_id)
        
        if request.start_date:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d").date()
            query = query.filter(Invoice.invoice_date >= start_date)
        
        if request.end_date:
            end_date = datetime.strptime(request.end_date, "%Y-%m-%d").date()
            query = query.filter(Invoice.invoice_date <= end_date)
        
        invoices = query.order_by(desc(Invoice.created_at)).all()
        
        restored_invoices = []
        total_line_items = 0
        customers_restored = set()
        
        for invoice in invoices:
            # Get line items
            line_items = db.query(InvoiceLineItem).filter(
                InvoiceLineItem.invoice_id == invoice.id
            ).all()
            
            # Build invoice data
            invoice_data = {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": invoice.customer_id,
                "customer_name": invoice.customer_name,
                "customer_phone": invoice.customer_phone,
                "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "subtotal": float(invoice.subtotal),
                "tax": float(invoice.tax),
                "total_amount": float(invoice.total_amount),
                "paid_amount": float(invoice.paid_amount),
                "status": invoice.status,
                "payment_status": invoice.payment_status,
                "payment_method": invoice.payment_method,
                "source": invoice.source,
                "notes": invoice.notes,
                "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
                "line_items": [
                    {
                        "id": item.id,
                        "product_id": item.product_id,
                        "description": item.description,
                        "quantity": item.quantity,
                        "unit_price": float(item.unit_price),
                        "line_total": float(item.line_total)
                    }
                    for item in line_items
                ]
            }
            
            restored_invoices.append(invoice_data)
            total_line_items += len(line_items)
            
            if invoice.customer_id:
                customers_restored.add(invoice.customer_id)
        
        # Apply stock impact if requested
        stock_impact_applied = False
        if request.include_stock_impact:
            stock_impact_applied = _apply_stock_impact_from_sales(
                db, user_id, invoices, background_tasks
            )
        
        # Calculate summary
        total_revenue = sum(float(inv['total_amount']) for inv in restored_invoices)
        total_paid = sum(float(inv['paid_amount']) for inv in restored_invoices)
        unpaid_count = sum(1 for inv in restored_invoices if inv['payment_status'] in ['UNPAID', 'PARTIAL'])
        
        summary = {
            "total_revenue": total_revenue,
            "total_paid": total_paid,
            "outstanding_amount": total_revenue - total_paid,
            "unpaid_invoices": unpaid_count,
            "paid_invoices": len(restored_invoices) - unpaid_count,
            "average_invoice_value": total_revenue / len(restored_invoices) if restored_invoices else 0,
            "date_range": {
                "start": request.start_date,
                "end": request.end_date,
                "actual_start": restored_invoices[-1]['invoice_date'] if restored_invoices else None,
                "actual_end": restored_invoices[0]['invoice_date'] if restored_invoices else None
            }
        }
        
        logger.info(f"Sales restoration complete: {len(restored_invoices)} invoices, {total_line_items} line items")
        
        return SalesRestoreResponse(
            user_id=user_id,
            timestamp=datetime.utcnow(),
            total_invoices_restored=len(restored_invoices),
            total_line_items_restored=total_line_items,
            customers_restored=len(customers_restored),
            stock_impact_applied=stock_impact_applied,
            invoices=restored_invoices,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Sales restoration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Restoration failed: {str(e)}")


@router.get("/restore-summary")
def get_restore_summary(
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Get summary of available sales data for restoration.
    """
    try:
        # Get invoice counts by status
        total_invoices = db.query(Invoice).filter(Invoice.user_id == user_id).count()
        
        paid_count = db.query(Invoice).filter(
            Invoice.user_id == user_id,
            Invoice.payment_status == "PAID"
        ).count()
        
        unpaid_count = db.query(Invoice).filter(
            Invoice.user_id == user_id,
            Invoice.payment_status == "UNPAID"
        ).count()
        
        partial_count = db.query(Invoice).filter(
            Invoice.user_id == user_id,
            Invoice.payment_status == "PARTIAL"
        ).count()
        
        # Get date range
        oldest_invoice = db.query(Invoice).filter(
            Invoice.user_id == user_id
        ).order_by(Invoice.created_at).first()
        
        newest_invoice = db.query(Invoice).filter(
            Invoice.user_id == user_id
        ).order_by(desc(Invoice.created_at)).first()
        
        # Get total revenue
        total_revenue = db.query(func.sum(Invoice.total_amount)).filter(
            Invoice.user_id == user_id
        ).scalar() or 0
        
        # Get customer count
        customer_count = db.query(Customer).filter(
            Customer.user_id == user_id
        ).count()
        
        return {
            "user_id": user_id,
            "available_for_restore": True,
            "invoice_summary": {
                "total_invoices": total_invoices,
                "paid": paid_count,
                "unpaid": unpaid_count,
                "partial": partial_count
            },
            "date_range": {
                "oldest_invoice": oldest_invoice.created_at.isoformat() if oldest_invoice else None,
                "newest_invoice": newest_invoice.created_at.isoformat() if newest_invoice else None
            },
            "financial_summary": {
                "total_revenue": float(total_revenue),
                "customer_count": customer_count
            },
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Restore summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"Summary failed: {str(e)}")


@router.post("/restore-customers")
def restore_customers(
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """
    Restore all customer data from backend.
    """
    try:
        customers = db.query(Customer).filter(
            Customer.user_id == user_id,
            Customer.is_active == True
        ).all()
        
        restored_customers = []
        for customer in customers:
            # Get customer's invoice count
            invoice_count = db.query(Invoice).filter(
                Invoice.customer_id == customer.id
            ).count()
            
            restored_customers.append({
                "id": customer.id,
                "customer_name": customer.customer_name,
                "email": customer.email,
                "phone": customer.phone,
                "whatsapp_number": customer.whatsapp_number,
                "address": customer.address,
                "city": customer.city,
                "credit_limit": float(customer.credit_limit) if customer.credit_limit else 0,
                "payment_terms": customer.payment_terms,
                "contact_preference": customer.contact_preference,
                "is_active": customer.is_active,
                "created_at": customer.created_at.isoformat() if customer.created_at else None,
                "invoice_count": invoice_count
            })
        
        logger.info(f"Customer restoration complete: {len(restored_customers)} customers")
        
        return {
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "total_customers_restored": len(restored_customers),
            "customers": restored_customers
        }
        
    except Exception as e:
        logger.error(f"Customer restoration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Customer restoration failed: {str(e)}")


# ==================== HELPER FUNCTIONS ====================

def _apply_stock_impact_from_sales(
    db: Session, 
    user_id: int, 
    invoices: List[Invoice],
    background_tasks: BackgroundTasks
) -> bool:
    """
    Apply stock impact from restored sales.
    This ensures inventory is consistent with sales history.
    """
    try:
        # Get all stock movements from these invoices
        invoice_numbers = [inv.invoice_number for inv in invoices]
        
        existing_movements = db.query(StockMovement).filter(
            StockMovement.reference_id.in_(invoice_numbers),
            StockMovement.reason == "Sales Sync"
        ).all()
        
        existing_refs = {m.reference_id for m in existing_movements}
        
        # Create missing stock movements
        movements_created = 0
        
        for invoice in invoices:
            if invoice.invoice_number in existing_refs:
                continue  # Already has stock movement
            
            line_items = db.query(InvoiceLineItem).filter(
                InvoiceLineItem.invoice_id == invoice.id
            ).all()
            
            for item in line_items:
                if item.product_id:
                    product = db.query(Product).filter(
                        Product.id == item.product_id,
                        Product.user_id == user_id
                    ).first()
                    
                    if product:
                        movement = StockMovement(
                            product_id=item.product_id,
                            movement_type="OUT",
                            quantity=item.quantity,
                            reason="Sales Sync (Restored)",
                            reference_id=invoice.invoice_number
                        )
                        db.add(movement)
                        movements_created += 1
        
        if movements_created > 0:
            db.commit()
            logger.info(f"Created {movements_created} stock movements from restored sales")
        
        return True
        
    except Exception as e:
        logger.error(f"Stock impact application failed: {e}")
        db.rollback()
        return False
