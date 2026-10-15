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
import re
from datetime import datetime, date, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import or_, and_, desc, func, cast, Integer, text
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
from sqlalchemy.exc import IntegrityError

from db import get_db
from models import (
    Invoice, InvoiceLineItem, Product, Customer, FlashSale,
    UniversalTransaction, StockMovement, ShopExpense, Payment, PaymentMethod,
    PaymentStatus, InvoiceStatus, OnlineOrder
)
from security import owner_only, worker_or_owner, sanitize_input, resolve_shop_id
from realtime import publish_realtime_event
from durable_sync import append_sync_event
from audit_logging import AuditAction, AuditService

router = APIRouter(prefix="/api/invoices", tags=["invoices & billing"])
logger = logging.getLogger(__name__)


def _invoice_replay_matches(existing: Invoice, data: "InvoiceSyncCreate", invoice_number: str) -> bool:
    """Treat an offline retry as idempotent only when immutable sale facts match.

    Paid state is intentionally excluded because a later payment may legitimately
    update an invoice after the original offline sale has synced.
    """
    def _money(value) -> Decimal:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _name(value) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip().casefold()

    try:
        if not data.invoice_date:
            return False
        if str(existing.invoice_number or "").strip() != invoice_number:
            return False
        if _money(existing.total_amount) != _money(data.total_amount):
            return False
        if _money(existing.tax) != _money(data.tax):
            return False
        parsed_date = datetime.strptime(data.invoice_date, "%Y-%m-%d").date()
        if existing.invoice_date != parsed_date:
            return False
        if data.customer_phone and _name(existing.customer_phone) != _name(data.customer_phone):
            return False
        if data.customer_name and _name(existing.customer_name) != _name(data.customer_name):
            return False

        if data.line_items is None:
            return True
        stored_lines = list(getattr(existing, "line_items", []) or [])
        if len(stored_lines) != len(data.line_items):
            return False
        incoming = sorted(
            (_name(line.product_name),
             Decimal(str(line.quantity)).quantize(Decimal("0.001")),
             _money(line.unit_price))
            for line in data.line_items
        )
        persisted = sorted(
            (_name(line.description),
             Decimal(str(line.quantity)).quantize(Decimal("0.001")),
             _money(line.unit_price))
            for line in stored_lines
        )
        return incoming == persisted
    except (ArithmeticError, TypeError, ValueError):
        return False


def _already_synced_invoice(existing: Invoice) -> dict:
    return {
        "message": "Invoice already synced; canonical server record returned.",
        "invoice_id": existing.id,
        "invoice_number": existing.invoice_number,
        "offline_id": existing.offline_id,
        "status": "ALREADY_SYNCED",
        "total_amount": float(existing.total_amount or 0),
        "paid_amount": float(existing.paid_amount or 0),
        "payment_status": (
            existing.payment_status.value
            if hasattr(existing.payment_status, "value")
            else str(existing.payment_status or "")
        ),
    }


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


def _invoice_event_timestamp(invoice: Invoice) -> datetime:
    """Return the sale event time in naive UTC for DateTime database columns."""
    timestamp = getattr(invoice, "created_at", None)
    if timestamp is None:
        return datetime.utcnow()
    if timestamp.tzinfo is not None:
        return timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    return timestamp


