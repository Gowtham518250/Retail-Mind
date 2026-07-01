"""
🧾 INVOICES & BILLING API — AI Shop Pro Enterprise Backend
Covers:
  - Generate invoices
  - Accept offline-synced invoices from app (`/sync` endpoints)
  - Auto-deduct inventory
  - Auto-log in Universal Transactions
  - GST extraction and filtering
"""

from typing import Optional, List
from datetime import datetime, date, timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from db import get_db
from models import (
    Invoice, InvoiceLineItem, Product, Customer,
    UniversalTransaction, StockMovement
)
from security import owner_only, worker_or_owner, sanitize_input

router = APIRouter(prefix="/api/invoices", tags=["invoices & billing"])

# =====================
# SCHEMAS
# =====================
class InvoiceLineItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)

class InvoiceSyncCreate(BaseModel):
    invoice_number: str
    offline_id: Optional[str] = None
    customer_phone: Optional[str] = None  # Removed min_length/max_length restriction for flexibility
    customer_name: Optional[str] = None
    total_amount: float
    paid_amount: float = 0
    tax: float = 0
    payment_status: str = "PAID"
    line_items: Optional[List[InvoiceLineItemCreate]] = None  # Made optional
    invoice_date: Optional[str] = None  # YYYY-MM-DD
    due_date: Optional[str] = None  # Added due_date
    notes: Optional[str] = None
    
    @validator('line_items')
    def validate_line_items(cls, v):
        if v is not None and len(v) > 0:
            for item in v:
                if not item.product_name or item.product_name.strip().lower() in ['unknown', 'unknown item', '??']:
                    raise ValueError(f'Invalid product name: {item.product_name}')
        return v

class InvoiceLineItemResponse(BaseModel):
    id: int
    product_id: Optional[int]
    description: Optional[str]
    quantity: int
    unit_price: float
    line_total: float
    
    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    total_amount: float
    paid_amount: float
    status: str
    payment_status: str
    invoice_date: date
    created_at: datetime
    line_items: List[InvoiceLineItemResponse] = []

    class Config:
        from_attributes = True

# =====================
# ENDPOINTS
# =====================

