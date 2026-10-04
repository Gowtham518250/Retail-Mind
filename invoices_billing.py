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
from datetime import datetime, date, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import or_, and_, desc, func, cast, Integer
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal
import logging
from sqlalchemy.exc import IntegrityError

from db import get_db
from models import (
    Invoice, InvoiceLineItem, Product, Customer, FlashSale,
    UniversalTransaction, StockMovement, Payment, PaymentMethod,
    PaymentStatus, InvoiceStatus
)
from security import owner_only, worker_or_owner, sanitize_input, resolve_shop_id
from realtime import publish_realtime_event
from audit_logging import AuditAction, AuditService

router = APIRouter(prefix="/api/invoices", tags=["invoices & billing"])
logger = logging.getLogger(__name__)


def _parse_client_timestamp(raw: Optional[str]) -> Optional[datetime]:
    """Normalize an ISO-8601 phone timestamp to naive UTC for DateTime columns."""
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError, OverflowError):
        return None

# =====================
# SCHEMAS
# =====================
class InvoiceLineItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    # Decimal is intentional: Product.current_stock is PostgreSQL NUMERIC,
    # so quantities must use the same numeric type during inventory arithmetic.
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount_amount: Decimal = Field(Decimal("0"), ge=0)
    discount_reason: Optional[str] = Field(default=None, max_length=120)
    discount_source: Optional[str] = Field(default=None, max_length=50)

class InvoiceSyncCreate(BaseModel):
    invoice_number: str
    offline_id: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    total_amount: float = Field(..., ge=0)
    paid_amount: float = Field(0, ge=0)
    tax: float = Field(0, ge=0)
    payment_status: str = "PAID"
    line_items: Optional[List[InvoiceLineItemCreate]] = None
    invoice_date: Optional[str] = None
    sale_timestamp: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None
    # FEATURE (staff sales leaderboard): optional, self-reported by the
    # client's active-worker selector. See models.py Invoice.sold_by_worker_id
    # for why this is not used for any authorization decision.
    sold_by_worker_id: Optional[int] = None
    
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
    quantity: float
    unit_price: float
    discount_amount: float = 0
    line_total: float
    
    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    total_amount: float
    paid_amount: float
    status: str
    payment_status: str
    invoice_date: date
    created_at: datetime
    line_items: List[InvoiceLineItemResponse] = []

    class Config:
        from_attributes = True


class PaymentWriteRequest(BaseModel):
    invoice_id: Optional[int] = None
    invoice_number: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    paid_amount: Optional[float] = Field(None, ge=0)
    payment_method: str = "ONLINE"
    reference_id: Optional[str] = Field(default=None, max_length=100)
    idempotency_key: Optional[str] = Field(default=None, max_length=128)
    payer_name: Optional[str] = Field(default=None, max_length=120)
    source: str = Field(default="PAYMENT_DETECTION", max_length=50)
    timestamp: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=500)


def _payment_status_for(invoice: Invoice) -> PaymentStatus:
    total = Decimal(str(invoice.total_amount or 0))
    paid = Decimal(str(invoice.paid_amount or 0))
    if paid >= total - Decimal("0.01"):
        return PaymentStatus.PAID
    if paid > Decimal("0.01"):
        return PaymentStatus.PARTIAL
    return PaymentStatus.UNPAID