def _resolve_invoice_sync_payment_state(
    total_amount,
    paid_amount,
    is_borrow: Optional[bool],
    notes: Optional[str],
    payment_method: Optional[str],
):
    """Return canonical paid amount, document status, and payment status.

    Only a checkout explicitly marked CASH can default zero received to a full
    cash receipt. Older clients are repaired only when invoice notes explicitly
    identify both cash and a regular (not borrow) sale. Online/unlabelled records
    with no receipt are never assumed to be paid.
    """
    total = Decimal(str(total_amount or 0)).quantize(Decimal("0.01"))
    paid = Decimal(str(paid_amount or 0)).quantize(Decimal("0.01"))
    note_text = str(notes or "").casefold()
    method_text = str(payment_method or "").strip().casefold().replace("_", " ").replace("-", " ")
    explicit_cash_method = method_text in {"cash", "cod", "cash on delivery"}
    cash_in_legacy_note = "payment via cash" in note_text
    legacy_regular_cash_sale = (
        "regular sale" in note_text
        and "borrow invoice" not in note_text
        and cash_in_legacy_note
    )

    if paid == Decimal("0.00") and (
        (is_borrow is False and (explicit_cash_method or cash_in_legacy_note))
        or (is_borrow is None and legacy_regular_cash_sale)
    ):
        paid = total

    paid = min(max(paid, Decimal("0.00")), total)
    if total > Decimal("0.00") and paid > Decimal("0.00") and paid >= total - Decimal("0.01"):
        return float(total), "PAID", "PAID"
    if paid > Decimal("0.00"):
        return float(paid), "PARTIAL", "PARTIAL"
    return 0.0, "SENT", "UNPAID"


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

    @validator("total_amount", "paid_amount", "tax", pre=True)
    def normalize_money_to_paise(cls, value):
        """Normalize monetary inputs before validation or persistence.

        A float's extra binary precision must not leak into invoice balances.
        Once rounded to paise, every later comparison uses the same currency
        precision as the stored NUMERIC financial fields.
        """
        try:
            amount = Decimal(str(value))
            if not amount.is_finite() or amount < 0:
                raise ValueError("Monetary amounts must be finite and non-negative.")
            return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Monetary amounts must be finite and non-negative.") from exc

    @validator("paid_amount")
    def paid_amount_must_not_exceed_total(cls, value, values):
        total = values.get("total_amount")
        if total is not None and value > total:
            raise ValueError("paid_amount cannot exceed total_amount.")
        return value

    @validator("tax")
    def tax_must_not_exceed_total(cls, value, values):
        total = values.get("total_amount")
        if total is not None and value > total:
            raise ValueError("tax cannot exceed total_amount.")
        return value
    payment_status: str = "PAID"
    is_borrow: Optional[bool] = None
    payment_method: Optional[str] = Field(default=None, max_length=50)
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
    subtotal: float = 0
    tax: float = 0
    total_amount: float
    paid_amount: float
    status: str
    payment_status: str
    payment_method: Optional[str] = None
    source: Optional[str] = None
    invoice_date: date
    due_date: Optional[date] = None
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


def _normalize_invoice_payment_method(value: Optional[str], default: str = "CASH") -> str:
    """Normalize client labels to the canonical invoice payment-method values."""
    raw = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "COD": "CASH",
        "CASH_ON_DELIVERY": "CASH",
        "UPI": "ONLINE",
        "DIGITAL": "ONLINE",
        "NET_BANKING": "ONLINE",
        "NETBANKING": "ONLINE",
        "BANK_TRANSFER": "TRANSFER",
        "CHEQUE": "CHEQUE",
        "CHECK": "CHEQUE",
    }
    normalized = aliases.get(raw, raw)
    allowed = {"CASH", "CARD", "TRANSFER", "CHEQUE", "ONLINE"}
    return normalized if normalized in allowed else default


def _normalize_new_invoice_payment_state(invoice: Invoice) -> PaymentStatus:
    """Payment status must match recorded money, not a client-side default label."""
    state = _payment_status_for(invoice)
    invoice.payment_status = state
    if state == PaymentStatus.PAID:
        invoice.status = InvoiceStatus.PAID
    elif state == PaymentStatus.PARTIAL:
        invoice.status = InvoiceStatus.PARTIAL
    else:
        invoice.status = InvoiceStatus.SENT
    return state