@router.post("/sync")
def sync_offline_invoice(
    data: InvoiceSyncCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    """
    Accept an invoice generated while the app was offline.
    This creates the invoice, deducts inventory, and logs revenue.
    Uses transaction-based approach for data integrity.
    """
    shop_id = current_user
    invoice_number = sanitize_input(data.invoice_number, "invoice_number")

    # Check for duplicate sync (idempotency) - check both offline_id and invoice_number
    if data.offline_id:
        existing = db.query(Invoice).filter(
            Invoice.user_id == shop_id,
            Invoice.offline_id == data.offline_id
        ).first()
        if existing:
            return {"message": "Invoice already synced (offline_id).", "invoice_id": existing.id, "status": "DUPLICATE"}
    
    # Always check invoice_number as fallback
    existing = db.query(Invoice).filter(
        Invoice.user_id == shop_id,
        Invoice.invoice_number == invoice_number
    ).first()

    if existing:
        return {"message": "Invoice already synced (invoice_number).", "invoice_id": existing.id, "status": "DUPLICATE"}

    # Find/Create Customer
    customer_id = None
    if data.customer_phone:
        phone = sanitize_input(data.customer_phone, "customer_phone")
        cust = db.query(Customer).filter(
            Customer.user_id == shop_id,
            Customer.phone == phone
        ).first()
        if not cust:
            cust = Customer(
                user_id=shop_id,
                customer_name=sanitize_input(data.customer_name or "Cash Customer", "customer_name"),
                phone=phone
            )
            db.add(cust)
            db.flush()
        customer_id = cust.id

    try:
        inv_date = datetime.strptime(data.invoice_date, "%Y-%m-%d").date() if data.invoice_date else date.today()
    except ValueError:
        inv_date = date.today()
    
    try:
        due_date = datetime.strptime(data.due_date, "%Y-%m-%d").date() if data.due_date else inv_date
    except ValueError:
        due_date = inv_date

    # TRANSACTION-BASED APPROACH: All operations in single transaction
    try:
        # Create Invoice
        invoice = Invoice(
            user_id=shop_id,
            customer_id=customer_id,
            customer_name=sanitize_input(data.customer_name or "Cash Customer", "customer_name"),
            customer_phone=data.customer_phone,
            invoice_number=invoice_number,
            offline_id=data.offline_id,
            invoice_date=inv_date,
            due_date=due_date,
            subtotal=data.total_amount - data.tax,
            tax=data.tax,
            total_amount=data.total_amount,
            paid_amount=data.paid_amount,
            status="SENT",
            payment_status=data.payment_status.upper() if data.payment_status else "UNPAID",
            source="OFFLINE_SYNC",
            notes=sanitize_input(data.notes or "", "notes"),
        )
        db.add(invoice)
        db.flush()

        # Process Line Items & Deduct Inventory (if any)
        if data.line_items and len(data.line_items) > 0:
            for item in data.line_items:
                line_total = item.quantity * item.unit_price
                db_line = InvoiceLineItem(
                    invoice_id=invoice.id,
                    product_id=item.product_id,
                    description=sanitize_input(item.product_name, "product_name"),
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=line_total,
                )
                db.add(db_line)

                # Inventory Auto-Deduction with validation
                if item.product_id:
                    product = db.query(Product).filter(
                        Product.id == item.product_id,
                        Product.user_id == shop_id
                    ).with_for_update().first()  # Row-level lock for concurrency
                    if product:
                        # Validate stock availability
                        current_stock = product.current_stock or 0
                        if current_stock < item.quantity:
                            raise HTTPException(
                                status_code=400,
                                detail=f"Insufficient stock for product {item.product_name}. Available: {current_stock}, Required: {item.quantity}"
                            )
                        # 🔧 FIX: Debug logging for quantity deduction
                        print(f"🔍 [Backend] Deducting {item.quantity} from {item.product_name} (current: {current_stock})")
                        product.current_stock = max(0, current_stock - item.quantity)
                        # Log stock movement
                        mov = StockMovement(
                            product_id=product.id,
                            movement_type="OUT",
                            quantity=item.quantity,
                            reason="Sales Sync",
                            reference_id=invoice_number,
                        )
                        db.add(mov)
                        print(f"✅ [Backend] Stock updated: {item.product_name} ({current_stock} → {product.current_stock})")
                else:
                    # 🔧 FIX: Deduct by product name when product_id is missing
                    product = db.query(Product).filter(
                        Product.product_name.ilike(f"%{item.product_name}%"),
                        Product.user_id == shop_id
                    ).with_for_update().first()
                    if product:
                        current_stock = product.current_stock or 0
                        if current_stock >= item.quantity:
                            # 🔧 FIX: Debug logging for quantity deduction
                            print(f"🔍 [Backend] Deducting {item.quantity} from {item.product_name} by name (current: {current_stock})")
                            product.current_stock = max(0, current_stock - item.quantity)
                            mov = StockMovement(
                                product_id=product.id,
                                movement_type="OUT",
                                quantity=item.quantity,
                                reason="Sales Sync (by name)",
                                reference_id=invoice_number,
                            )
                            db.add(mov)
                            print(f"✅ [Backend] Stock updated: {item.product_name} ({current_stock} → {product.current_stock})")

        # Universal Journal Entry
        tx = UniversalTransaction(
            shop_id=shop_id,
            tx_type="INCOME",
            category="SALE",
            amount=data.paid_amount,
            reference_id=invoice_number,
            description=f"Sales Sync: {invoice_number}",
            tx_date=datetime.combine(inv_date, datetime.min.time()),
        )
        db.add(tx)

        # Commit transaction - all operations succeed or all fail
        db.commit()
        # Build consistent response payload
        line_items_out = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
        payload = {
            "id": invoice.id,
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "total_amount": float(invoice.total_amount),
            "paid_amount": float(invoice.paid_amount),
            "subtotal": float(invoice.subtotal),
            "tax": float(invoice.tax),
            "status": invoice.status,
            "payment_status": invoice.payment_status,
            "invoice_date": str(invoice.invoice_date),
            "due_date": str(invoice.due_date) if invoice.due_date else None,
            "created_at": invoice.created_at.isoformat(),
            "message": "Invoice synced and inventory deducted.",
            "line_items": [
                {
                    "product_id": li.product_id,
                    "product_name": li.description,
                    "quantity": li.quantity,
                    "unit_price": float(li.unit_price),
                    "total": float(li.line_total),
                }
                for li in line_items_out
            ],
        }
        return JSONResponse(status_code=201, content=payload)

    except Exception as e:
        # Rollback on any error
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")


@router.get("/", response_model=List[InvoiceResponse])
def get_invoices(
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    source: Optional[str] = None,
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Get all invoices for the shop"""
    shop_id = current_user
    query = db.query(Invoice).filter(Invoice.user_id == shop_id)
    if status:
        query = query.filter(Invoice.status == status.upper())
    if payment_status:
        query = query.filter(Invoice.payment_status == payment_status.upper())
    if source:
        query = query.filter(Invoice.source == source.upper())
    return query.order_by(desc(Invoice.created_at)).offset(skip).limit(limit).all()


@router.post("/create")
def create_invoice(
    data: InvoiceSyncCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    shop_id = current_user
    invoice_number = sanitize_input(data.invoice_number, "invoice_number")

    existing = db.query(Invoice).filter(
        Invoice.user_id == shop_id,
        Invoice.invoice_number == invoice_number
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Invoice number already exists")

    customer_id = None
    if data.customer_phone:
        phone = sanitize_input(data.customer_phone, "customer_phone")
        cust = db.query(Customer).filter(
            Customer.user_id == shop_id,
            Customer.phone == phone
        ).first()
        if not cust:
            cust = Customer(
                user_id=shop_id,
                customer_name=sanitize_input(data.customer_name or "Cash Customer", "customer_name"),
                phone=phone
            )
            db.add(cust)
            db.flush()
        customer_id = cust.id

    try:
        inv_date = datetime.strptime(data.invoice_date, "%Y-%m-%d").date() if data.invoice_date else date.today()
    except ValueError:
        inv_date = date.today()
    
    try:
        due_date = datetime.strptime(data.due_date, "%Y-%m-%d").date() if data.due_date else inv_date
    except ValueError:
        due_date = inv_date

    invoice = Invoice(
        user_id=shop_id,
        customer_id=customer_id,
        customer_name=sanitize_input(data.customer_name or "Cash Customer", "customer_name"),
        customer_phone=data.customer_phone,
        invoice_number=invoice_number,
        invoice_date=inv_date,
        due_date=due_date,
        subtotal=data.total_amount - data.tax,
        tax=data.tax,
        total_amount=data.total_amount,
        paid_amount=data.paid_amount,
        status="SENT",
        payment_status=data.payment_status.upper() if data.payment_status else "UNPAID",
        source="MANUAL_ENTRY",
        notes=sanitize_input(data.notes or "", "notes"),
    )
    db.add(invoice)
    db.flush()

    if data.line_items and len(data.line_items) > 0:
        for item in data.line_items:
            line_total = item.quantity * item.unit_price
            db_line = InvoiceLineItem(
                invoice_id=invoice.id,
                product_id=item.product_id,
                description=sanitize_input(item.product_name, "product_name"),
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=line_total,
            )
            db.add(db_line)

            if item.product_id:
                product = db.query(Product).filter(
                    Product.id == item.product_id,
                    Product.user_id == shop_id
                ).first()
                if product:
                    if (product.current_stock or 0) < item.quantity:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Insufficient stock for product ID {product.id}. Available: {product.current_stock or 0}, Requested: {item.quantity}"
                        )
                    # 🔧 FIX: Debug logging for quantity deduction
                    print(f"🔍 [Backend Create] Deducting {item.quantity} from {item.product_name} (current: {product.current_stock or 0})")
                    product.current_stock = (product.current_stock or 0) - item.quantity
                    mov = StockMovement(
                        product_id=product.id,
                        movement_type="OUT",
                        quantity=item.quantity,
                        reason="Manual Sale",
                        reference_id=invoice_number,
                    )
                    db.add(mov)
                    print(f"✅ [Backend Create] Stock updated: {item.product_name} ({product.current_stock or 0 + item.quantity} → {product.current_stock})")
            else:
                # 🔧 FIX: Deduct by product name when product_id is missing
                product = db.query(Product).filter(
                    Product.product_name.ilike(f"%{item.product_name}%"),
                    Product.user_id == shop_id
                ).first()
                if product:
                    current_stock = product.current_stock or 0
                    if current_stock >= item.quantity:
                        # 🔧 FIX: Debug logging for quantity deduction
                        print(f"🔍 [Backend Create] Deducting {item.quantity} from {item.product_name} by name (current: {current_stock})")
                        product.current_stock = max(0, current_stock - item.quantity)
                        mov = StockMovement(
                            product_id=product.id,
                            movement_type="OUT",
                            quantity=item.quantity,
                            reason="Manual Sale (by name)",
                            reference_id=invoice_number,
                        )
                        db.add(mov)
                        print(f"✅ [Backend Create] Stock updated: {item.product_name} ({current_stock} → {product.current_stock})")

    tx = UniversalTransaction(
        shop_id=shop_id,
        tx_type="INCOME",
        category="SALE",
        amount=data.paid_amount,
        reference_id=invoice_number,
        description=f"Manual Invoice: {invoice_number}",
        tx_date=datetime.combine(inv_date, datetime.min.time()),
    )
    db.add(tx)

    db.commit()
    db.refresh(invoice)

    line_items_out = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice.id).all()
    payload = {
        "id": invoice.id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "total_amount": float(invoice.total_amount),
        "paid_amount": float(invoice.paid_amount),
        "subtotal": float(invoice.subtotal),
        "tax": float(invoice.tax),
        "status": invoice.status,
        "payment_status": invoice.payment_status,
        "invoice_date": str(invoice.invoice_date),
        "due_date": str(invoice.due_date) if invoice.due_date else None,
        "created_at": invoice.created_at.isoformat(),
        "message": "Invoice created successfully.",
        "line_items": [
            {
                "product_id": li.product_id,
                "product_name": li.description,
                "quantity": li.quantity,
                "unit_price": float(li.unit_price),
                "total": float(li.line_total),
            }
            for li in line_items_out
        ],
    }
    return JSONResponse(status_code=201, content=payload)


# ── These MUST come before /{invoice_id} ──────────────────────────────

@router.get("/overdue")
def get_overdue_invoices(
    days_overdue: int = Query(30),
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    shop_id = current_user
    cutoff_date = date.today() - timedelta(days=days_overdue)
    overdue_invoices = db.query(Invoice).filter(
        Invoice.user_id == shop_id,
        Invoice.payment_status.in_(["UNPAID", "PARTIAL"]),
        Invoice.due_date < cutoff_date
    ).order_by(desc(Invoice.due_date)).offset(skip).limit(limit).all()
    return {
        "overdue_invoices": overdue_invoices,
        "count": len(overdue_invoices),
        "days_overdue_threshold": days_overdue
    }


@router.get("/payments")
def get_invoice_payments(
    invoice_id: Optional[int] = None,
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    shop_id = current_user
    from models import Payment
    query = db.query(Payment).join(Invoice).filter(Invoice.user_id == shop_id)
    if invoice_id:
        query = query.filter(Payment.invoice_id == invoice_id)
    payments = query.order_by(desc(Payment.payment_date)).offset(skip).limit(limit).all()
    return {
        "payments": [
            {
                "id": p.id,
                "invoice_id": p.invoice_id,
                "payment_method": p.payment_method,
                "amount": float(p.amount),
                "payment_date": p.payment_date,
                "reference_number": p.reference_number,
                "notes": p.notes
            }
            for p in payments
        ],
        "count": len(payments)
    }


@router.get("/analytics/summary")
def get_invoice_analytics(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    shop_id = current_user
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()
    query = db.query(Invoice).filter(
        Invoice.user_id == shop_id,
        Invoice.invoice_date >= start_date,
        Invoice.invoice_date <= end_date
    )
    total_invoices = query.count()
    total_amount   = query.with_entities(func.sum(Invoice.total_amount)).scalar() or 0
    total_paid     = query.with_entities(func.sum(Invoice.paid_amount)).scalar() or 0
    paid_count     = query.filter(Invoice.payment_status == "PAID").count()
    unpaid_count   = query.filter(Invoice.payment_status == "UNPAID").count()
    partial_count  = query.filter(Invoice.payment_status == "PARTIAL").count()
    sent_count     = query.filter(Invoice.status == "SENT").count()
    overdue_count  = query.filter(
        Invoice.payment_status.in_(["UNPAID", "PARTIAL"]),
        Invoice.due_date < date.today()
    ).count()
    return {
        "period": {"start": str(start_date), "end": str(end_date)},
        "total_invoices": total_invoices,
        "total_amount": float(total_amount),
        "total_paid": float(total_paid),
        "outstanding_amount": float(total_amount - total_paid),
        "payment_status_breakdown": {"paid": paid_count, "unpaid": unpaid_count, "partial": partial_count},
        "status_breakdown": {"sent": sent_count, "overdue": overdue_count},
        "collection_rate": round((total_paid / total_amount * 100) if total_amount > 0 else 0, 2)
    }


# ── /{invoice_id} MUST be last ────────────────────────────────────────

@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    shop_id = current_user
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == shop_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    line_items = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice_id).all()
    return {
        "id":             invoice.id,
        "invoice_number": invoice.invoice_number,
        "total_amount":   float(invoice.total_amount),
        "paid_amount":    float(invoice.paid_amount),
        "subtotal":       float(invoice.subtotal),
        "tax":            float(invoice.tax),
        "status":         invoice.status,
        "payment_status": invoice.payment_status,
        "invoice_date":   str(invoice.invoice_date),
        "created_at":     invoice.created_at.isoformat(),
        "line_items": [
            {
                "product_id":   li.product_id,
                "product_name": li.description,
                "quantity":     li.quantity,
                "unit_price":   float(li.unit_price),
                "total":        float(li.line_total),
            }
            for li in line_items
        ],
    }


class InvoiceUpdate(BaseModel):
    paid_amount: Optional[float] = None
    payment_status: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

@router.put("/{invoice_id}")
def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    shop_id = current_user
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == shop_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Update fields
    if data.paid_amount is not None:
        invoice.paid_amount = data.paid_amount
        # Auto-set payment status based on paid_amount vs total_amount
        if invoice.paid_amount >= invoice.total_amount:
            invoice.payment_status = "PAID"
        elif invoice.paid_amount > 0:
            invoice.payment_status = "PARTIAL"
        else:
            invoice.payment_status = "UNPAID"
    
    if data.payment_status is not None:
        invoice.payment_status = data.payment_status.upper()
    
    if data.status is not None:
        invoice.status = data.status.upper()
    
    if data.notes is not None:
        invoice.notes = data.notes
    
    db.commit()
    db.refresh(invoice)
    
    # Get line items
    line_items = db.query(InvoiceLineItem).filter(InvoiceLineItem.invoice_id == invoice_id).all()
    
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "total_amount": float(invoice.total_amount),
        "paid_amount": float(invoice.paid_amount),
        "subtotal": float(invoice.subtotal),
        "tax": float(invoice.tax),
        "status": invoice.status,
        "payment_status": invoice.payment_status,
        "invoice_date": str(invoice.invoice_date),
        "due_date": str(invoice.due_date) if invoice.due_date else None,
        "created_at": invoice.created_at.isoformat(),
        "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
        "line_items": [
            {
                "product_id": li.product_id,
                "product_name": li.description,
                "quantity": li.quantity,
                "unit_price": float(li.unit_price),
                "total": float(li.line_total),
            }
            for li in line_items
        ],
    }

@router.delete("/{invoice_id}")
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    shop_id = current_user
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == shop_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete(invoice)
    db.commit()
    return {"message": "Invoice deleted securely."}