def _apply_payment_write(
    *,
    data: PaymentWriteRequest,
    db: Session,
    shop_id: int,
    mode: str,
):
    if data.amount is None and data.paid_amount is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either amount or paid_amount.",
        )

    idempotency_key = (data.idempotency_key or "").strip() or None
    if idempotency_key:
        existing = (
            db.query(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(
                Invoice.user_id == shop_id,
                Payment.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing:
            existing_invoice = (
                db.query(Invoice)
                .filter(
                    Invoice.id == existing.invoice_id,
                    Invoice.user_id == shop_id,
                )
                .first()
            )
            if existing_invoice is None:
                raise HTTPException(status_code=404, detail="Payment invoice not found.")
            return {
                "success": True,
                "duplicate": True,
                "payment_id": existing.id,
                "invoice_id": existing_invoice.id,
                "invoice_number": existing_invoice.invoice_number,
                "applied_amount": float(existing.amount or 0),
                "paid_amount": float(existing_invoice.paid_amount or 0),
                "payment_status": (
                    existing_invoice.payment_status.value
                    if hasattr(existing_invoice.payment_status, "value")
                    else str(existing_invoice.payment_status)
                ),
                "message": "Payment already recorded (idempotent retry).",
            }

    if data.invoice_id is None and not (data.invoice_number and data.invoice_number.strip()):
        raise HTTPException(
            status_code=400,
            detail="invoice_id or invoice_number is required for a payment write.",
        )

    invoice_query = db.query(Invoice).filter(
        Invoice.user_id == shop_id,
        Invoice.status != InvoiceStatus.CANCELLED,
    )
    if data.invoice_id is not None:
        invoice_query = invoice_query.filter(Invoice.id == data.invoice_id)
    else:
        invoice_query = invoice_query.filter(
            Invoice.invoice_number == data.invoice_number.strip()
        )

    invoice = invoice_query.with_for_update().first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    total = Decimal(str(invoice.total_amount or 0))
    current_paid = Decimal(str(invoice.paid_amount or 0))

    if mode == "delta":
        delta = Decimal(str(data.amount or 0))
    else:
        target_paid = Decimal(str(data.paid_amount if data.paid_amount is not None else 0))
        if target_paid < current_paid - Decimal("0.01"):
            raise HTTPException(
                status_code=400,
                detail="paid_amount cannot reduce an invoice's existing paid amount.",
            )
        delta = target_paid - current_paid

    if delta <= Decimal("0.01"):
        status_value = _payment_status_for(invoice)
        invoice.payment_status = status_value
        if status_value == PaymentStatus.PAID:
            invoice.status = InvoiceStatus.PAID
        elif status_value == PaymentStatus.PARTIAL:
            invoice.status = InvoiceStatus.PARTIAL
        return {
            "success": True,
            "duplicate": False,
            "no_op": True,
            "payment_id": None,
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "applied_amount": 0.0,
            "paid_amount": float(invoice.paid_amount or 0),
            "payment_status": status_value.value,
            "message": "Invoice already reflects this payment state.",
        }

    outstanding = max(Decimal("0"), total - current_paid)
    if delta > outstanding + Decimal("0.01"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Payment exceeds invoice balance. "
                f"Outstanding: ₹{outstanding:.2f}, Received: ₹{delta:.2f}"
            ),
        )

    method_name = (data.payment_method or "ONLINE").upper().strip()
    payment_method = PaymentMethod.__members__.get(method_name)
    if payment_method is None:
        payment_method = PaymentMethod.ONLINE

    new_paid = min(total, current_paid + delta)
    invoice.paid_amount = new_paid
    invoice.payment_status = _payment_status_for(invoice)

    if invoice.payment_status == PaymentStatus.PAID:
        invoice.status = InvoiceStatus.PAID
    elif invoice.payment_status == PaymentStatus.PARTIAL:
        invoice.status = InvoiceStatus.PARTIAL

    payment = Payment(
        invoice_id=invoice.id,
        payment_method=payment_method,
        amount=delta,
        payment_date=_parse_client_timestamp(data.timestamp) or datetime.utcnow(),
        reference_number=(data.reference_id or "").strip() or None,
        notes=(
            data.notes
            or (
                f"{data.source} payment"
                + (f" from {data.payer_name.strip()}" if data.payer_name else "")
            )
        ),
        idempotency_key=idempotency_key,
    )
    db.add(payment)

    db.add(
        UniversalTransaction(
            shop_id=shop_id,
            tx_type="INCOME",
            category="PAYMENT",
            amount=delta,
            reference_id=invoice.invoice_number,
            description=f"Payment received for invoice {invoice.invoice_number}",
            tx_date=payment.payment_date,
        )
    )

    try:
        db.commit()
        db.refresh(invoice)
        db.refresh(payment)
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = (
                db.query(Payment)
                .join(Invoice, Payment.invoice_id == Invoice.id)
                .filter(
                    Invoice.user_id == shop_id,
                    Payment.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing:
                existing_invoice = (
                    db.query(Invoice)
                    .filter(
                        Invoice.id == existing.invoice_id,
                        Invoice.user_id == shop_id,
                    )
                    .first()
                )
                return {
                    "success": True,
                    "duplicate": True,
                    "payment_id": existing.id,
                    "invoice_id": existing.invoice_id,
                    "invoice_number": existing_invoice.invoice_number if existing_invoice else None,
                    "applied_amount": float(existing.amount or 0),
                    "paid_amount": float(existing_invoice.paid_amount or 0) if existing_invoice else 0.0,
                    "payment_status": (
                        existing_invoice.payment_status.value
                        if existing_invoice and hasattr(existing_invoice.payment_status, "value")
                        else str(existing_invoice.payment_status) if existing_invoice else None
                    ),
                    "message": "Payment already recorded (idempotent retry).",
                }
        raise HTTPException(status_code=409, detail="Payment write conflicted with another transaction.")
    except Exception as exc:
        db.rollback()
        logger.error("Payment transaction failed safely: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Payment transaction failed safely.")

    # Business-level audit trail is best-effort and intentionally runs after
    # the financial transaction has committed. A logging failure must never
    # turn a successful payment into an apparent API failure.
    try:
        AuditService.log_action(
            db=db,
            user_id=shop_id,
            action=AuditAction.CREATE,
            table_name="payments",
            record_id=payment.id,
            new_values={
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "amount": float(delta),
                "payment_method": payment_method.value,
                "reference_id": (data.reference_id or "").strip() or None,
                "source": data.source,
            },
            description=f"Payment recorded for invoice {invoice.invoice_number}",
        )
        AuditService.log_action(
            db=db,
            user_id=shop_id,
            action=AuditAction.UPDATE,
            table_name="invoices",
            record_id=invoice.id,
            new_values={
                "paid_amount": float(invoice.paid_amount or 0),
                "payment_status": (
                    invoice.payment_status.value
                    if hasattr(invoice.payment_status, "value")
                    else str(invoice.payment_status)
                ),
            },
            description=f"Invoice payment state updated for {invoice.invoice_number}",
        )
    except Exception as audit_error:
        logger.warning(
            "Payment audit logging failed after committed transaction: %s",
            audit_error,
        )

    event_id = str(uuid.uuid4())
    payment_status = (
        invoice.payment_status.value
        if hasattr(invoice.payment_status, "value")
        else str(invoice.payment_status)
    )

    publish_realtime_event({
        "event_id": event_id,
        "type": "payment.updated",
        "shop_id": shop_id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "amount": float(delta),
        "paid_amount": float(invoice.paid_amount or 0),
        "payment_status": payment_status,
        "payment_id": payment.id,
        "reference_id": (data.reference_id or "").strip() or None,
        "source": data.source,
    })

    publish_realtime_event({
        "event_id": str(uuid.uuid4()),
        "type": "invoice.updated",
        "shop_id": shop_id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "paid_amount": float(invoice.paid_amount or 0),
        "payment_status": payment_status,
        "status": invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
        "source": data.source,
    })

    return {
        "success": True,
        "duplicate": False,
        "payment_id": payment.id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "applied_amount": float(delta),
        "paid_amount": float(invoice.paid_amount or 0),
        "payment_status": payment_status,
        "message": "Payment recorded successfully.",
    }


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
    shop_id = resolve_shop_id(current_user)
    invoice_number = sanitize_input(data.invoice_number, "invoice_number")

    if data.offline_id:
        existing = db.query(Invoice).filter(
            Invoice.user_id == shop_id,
            Invoice.offline_id == data.offline_id
        ).first()
        if existing:
            return {"message": "Invoice already synced (offline_id).", "invoice_id": existing.id, "status": "ALREADY_SYNCED", "offline_id": data.offline_id}
    
    existing = db.query(Invoice).filter(
        Invoice.user_id == shop_id,
        Invoice.invoice_number == invoice_number
    ).first()

    if existing:
        return {"message": "Invoice already synced (invoice_number).", "invoice_id": existing.id, "status": "ALREADY_SYNCED", "invoice_number": invoice_number}

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

    if not data.invoice_date:
        raise HTTPException(
            status_code=400,
            detail="invoice_date is required to preserve the sale's business date",
        )
    try:
        inv_date = datetime.strptime(data.invoice_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="invoice_date must use YYYY-MM-DD format")
    
    client_timestamp = _parse_client_timestamp(data.sale_timestamp)

    try:
        due_date = datetime.strptime(data.due_date, "%Y-%m-%d").date() if data.due_date else inv_date
    except ValueError:
        due_date = inv_date

    try:
        sub_t = Decimal(str(data.total_amount)) - Decimal(str(data.tax))

        now_utc = datetime.utcnow()
        active_flash_sale = (
            db.query(FlashSale)
            .filter(
                FlashSale.user_id == shop_id,
                FlashSale.is_active == True,
                FlashSale.end_time > now_utc,
            )
            .order_by(FlashSale.start_time.desc())
            .first()
        )

        prepared_line_items = []
        special_discount_total = Decimal("0")

        if data.line_items and len(data.line_items) > 0:
            for item in data.line_items:
                base_line = (
                    Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
                )
                client_discount = min(
                    base_line,
                    max(Decimal("0"), Decimal(str(item.discount_amount or 0))),
                )

                flash_discount = Decimal("0")
                flash_reason = ""
                product = None

                if item.product_id:
                    product = (
                        db.query(Product)
                        .filter(
                            Product.id == item.product_id,
                            Product.user_id == shop_id,
                        )
                        .first()
                    )
                if product is None:
                    product = (
                        db.query(Product)
                        .filter(
                            func.lower(Product.product_name) ==
                            item.product_name.lower().strip(),
                            Product.user_id == shop_id,
                        )
                        .first()
                    )

                if active_flash_sale and product:
                    sale_category = (
                        active_flash_sale.category or ""
                    ).strip().lower()
                    product_category = (
                        getattr(product, "category", None) or ""
                    ).strip().lower()
                    applies = (
                        sale_category in {
                            "all", "*", "all products"
                        }
                        or (
                            sale_category
                            and product_category == sale_category
                        )
                    )
                    if applies:
                        flash_discount = (
                            base_line
                            * Decimal(
                                str(active_flash_sale.discount_pct or 0)
                            )
                            / Decimal("100")
                        ).quantize(Decimal("0.01"))
                        flash_discount = min(
                            base_line,
                            max(Decimal("0"), flash_discount),
                        )
                        flash_reason = (
                            f"Special Discount: Flash Sale "
                            f"{float(active_flash_sale.discount_pct):g}%"
                        )

                client_has_flash = "flash sale" in (
                    ((item.discount_reason or "") + " " +
                     (item.discount_source or "")).lower()
                )

                effective_discount = client_discount
                if flash_discount > Decimal("0") and not client_has_flash:
                    effective_discount = min(
                        base_line,
                        client_discount + flash_discount,
                    )
                elif client_has_flash:
                    effective_discount = min(
                        base_line,
                        max(client_discount, flash_discount),
                    )

                special_discount_total += max(
                    Decimal("0"),
                    effective_discount,
                )
                prepared_line_items.append({
                    "item": item,
                    "product": product,
                    "discount_amount": effective_discount,
                    "discount_reason": flash_reason
                        if flash_discount > Decimal("0")
                        else item.discount_reason,
                })

            computed_subtotal = sum(
                (
                    entry["item"].quantity *
                    entry["item"].unit_price
                ) - entry["discount_amount"]
                for entry in prepared_line_items
            )
            computed_subtotal = max(Decimal("0"), computed_subtotal)
            tolerance = max(
                Decimal("0.5"),
                computed_subtotal * Decimal("0.01"),
            )
            if abs(computed_subtotal - sub_t) > tolerance:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invoice total mismatch: discounted line items "
                        f"sum to {computed_subtotal}, but total_amount - "
                        f"tax = {sub_t}. Please recalculate."
                    ),
                )

        # FEATURE (staff sales leaderboard): validate the claimed worker
        # actually belongs to this shop before trusting it, rather than
        # blindly storing a client-supplied ID (which could otherwise be
        # used to attribute a sale to an arbitrary worker row in any shop).
        validated_worker_id = None
        if data.sold_by_worker_id:
            from models import Worker
            worker_row = db.query(Worker).filter(
                Worker.id == data.sold_by_worker_id,
                Worker.shopkeeper_id == shop_id,
            ).first()
            if worker_row:
                validated_worker_id = worker_row.id

        invoice = Invoice(
            user_id=shop_id,
            customer_id=customer_id,
            customer_name=sanitize_input(data.customer_name or "Cash Customer", "customer_name"),
            customer_phone=data.customer_phone,
            invoice_number=invoice_number,
            offline_id=data.offline_id,
            invoice_date=inv_date,
            created_at=client_timestamp or datetime.utcnow(),
            due_date=due_date,
            subtotal=float(sub_t),
            tax=data.tax,
            total_amount=data.total_amount,
            paid_amount=data.paid_amount,
            status="SENT",
            payment_status=data.payment_status.upper() if data.payment_status else "UNPAID",
            source="OFFLINE_SYNC",
            notes=sanitize_input(
                (
                    (data.notes or "").strip()
                    + (
                        f" | Special Discount: ₹{special_discount_total:.2f}"
                        if special_discount_total > Decimal("0")
                        else ""
                    )
                ),
                "notes",
            ),
            sold_by_worker_id=validated_worker_id,
        )
        db.add(invoice)
        db.flush()

        inventory_changes = []
        for prepared in prepared_line_items:
            item = prepared["item"]
            discount_amount = prepared["discount_amount"]
            line_total = max(
                Decimal("0"),
                (item.quantity * item.unit_price) - discount_amount,
            )
            product_id = item.product_id or (
                prepared["product"].id if prepared["product"] else None
            )

            db_line = InvoiceLineItem(
                invoice_id=invoice.id,
                product_id=product_id,
                description=sanitize_input(item.product_name, "product_name"),
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=discount_amount,
                line_total=line_total,
            )
            db.add(db_line)

            if product_id:
                product = db.query(Product).filter(
                    Product.id == product_id,
                    Product.user_id == shop_id
                ).with_for_update().first()
            else:
                product = db.query(Product).filter(
                    func.lower(Product.product_name) ==
                    item.product_name.lower().strip(),
                    Product.user_id == shop_id
                ).with_for_update().first()

            if product:
                current_stock = product.current_stock or Decimal("0")
                if current_stock < item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Insufficient stock for product "
                            f"'{item.product_name}'. Available: "
                            f"{current_stock}, Required: {item.quantity}"
                        ),
                    )
                product.current_stock = max(
                    Decimal("0"),
                    current_stock - item.quantity,
                )
                inventory_changes.append({
                    "product_id": product.id,
                    "quantity": float(item.quantity),
                    "new_stock": float(product.current_stock),
                })
                mov = StockMovement(
                    product_id=product.id,
                    movement_type="OUT",
                    quantity=item.quantity,
                    reason=(
                        "Flash Sale Sale"
                        if prepared["discount_amount"] > 0
                        else "Sales Sync"
                    ),
                    reference_id=invoice_number,
                )
                db.add(mov)

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

        db.commit()

        publish_realtime_event({
            "event_id": str(uuid.uuid4()),
            "type": "invoice.created",
            "shop_id": shop_id,
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "customer_id": customer_id,
            "total_amount": float(invoice.total_amount),
            "paid_amount": float(invoice.paid_amount),
            "payment_status": invoice.payment_status,
            "source": invoice.source,
        })

        if data.paid_amount > 0:
            publish_realtime_event({
                "event_id": str(uuid.uuid4()),
                "type": "payment.updated",
                "shop_id": shop_id,
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "customer_id": customer_id,
                "amount": float(invoice.paid_amount),
                "payment_status": invoice.payment_status,
                "source": "OFFLINE_SYNC",
            })

        if inventory_changes:
            publish_realtime_event({
                "event_id": str(uuid.uuid4()),
                "type": "inventory.changed",
                "shop_id": shop_id,
                "reference_type": "INVOICE_SYNC",
                "reference_id": invoice_number,
                "changes": inventory_changes,
            })

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
            "special_discount_total": float(special_discount_total),
            "line_items": [
                {
                    "product_id": li.product_id,
                    "product_name": li.description,
                    "quantity": float(li.quantity),
                    "unit_price": float(li.unit_price),
                    "discount_amount": float(li.discount_amount or 0),
                    "total": float(li.line_total),
                }
                for li in line_items_out
            ],
        }
        return JSONResponse(status_code=201, content=payload)

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        existing = None
        if data.offline_id:
            existing = db.query(Invoice).filter(
                Invoice.user_id == shop_id,
                Invoice.offline_id == data.offline_id,
            ).first()
        if existing is None:
            existing = db.query(Invoice).filter(
                Invoice.user_id == shop_id,
                Invoice.invoice_number == invoice_number,
            ).first()
        if existing is not None:
            return {
                "message": "Invoice already synced",
                "invoice_id": existing.id,
                "invoice_number": existing.invoice_number,
                "offline_id": existing.offline_id,
                "status": "ALREADY_SYNCED",
            }
        raise HTTPException(status_code=409, detail="Invoice idempotency conflict")
    except Exception as e:
        db.rollback()
        logger.exception("Invoice sync transaction failed")
        raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")


