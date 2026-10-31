"""
Sales Restore Service - Complete Sales Recovery After App Reinstall
Restores: invoices, invoice items, stock impact, customer history, payment status
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc, case
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from db import get_db
from models import Invoice, InvoiceStatus, InvoiceLineItem, Customer, Product, StockMovement, OnlineOrder, OnlineOrderStatus
from security import get_current_user as check_current_user
from sales_recognition import recognized_invoice_filters

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

@router.get("/cancelled-order-identifiers")
def get_cancelled_order_identifiers(
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    """Return minimal cancellation references for safe invoice restoration.

    This route deliberately does not depend on the paid online_orders feature:
    invoice/Khata recovery must still be possible when the owner cannot open the
    online-orders management screen. It reveals only the caller's own cancelled
    order IDs and statuses, not customer names, addresses, items or payments.
    """
    owner_filter = OnlineOrder.shop_id == user_id
    total_count = db.query(func.count(OnlineOrder.id)).filter(owner_filter).scalar() or 0
    cancellation_rows = db.query(
        OnlineOrder.id,
        OnlineOrder.order_status,
    ).filter(
        owner_filter,
        OnlineOrder.order_status.in_([
            OnlineOrderStatus.CANCELLED,
            OnlineOrderStatus.REJECTED,
            OnlineOrderStatus.RETURNED,
        ]),
    ).all()

    # The dashboard's Total Online Orders metric is a lifetime count:
    # include pending, accepted, dispatched, delivered, cancelled, rejected
    # and returned records. The separate IDs below are used only to exclude
    # cancelled-order invoices from sales/Khata restoration.
    orders = [
        {
            "id": int(row.id),
            "order_id": int(row.id),
            "status": (
                row.order_status.value
                if hasattr(row.order_status, "value")
                else str(row.order_status)
            ),
            "order_status": (
                row.order_status.value
                if hasattr(row.order_status, "value")
                else str(row.order_status)
            ),
        }
        for row in cancellation_rows
    ]
    return {
        "orders": orders,
        "total": int(total_count),
        "totalCount": int(total_count),
        "cancelledCount": sum(
            1
            for order in orders
            if order["status"].upper() in {"CANCELLED", "CANCELED", "RETURNED"}
        ),
        "rejectedCount": sum(
            1 for order in orders if order["status"].upper() == "REJECTED"
        ),
    }


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
        query = db.query(Invoice).filter(
            Invoice.user_id == user_id,
            Invoice.status != InvoiceStatus.CANCELLED,
        )
        
        if request.start_date:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d").date()
            query = query.filter(Invoice.invoice_date >= start_date)
        
        if request.end_date:
            end_date = datetime.strptime(request.end_date, "%Y-%m-%d").date()
            query = query.filter(Invoice.invoice_date <= end_date)
        
        invoices = query.order_by(desc(Invoice.created_at)).all()
        # Keep provisional online invoices available for the invoice/order UI,
        # but exclude them from the sales totals until the order is DELIVERED.
        if invoices:
            recognized_invoice_ids = {
                row[0]
                for row in query.with_entities(Invoice.id).filter(
                    *recognized_invoice_filters(),
                ).all()
            }
        else:
            recognized_invoice_ids = set()

        restored_invoices = []
        total_line_items = 0
        customers_restored = set()

        # Fetch all line items in one query. Querying inside the invoice loop
        # caused an N+1 round trip for every restored invoice.
        invoice_ids = [invoice.id for invoice in invoices]
        line_items_by_invoice: Dict[int, List[InvoiceLineItem]] = {}
        if invoice_ids:
            all_line_items = db.query(InvoiceLineItem).filter(
                InvoiceLineItem.invoice_id.in_(invoice_ids)
            ).all()
            for line_item in all_line_items:
                line_items_by_invoice.setdefault(line_item.invoice_id, []).append(
                    line_item
                )

        for invoice in invoices:
            line_items = line_items_by_invoice.get(invoice.id, [])

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
                "counts_as_sale": invoice.id in recognized_invoice_ids,
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
                db, user_id, invoices, background_tasks, line_items_by_invoice
            )
        
        # The restore payload includes open invoices, but sales KPIs must not
        # count accepted/undelivered online orders as completed revenue.
        recognized_invoices = [
            inv for inv in restored_invoices if inv["counts_as_sale"]
        ]
        total_revenue = sum(float(inv["total_amount"]) for inv in recognized_invoices)
        total_paid = sum(float(inv["paid_amount"]) for inv in recognized_invoices)
        unpaid_count = sum(
            1 for inv in recognized_invoices
            if inv["payment_status"] in ["UNPAID", "PARTIAL"]
        )

        summary = {
            "total_revenue": total_revenue,
            "total_paid": total_paid,
            "outstanding_amount": total_revenue - total_paid,
            "unpaid_invoices": unpaid_count,
            "paid_invoices": len(recognized_invoices) - unpaid_count,
            "average_invoice_value": total_revenue / len(recognized_invoices) if recognized_invoices else 0,
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
        # Aggregate invoice counts, dates and revenue in one DB round trip
        # instead of issuing a separate COUNT/SELECT for each statistic.
        invoice_stats = db.query(
            func.count(Invoice.id),
            func.coalesce(
                func.sum(case((Invoice.payment_status == "PAID", 1), else_=0)), 0
            ),
            func.coalesce(
                func.sum(case((Invoice.payment_status == "UNPAID", 1), else_=0)), 0
            ),
            func.coalesce(
                func.sum(case((Invoice.payment_status == "PARTIAL", 1), else_=0)), 0
            ),
            func.min(Invoice.created_at),
            func.max(Invoice.created_at),
            func.coalesce(func.sum(Invoice.total_amount), 0),
        ).filter(
            Invoice.user_id == user_id,
            Invoice.status != InvoiceStatus.CANCELLED,
        ).one()

        (
            total_invoices,
            paid_count,
            unpaid_count,
            partial_count,
            oldest_created_at,
            newest_created_at,
            total_revenue,
        ) = invoice_stats
        
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
                "oldest_invoice": oldest_created_at.isoformat() if oldest_created_at else None,
                "newest_invoice": newest_created_at.isoformat() if newest_created_at else None
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
    background_tasks: BackgroundTasks,
    line_items_by_invoice: Optional[Dict[int, List[InvoiceLineItem]]] = None,
) -> bool:
    """
    Record the stock impact of restored sales without N+1 database queries.

    A stable per-invoice-line idempotency key prevents repeat restores from
    creating duplicate OUT movements. Legacy "Sales Sync" and previously
    restored rows are both recognised.
    """
    try:
        if not invoices:
            return True

        invoice_numbers = [
            invoice.invoice_number for invoice in invoices
            if invoice.invoice_number
        ]
        if not invoice_numbers:
            return True

        existing_rows = db.query(StockMovement.reference_id).filter(
            StockMovement.reference_id.in_(invoice_numbers),
            func.upper(StockMovement.reason).in_(
                ("SALES SYNC", "SALES SYNC (RESTORED)")
            ),
        ).all()
        existing_refs = {row[0] for row in existing_rows}

        if line_items_by_invoice is None:
            invoice_ids = [invoice.id for invoice in invoices]
            line_items_by_invoice = {}
            if invoice_ids:
                line_items = db.query(InvoiceLineItem).filter(
                    InvoiceLineItem.invoice_id.in_(invoice_ids)
                ).all()
                for item in line_items:
                    line_items_by_invoice.setdefault(item.invoice_id, []).append(
                        item
                    )

        candidate_product_ids = {
            item.product_id
            for invoice in invoices
            if invoice.invoice_number not in existing_refs
            for item in line_items_by_invoice.get(invoice.id, [])
            if item.product_id is not None
        }
        owned_product_ids = set()
        if candidate_product_ids:
            owned_rows = db.query(Product.id).filter(
                Product.user_id == user_id,
                Product.id.in_(candidate_product_ids),
            ).all()
            owned_product_ids = {row[0] for row in owned_rows}

        movements_to_create = []
        for invoice in invoices:
            if invoice.invoice_number in existing_refs:
                continue

            for item in line_items_by_invoice.get(invoice.id, []):
                if item.product_id not in owned_product_ids:
                    continue

                movements_to_create.append(
                    StockMovement(
                        product_id=item.product_id,
                        movement_type="OUT",
                        quantity=item.quantity,
                        reason="Sales Sync",
                        reference_id=invoice.invoice_number,
                        idempotency_key=f"sales-restore:{invoice.id}:{item.id}",
                    )
                )

        if movements_to_create:
            db.add_all(movements_to_create)
            db.commit()
            logger.info(
                "Created %s stock movements from restored sales",
                len(movements_to_create),
            )

        return True

    except Exception as e:
        logger.error("Stock impact application failed: %s", e)
        db.rollback()
        return False