def _calculate_sale_loss(*, purchase_price, quantity, net_sale_amount) -> Decimal:
    """Return the non-negative shortfall versus recorded cost, excluding sales tax."""
    try:
        cost_per_unit = Decimal(str(purchase_price or 0))
        qty = Decimal(str(quantity or 0))
        net_sold = Decimal(str(net_sale_amount or 0))
    except Exception:
        return Decimal("0.00")
    if (
        not cost_per_unit.is_finite()
        or not qty.is_finite()
        or not net_sold.is_finite()
        or cost_per_unit <= 0
        or qty <= 0
    ):
        return Decimal("0.00")
    total_cost = (cost_per_unit * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    net_sold = max(Decimal("0"), net_sold).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return max(Decimal("0.00"), total_cost - net_sold).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _record_below_cost_sale_loss(
    *,
    db: Session,
    shop_id: int,
    invoice_number: str,
    sale_date: date,
    product: Product,
    quantity,
    net_sale_amount,
) -> Decimal:
    """Persist below-cost loss into the shop expense ledger and universal P&L journal."""
    purchase_price = getattr(product, "purchase_price", None)
    loss_amount = _calculate_sale_loss(
        purchase_price=purchase_price,
        quantity=quantity,
        net_sale_amount=net_sale_amount,
    )
    if loss_amount <= Decimal("0"):
        return Decimal("0.00")

    name = sanitize_input(str(product.product_name or "Catalog product"), "product_name")
    cost = Decimal(str(purchase_price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    description = (
        f"Sold {name} below cost: qty {quantity}, cost ₹{cost:.2f}/unit, "
        f"net sale ₹{Decimal(str(net_sale_amount or 0)):.2f}; invoice {invoice_number}"
    )[:200]
    db.add(
        ShopExpense(
            shop_id=shop_id,
            category="SALE_LOSS",
            amount=loss_amount,
            description=description,
            expense_date=sale_date,
            payment_method="non_cash_adjustment",
        )
    )
    db.add(
        UniversalTransaction(
            shop_id=shop_id,
            tx_type="EXPENSE",
            category="SALE_LOSS",
            amount=loss_amount,
            reference_id=invoice_number,
            description=description,
            tx_date=datetime.combine(sale_date, datetime.min.time()),
        )
    )
    logger.info(
        "SALE BELOW COST: shop=%s invoice=%s product_id=%s quantity=%s loss=%s",
        shop_id,
        invoice_number,
        product.id,
        quantity,
        loss_amount,
    )
    return loss_amount


def _apply_payment_write(
    *,
    data: PaymentWriteRequest,
    db: Session,
    shop_id: int,
    mode: str,
    commit_transaction: bool = True,
):
    """Record a payment; callers may join it to a larger atomic transaction."""
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
        # The production DB has a compatibility trigger that records a payment
        # if an ONLINE_ORDER invoice is marked PAID directly. When this canonical
        # writer is doing the same update, tell that trigger not to create a
        # second Payment row; this writer already inserts the idempotent ledger row.
        postgres_payment_guard = db.get_bind().dialect.name == "postgresql"
        if postgres_payment_guard:
            db.connection().execute(
                text("SELECT set_config('retail_mind.payment_write_invoice_id', :invoice_id, true)"),
                {"invoice_id": str(invoice.id)},
            )
        db.flush()
        if postgres_payment_guard:
            db.connection().execute(
                text("SELECT set_config('retail_mind.payment_write_invoice_id', '', true)")
            )
        payment_status = (
            invoice.payment_status.value
            if hasattr(invoice.payment_status, "value")
            else str(invoice.payment_status)
        )
        invoice_status = (
            invoice.status.value
            if hasattr(invoice.status, "value")
            else str(invoice.status)
        )
        payment_events = [
            append_sync_event(db, {
                "event_id": str(uuid.uuid4()),
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
            }),
            append_sync_event(db, {
                "event_id": str(uuid.uuid4()),
                "type": "invoice.updated",
                "shop_id": shop_id,
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "paid_amount": float(invoice.paid_amount or 0),
                "payment_status": payment_status,
                "status": invoice_status,
                "source": data.source,
            }),
        ]
        if commit_transaction:
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

    # When the caller composes this payment into a larger transaction,
    # defer audit logging and event publishing until that caller commits.
    if commit_transaction:
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

        for event in payment_events:
            publish_realtime_event(event)

    return {
        "success": True,
        "duplicate": False,
        "payment_id": payment.id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "applied_amount": float(delta),
        "paid_amount": float(invoice.paid_amount or 0),
        "payment_status": payment_status,
        "events": [] if commit_transaction else payment_events,
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
            if _invoice_replay_matches(existing, data, invoice_number):
                return _already_synced_invoice(existing)
            raise HTTPException(
                status_code=409,
                detail="offline_id already belongs to an invoice with different immutable sale details.",
            )
    
    existing = db.query(Invoice).filter(
        Invoice.user_id == shop_id,
        Invoice.invoice_number == invoice_number
    ).first()

    if existing:
        if _invoice_replay_matches(existing, data, invoice_number):
            return _already_synced_invoice(existing)
        raise HTTPException(
            status_code=409,
            detail="invoice_number already belongs to a different invoice; refusing to hide a financial conflict.",
        )

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

    resolved_paid_amount, resolved_invoice_status, resolved_payment_status = (
        _resolve_invoice_sync_payment_state(
            data.total_amount, data.paid_amount, data.is_borrow,
            data.notes, data.payment_method
        )
    )

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
            paid_amount=resolved_paid_amount,
            status=resolved_invoice_status,
            payment_status=resolved_payment_status,
            payment_method=_normalize_invoice_payment_method(data.payment_method),
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
        sale_loss_total = Decimal("0.00")
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
                # Offline invoices must never be lost just because the
                # server's stock is stale or was already decremented locally.
                # The invoice/sale is the source of truth for the completed sale.
                # Clamp inventory at zero rather than rejecting the financial
                # transaction. This makes offline sync idempotent from the
                # business perspective while still preventing negative stock.
                available_stock = max(Decimal("0"), current_stock)
                shortage = max(Decimal("0"), item.quantity - available_stock)
                deducted = min(item.quantity, available_stock)
                product.current_stock = available_stock - deducted

                inventory_changes.append({
                    "product_id": product.id,
                    "quantity": float(item.quantity),
                    "deducted_quantity": float(deducted),
                    "shortage_quantity": float(shortage),
                    "new_stock": float(product.current_stock),
                    "forced_sale": bool(shortage > 0),
                })
                if shortage > 0:
                    logger.warning(
                        "FORCED OFFLINE SALE: product=%s available=%s requested=%s shortage=%s invoice=%s",
                        item.product_name,
                        available_stock,
                        item.quantity,
                        shortage,
                        invoice_number,
                    )

                mov = StockMovement(
                    product_id=product.id,
                    movement_type="OUT",
                    quantity=item.quantity,
                    reason=(
                        "Flash Sale Sale"
                        if prepared["discount_amount"] > 0
                        else ("Offline Sale - Stock Shortage" if shortage > 0 else "Sales Sync")
                    ),
                    reference_id=invoice_number,
                )
                db.add(mov)
                sale_loss_total += _record_below_cost_sale_loss(
                    db=db,
                    shop_id=shop_id,
                    invoice_number=invoice_number,
                    sale_date=inv_date,
                    product=product,
                    quantity=item.quantity,
                    net_sale_amount=line_total,
                )

        tx = UniversalTransaction(
            shop_id=shop_id,
            tx_type="INCOME",
            category="SALE",
            amount=resolved_paid_amount,
            reference_id=invoice_number,
            description=f"Sales Sync: {invoice_number}",
            tx_date=_invoice_event_timestamp(invoice),
        )
        db.add(tx)

        # Persist recovery events in the same transaction as the invoice,
        # payments, stock movements, and universal transaction records.
        realtime_events = [{
            "event_id": str(uuid.uuid4()),
            "type": "invoice.created",
            "shop_id": shop_id,
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "customer_id": customer_id,
            "total_amount": float(invoice.total_amount),
            "paid_amount": float(invoice.paid_amount),
            "payment_status": invoice.payment_status,
            "payment_method": invoice.payment_method,
            "source": invoice.source,
        }]

        if resolved_paid_amount > 0:
            realtime_events.append({
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
            realtime_events.append({
                "event_id": str(uuid.uuid4()),
                "type": "inventory.changed",
                "shop_id": shop_id,
                "reference_type": "INVOICE_SYNC",
                "reference_id": invoice_number,
                "changes": inventory_changes,
            })

        durable_events = [append_sync_event(db, event) for event in realtime_events]
        db.commit()

        # Redis/WebSocket is a fast notification path only. The durable event
        # remains available to clients even if this publish fails.
        for event in durable_events:
            publish_realtime_event(event)

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
            "payment_method": invoice.payment_method,
            "source": invoice.source,
            "invoice_date": str(invoice.invoice_date),
            "due_date": str(invoice.due_date) if invoice.due_date else None,
            "created_at": invoice.created_at.isoformat(),
            "message": "Invoice synced and inventory deducted.",
            "special_discount_total": float(special_discount_total),
            "sale_loss_total": float(sale_loss_total),
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
            if _invoice_replay_matches(existing, data, invoice_number):
                return _already_synced_invoice(existing)
            raise HTTPException(
                status_code=409,
                detail="Existing invoice conflicts with this offline retry payload.",
            )
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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Get all invoices for the shop"""
    shop_id = resolve_shop_id(current_user)
    # Keep invoice list responses bounded. The dashboard only needs a recent
    # page; fetching the full invoice history repeatedly makes serialization
    # and joined line-items increasingly expensive.
    query = (
        db.query(Invoice)
        .options(joinedload(Invoice.line_items))
        .filter(Invoice.user_id == shop_id)
    )
    if status:
        query = query.filter(Invoice.status == status.upper())
    if payment_status:
        query = query.filter(Invoice.payment_status == payment_status.upper())
    if source:
        query = query.filter(Invoice.source == source.upper())
    invoices = query.order_by(desc(Invoice.created_at)).offset(skip).limit(limit).all()

    # Earlier versions omitted payment method/source from invoice responses and
    # left online-order invoices without a persisted method. Resolve legacy rows
    # in one query so Flutter can classify them into the right Cash/Online tab.
    legacy_order_ids = {}
    for invoice in invoices:
        if not invoice.payment_method and str(invoice.source or "").upper() == "ONLINE_ORDER":
            match = re.search(r"Online Order #([0-9]+)", invoice.notes or "")
            if match:
                legacy_order_ids[invoice.id] = int(match.group(1))

    legacy_orders = {}
    if legacy_order_ids:
        orders = db.query(OnlineOrder).filter(
            OnlineOrder.shop_id == shop_id,
            OnlineOrder.id.in_(set(legacy_order_ids.values())),
        ).all()
        legacy_orders = {order.id: order for order in orders}

    for invoice in invoices:
        if invoice.payment_method:
            continue
        if str(invoice.source or "").upper() == "ONLINE_ORDER":
            order = legacy_orders.get(legacy_order_ids.get(invoice.id))
            method = str(getattr(order, "payment_method", "COD") or "COD").upper()
            invoice.payment_method = "ONLINE" if method in {"UPI", "ONLINE"} else "CASH"
        else:
            invoice.payment_method = "CASH"

    return invoices


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

    requested_paid = Decimal(str(data.paid_amount or 0))
    requested_total = Decimal(str(data.total_amount or 0))
    if requested_paid > requested_total + Decimal("0.01"):
        raise HTTPException(
            status_code=400,
            detail="paid_amount cannot exceed total_amount when creating an invoice.",
        )

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
        created_at=datetime.utcnow(),
        due_date=due_date,
        subtotal=float(sub_t2),
        tax=data.tax,
        total_amount=data.total_amount,
        paid_amount=data.paid_amount,
        status="SENT",
        payment_status=PaymentStatus.UNPAID,
        payment_method=_normalize_invoice_payment_method(data.payment_method),
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
    # /create is used for manually created bills. Ignore legacy client defaults
    # such as payment_status=PAID when no money was recorded in paid_amount.
    _normalize_new_invoice_payment_state(invoice)
    db.add(invoice)
    db.flush()
    sale_loss_total = Decimal("0.00")

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

            if product is not None:
                sale_loss_total += _record_below_cost_sale_loss(
                    db=db,
                    shop_id=shop_id,
                    invoice_number=invoice_number,
                    sale_date=inv_date,
                    product=product,
                    quantity=item.quantity,
                    net_sale_amount=line_total,
                )

    tx = UniversalTransaction(
        shop_id=shop_id,
        tx_type="INCOME",
        category="SALE",
        amount=data.paid_amount,
        reference_id=invoice_number,
        description=f"Manual Invoice: {invoice_number}",
        tx_date=_invoice_event_timestamp(invoice),
    )
    db.add(tx)

    try:
        db.flush()
        invoice_events = [
            append_sync_event(db, {
                "event_id": str(uuid.uuid4()),
                "type": "invoice.created",
                "shop_id": shop_id,
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "total_amount": float(invoice.total_amount),
                "paid_amount": float(invoice.paid_amount or 0),
                "payment_status": (
                    invoice.payment_status.value
                    if hasattr(invoice.payment_status, "value")
                    else str(invoice.payment_status)
                ),
                "payment_method": invoice.payment_method,
                "source": "MANUAL_ENTRY",
            })
        ]
        if prepared_line_items:
            invoice_events.append(append_sync_event(db, {
                "event_id": str(uuid.uuid4()),
                "type": "inventory.changed",
                "shop_id": shop_id,
                "reference_type": "MANUAL_INVOICE",
                "reference_id": invoice.invoice_number,
            }))
        db.commit()
        db.refresh(invoice)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create invoice: {str(e)}")

    for event in invoice_events:
        publish_realtime_event(event)

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
        "payment_method": invoice.payment_method,
        "source": invoice.source,
        "invoice_date": str(invoice.invoice_date),
        "due_date": str(invoice.due_date) if invoice.due_date else None,
        "created_at": invoice.created_at.isoformat(),
        "message": "Invoice created successfully.",
        "special_discount_total": float(special_discount_total),
        "sale_loss_total": float(sale_loss_total),
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


@router.get("/sync", include_in_schema=False)
def reject_invoice_sync_get():
    """Make incorrect GET calls to the write-only offline sync route explicit."""
    raise HTTPException(
        status_code=405,
        detail="Invoice sync requires POST with a JSON invoice payload.",
        headers={"Allow": "POST"},
    )


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
        update_event = append_sync_event(db, {
            "event_id": str(uuid.uuid4()),
            "type": "invoice.updated",
            "shop_id": shop_id,
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "total_amount": float(invoice.total_amount or 0),
            "paid_amount": float(invoice.paid_amount or 0),
            "payment_status": (
                invoice.payment_status.value
                if hasattr(invoice.payment_status, "value")
                else str(invoice.payment_status)
            ),
            "status": invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
            "source": invoice.source,
            "change": "invoice_updated",
        })
        db.commit()
        db.refresh(invoice)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update invoice: {str(e)}")
    
    publish_realtime_event(update_event)
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
    deleted_event = {
        "event_id": str(uuid.uuid4()),
        "type": "invoice.deleted",
        "shop_id": shop_id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
    }
    db.delete(invoice)
    try:
        append_sync_event(db, deleted_event)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete invoice: {str(e)}")
    publish_realtime_event(deleted_event)
    return {"message": "Invoice deleted securely."}