@router.get("", response_model=List[InvoiceResponse])
@router.get("/", response_model=List[InvoiceResponse], include_in_schema=False)
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
    shop_id = resolve_shop_id(current_user)
    query = db.query(Invoice).options(joinedload(Invoice.line_items)).filter(Invoice.user_id == shop_id)
    if status:
        query = query.filter(Invoice.status == status.upper())
    if payment_status:
        query = query.filter(Invoice.payment_status == payment_status.upper())
    if source:
        query = query.filter(Invoice.source == source.upper())
    return query.order_by(desc(Invoice.created_at)).offset(skip).limit(limit).all()


@router.get("/next-bill-number")
def get_next_bill_number(
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    """
    Return the highest customer-facing BILL-NNNN sequence currently stored for
    this shop. The phone keeps the next number locally, but the server history
    is authoritative when local app data has been cleared.
    """
    shop_id = resolve_shop_id(current_user)

    # Do not load every invoice into Python for a simple sequence lookup.
    # The previous implementation scanned the complete invoice table on every
    # sale, which became increasingly expensive as the shop history grew.
    # SUBSTR is supported by PostgreSQL and SQLite and lets the database do the
    # aggregation in one query.
    highest = (
        db.query(
            func.max(
                cast(
                    func.substr(Invoice.invoice_number, 6),
                    # SQLAlchemy maps this to the database integer type.
                    # Non-BILL invoice numbers are excluded by the filter.
                    Integer,
                )
            )
        )
        .filter(
            Invoice.user_id == shop_id,
            Invoice.invoice_number.ilike("BILL-%"),
        )
        .scalar()
        or 0
    )

    total_invoices = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.user_id == shop_id)
        .scalar()
        or 0
    )

    return {
        "shop_id": shop_id,
        "highest_bill_number": int(highest),
        "next_bill_number": f"BILL-{int(highest) + 1:04d}",
        "total_invoices": int(total_invoices),
    }


@router.post("/create")
def create_invoice(
    data: InvoiceSyncCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    shop_id = resolve_shop_id(current_user)
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

    sub_t2 = Decimal(str(data.total_amount)) - Decimal(str(data.tax))

    # Resolve the currently active shop Flash Sale once per invoice. The
    # backend is authoritative: a client cannot accidentally omit a live
    # discount just because its local cache is stale.
    now_utc = datetime.utcnow()
    active_flash_sale = (
        db.query(FlashSale)
        .filter(
            FlashSale.user_id == shop_id,
            FlashSale.is_active == True,
            FlashSale.end_time > now_utc,
        )
        .order_by(FlashSale.start_time.desc())
        .first()
    )

    prepared_line_items = []
    special_discount_total = Decimal("0")

    if data.line_items and len(data.line_items) > 0:
        for item in data.line_items:
            base_line = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
            client_discount = min(
                base_line,
                max(Decimal("0"), Decimal(str(item.discount_amount or 0))),
            )

            flash_discount = Decimal("0")
            flash_reason = ""
            product = None

            if item.product_id:
                product = (
                    db.query(Product)
                    .filter(
                        Product.id == item.product_id,
                        Product.user_id == shop_id,
                    )
                    .first()
                )
            if product is None:
                product = (
                    db.query(Product)
                    .filter(
                        func.lower(Product.product_name) == item.product_name.lower().strip(),
                        Product.user_id == shop_id,
                    )
                    .first()
                )

            if active_flash_sale and product:
                sale_category = (active_flash_sale.category or "").strip().lower()
                product_category = (getattr(product, "category", None) or "").strip().lower()
                sale_applies = (
                    sale_category in {"all", "*", "all products"} or
                    (sale_category and product_category == sale_category)
                )

                if sale_applies:
                    flash_discount = (
                        base_line *
                        Decimal(str(active_flash_sale.discount_pct or 0)) /
                        Decimal("100")
                    ).quantize(Decimal("0.01"))
                    flash_discount = min(base_line, max(Decimal("0"), flash_discount))
                    flash_reason = (
                        f"Flash Sale {float(active_flash_sale.discount_pct):g}%"
                    )

            # If the client already included the verified Flash Sale discount,
            # don't double-apply it. Otherwise the server adds the live one.
            client_has_flash = "flash sale" in (
                (item.discount_reason or "") + " " + (item.discount_source or "")
            ).lower()

            effective_discount = client_discount
            if flash_discount > Decimal("0") and not client_has_flash:
                effective_discount = min(
                    base_line,
                    client_discount + flash_discount,
                )
            elif client_has_flash:
                effective_discount = min(
                    base_line,
                    max(client_discount, flash_discount),
                )

            special_discount_total += max(Decimal("0"), effective_discount)
            prepared_line_items.append(
                {
                    "item": item,
                    "product": product,
                    "discount_amount": effective_discount,
                    "discount_reason": (
                        flash_reason
                        if flash_discount > Decimal("0")
                        else item.discount_reason
                    ) or None,
                }
            )

        computed_subtotal = sum(
            (entry["item"].quantity * entry["item"].unit_price)
            - entry["discount_amount"]
            for entry in prepared_line_items
        )
        computed_subtotal = max(Decimal("0"), computed_subtotal)

        tolerance = max(Decimal("0.5"), computed_subtotal * Decimal("0.01"))
        if abs(computed_subtotal - sub_t2) > tolerance:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invoice total mismatch: discounted line items sum to {computed_subtotal}, "
                    f"but total_amount - tax = {sub_t2}. Please recalculate."
                )
            )

    invoice = Invoice(
        user_id=shop_id,
        customer_id=customer_id,
        customer_name=sanitize_input(data.customer_name or "Cash Customer", "customer_name"),
        customer_phone=data.customer_phone,
        invoice_number=invoice_number,
        invoice_date=inv_date,
        due_date=due_date,
        subtotal=float(sub_t2),
        tax=data.tax,
        total_amount=data.total_amount,
        paid_amount=data.paid_amount,
        status="SENT",
        payment_status=data.payment_status.upper() if data.payment_status else "UNPAID",
        source="MANUAL_ENTRY",
        notes=sanitize_input(
            (
                (data.notes or "").strip()
                + (
                    f" | Special Discount: ₹{special_discount_total:.2f}"
                    if special_discount_total > Decimal("0")
                    else ""
                )
            ),
            "notes",
        ),
    )
    db.add(invoice)
    db.flush()

    if prepared_line_items:
        for prepared in prepared_line_items:
            item = prepared["item"]
            discount_amount = prepared["discount_amount"]
            line_total = max(
                Decimal("0"),
                (item.quantity * item.unit_price) - discount_amount,
            )
            db_line = InvoiceLineItem(
                invoice_id=invoice.id,
                product_id=item.product_id or (
                    prepared["product"].id if prepared["product"] else None
                ),
                description=sanitize_input(item.product_name, "product_name"),
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=discount_amount,
                line_total=line_total,
            )
            db.add(db_line)

            product_id = item.product_id or (
                prepared["product"].id if prepared["product"] else None
            )

            if product_id:
                product = (
                    db.query(Product)
                    .with_for_update()
                    .filter(
                        Product.id == product_id,
                        Product.user_id == shop_id,
                    )
                    .first()
                )
                if product:
                    current_stock = product.current_stock or Decimal("0")
                    if current_stock < item.quantity:
                        db.rollback()
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Insufficient stock for product '{item.product_name}'. "
                                f"Available: {current_stock}, Requested: {item.quantity}"
                            ),
                        )
                    product.current_stock = max(
                        Decimal("0"),
                        current_stock - item.quantity,
                    )
                    mov = StockMovement(
                        product_id=product.id,
                        movement_type="OUT",
                        quantity=item.quantity,
                        reason=(
                            "Flash Sale Sale"
                            if prepared["discount_reason"]
                            else "Manual Sale"
                        ),
                        reference_id=invoice_number,
                    )
                    db.add(mov)
            else:
                product = db.query(Product).with_for_update().filter(
                    func.lower(Product.product_name) == item.product_name.lower().strip(),
                    Product.user_id == shop_id,
                ).first()
                if product:
                    current_stock = product.current_stock or Decimal("0")
                    if current_stock < item.quantity:
                        db.rollback()
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Insufficient stock for product '{item.product_name}'. "
                                f"Available: {current_stock}, Requested: {item.quantity}"
                            ),
                        )
                    product.current_stock = max(
                        Decimal("0"),
                        current_stock - item.quantity,
                    )
                    db.add(
                        StockMovement(
                            product_id=product.id,
                            movement_type="OUT",
                            quantity=item.quantity,
                            reason=(
                                "Flash Sale Sale"
                                if prepared["discount_reason"]
                                else "Manual Sale (by name)"
                            ),
                            reference_id=invoice_number,
                        )
                    )

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

    try:
        db.commit()
        db.refresh(invoice)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create invoice: {str(e)}")

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
        "special_discount_total": float(special_discount_total),
        "line_items": [
            {
                "product_id": li.product_id,
                "product_name": li.description,
                "quantity": float(li.quantity),
                "unit_price": float(li.unit_price),
                "discount_amount": float(li.discount_amount or 0),
                "total": float(li.line_total),
            }
            for li in line_items_out
        ],
    }
    return JSONResponse(status_code=201, content=payload)


@router.post("/payments")
def create_invoice_payment(
    data: PaymentWriteRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    shop_id = resolve_shop_id(current_user)
    return _apply_payment_write(data=data, db=db, shop_id=shop_id, mode="delta")


@router.put("/update_payment")
def update_invoice_payment(
    data: PaymentWriteRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    shop_id = resolve_shop_id(current_user)
    return _apply_payment_write(data=data, db=db, shop_id=shop_id, mode="target")


@router.get("/overdue")
def get_overdue_invoices(
    days_overdue: int = Query(30),
    skip: int = Query(0),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    shop_id = resolve_shop_id(current_user)
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
    shop_id = resolve_shop_id(current_user)
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
    shop_id = resolve_shop_id(current_user)
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


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(worker_or_owner),
):
    shop_id = resolve_shop_id(current_user)
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
        "customer_name":  invoice.customer_name,
        "customer_phone": invoice.customer_phone,
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
                "quantity":     float(li.quantity),
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
    shop_id = resolve_shop_id(current_user)
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == shop_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if data.paid_amount is not None:
        invoice.paid_amount = data.paid_amount
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
    
    try:
        db.commit()
        db.refresh(invoice)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update invoice: {str(e)}")
    
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
                "quantity": float(li.quantity),
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
    shop_id = resolve_shop_id(current_user)
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.user_id == shop_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete(invoice)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete invoice: {str(e)}")
    return {"message": "Invoice deleted securely."}