import logging
from typing import List, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from db import get_db
from models import User, Customer, Invoice, Payment, PaymentStatus, InvoiceStatus, PaymentMethod
from security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/khata", tags=["Khata & Pending Payments Engine"])


# ==================== SCHEMAS ====================

class PaymentRecordRequest(BaseModel):
    customer_phone: Optional[str] = None
    customer_id: Optional[int] = None
    invoice_id: Optional[int] = None
    amount: float = Field(..., gt=0, description="Payment amount received")
    payment_method: str = Field("CASH", description="Payment method: CASH, UPI, CARD, TRANSFER")
    notes: Optional[str] = None
    idempotency_key: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Stable offline operation key; retrying it must not duplicate a payment.",
    )

class DeadlineUpdateRequest(BaseModel):
    customer_phone: Optional[str] = None
    customer_id: Optional[int] = None
    due_date: str = Field(..., description="Due date in YYYY-MM-DD format")


# ==================== ENDPOINTS ====================

@router.get("/pending-summary")
def get_khata_pending_summary(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregated summary of all pending udhar/khata balances for the shop owner.
    """
    try:
        today = date.today()
        week_end = today + timedelta(days=7)

        # Get all non-settled invoices for this user
        open_invoices = db.query(Invoice).filter(
            Invoice.user_id == user_id,
            Invoice.payment_status.in_([PaymentStatus.UNPAID, PaymentStatus.PARTIAL, PaymentStatus.OVERDUE]),
            Invoice.status != InvoiceStatus.CANCELLED
        ).all()

        total_outstanding = 0.0
        total_overdue = 0.0
        pending_customer_phones = set()
        overdue_customer_phones = set()
        due_this_week = 0.0

        for inv in open_invoices:
            balance = float(inv.total_amount or 0.0) - float(inv.paid_amount or 0.0)
            if balance <= 0.01:
                continue

            total_outstanding += balance
            phone_key = inv.customer_phone or str(inv.customer_id or "unknown")
            pending_customer_phones.add(phone_key)

            # Check due date
            inv_due = inv.due_date
            if inv_due:
                if isinstance(inv_due, str):
                    try:
                        inv_due = datetime.strptime(inv_due, "%Y-%m-%d").date()
                    except ValueError:
                        inv_due = None

            if inv_due and inv_due < today:
                total_overdue += balance
                overdue_customer_phones.add(phone_key)
            elif inv_due and today <= inv_due <= week_end:
                due_this_week += balance

        # Calculate payments collected today
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        collected_today_query = db.query(func.coalesce(func.sum(Payment.amount), 0)).join(Invoice).filter(
            Invoice.user_id == user_id,
            Payment.payment_date >= today_start,
            Payment.payment_date <= today_end
        ).scalar()

        return {
            "success": True,
            "total_outstanding": round(total_outstanding, 2),
            "total_overdue": round(total_overdue, 2),
            "pending_customers_count": len(pending_customer_phones),
            "overdue_customers_count": len(overdue_customer_phones),
            "due_this_week": round(due_this_week, 2),
            "collected_today": round(float(collected_today_query or 0.0), 2)
        }
    except Exception as e:
        logger.error(f"Error fetching khata summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-customers")
def get_pending_khata_customers(
    search: Optional[str] = Query(None, description="Search by name or phone"),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get itemized list of ALL customers with pending balances (Udhar/Khata).
    """
    try:
        today = date.today()

        # Query all non-settled invoices
        query = db.query(Invoice).filter(
            Invoice.user_id == user_id,
            Invoice.payment_status.in_([PaymentStatus.UNPAID, PaymentStatus.PARTIAL, PaymentStatus.OVERDUE]),
            Invoice.status != InvoiceStatus.CANCELLED
        )

        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Invoice.customer_name.ilike(search_term),
                    Invoice.customer_phone.ilike(search_term)
                )
            )

        invoices = query.order_by(Invoice.invoice_date.desc()).all()

        # Group by customer phone / name
        customer_map = {}
        for inv in invoices:
            balance = float(inv.total_amount or 0.0) - float(inv.paid_amount or 0.0)
            if balance <= 0.01:
                continue

            phone = (inv.customer_phone or "").strip()
            name = (inv.customer_name or "Walk-in Customer").strip()
            key = phone if phone else f"name_{name}"

            if key not in customer_map:
                customer_map[key] = {
                    "customer_id": inv.customer_id,
                    "customer_name": name,
                    "customer_phone": phone,
                    "whatsapp_number": phone,
                    "total_balance": 0.0,
                    "overdue_amount": 0.0,
                    "is_overdue": False,
                    "days_overdue": 0,
                    "earliest_due_date": None,
                    "invoices": []
                }

            c_entry = customer_map[key]
            c_entry["total_balance"] += balance

            # Parse due date
            inv_due = inv.due_date
            if inv_due and isinstance(inv_due, str):
                try:
                    inv_due = datetime.strptime(inv_due, "%Y-%m-%d").date()
                except ValueError:
                    inv_due = None

            is_inv_overdue = False
            inv_days_overdue = 0
            if inv_due and inv_due < today:
                is_inv_overdue = True
                inv_days_overdue = (today - inv_due).days
                c_entry["overdue_amount"] += balance
                c_entry["is_overdue"] = True
                if inv_days_overdue > c_entry["days_overdue"]:
                    c_entry["days_overdue"] = inv_days_overdue

            if inv_due:
                due_str = inv_due.strftime("%Y-%m-%d")
                if not c_entry["earliest_due_date"] or due_str < c_entry["earliest_due_date"]:
                    c_entry["earliest_due_date"] = due_str

            c_entry["invoices"].append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "invoice_date": str(inv.invoice_date or ""),
                "due_date": str(inv.due_date or ""),
                "total_amount": float(inv.total_amount or 0.0),
                "paid_amount": float(inv.paid_amount or 0.0),
                "balance": round(balance, 2),
                "payment_status": str(inv.payment_status.value if hasattr(inv.payment_status, 'value') else inv.payment_status),
                "is_overdue": is_inv_overdue,
                "days_overdue": inv_days_overdue,
                "notes": inv.notes
            })

        # Format result list
        results = []
        for c in customer_map.values():
            c["total_balance"] = round(c["total_balance"], 2)
            c["overdue_amount"] = round(c["overdue_amount"], 2)
            results.append(c)

        # Sort by overdue status first, then highest balance
        results.sort(key=lambda x: (not x["is_overdue"], -x["total_balance"]))

        return {
            "success": True,
            "count": len(results),
            "customers": results
        }
    except Exception as e:
        logger.error(f"Error fetching pending khata customers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record-payment")
def record_khata_payment(
    payload: PaymentRecordRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record a payment against pending invoices safely and idempotently."""
    try:
        payment_amount = float(payload.amount)
        if payment_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Payment amount must be greater than zero",
            )

        customer_phone = (payload.customer_phone or "").strip()
        customer_id = (
            payload.customer_id
            if payload.customer_id and payload.customer_id > 0
            else None
        )
        idempotency_key = (payload.idempotency_key or "").strip() or None

        # Retry protection. Payment has no direct user_id, so scope through Invoice.
        if idempotency_key:
            existing_payment = (
                db.query(Payment)
                .join(Invoice, Payment.invoice_id == Invoice.id)
                .filter(
                    Invoice.user_id == user_id,
                    Payment.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing_payment:
                existing_invoice = (
                    db.query(Invoice)
                    .filter(
                        Invoice.id == existing_payment.invoice_id,
                        Invoice.user_id == user_id,
                    )
                    .first()
                )
                return {
                    "success": True,
                    "duplicate": True,
                    "payment_id": existing_payment.id,
                    "invoice_id": existing_payment.invoice_id,
                    "message": "Payment already recorded (idempotent retry).",
                    "applied_amount": float(existing_payment.amount or 0),
                    "unapplied_change": 0.0,
                    "settled_invoices": (
                        [existing_invoice.invoice_number]
                        if existing_invoice is not None else []
                    ),
                    "idempotency_key": idempotency_key,
                }

        # Resolve invoices only within this authenticated shop.
        if payload.invoice_id:
            invoices = (
                db.query(Invoice)
                .filter(
                    Invoice.id == payload.invoice_id,
                    Invoice.user_id == user_id,
                    Invoice.status != InvoiceStatus.CANCELLED,
                )
                .with_for_update()
                .all()
            )
        elif customer_phone:
            invoices = (
                db.query(Invoice)
                .filter(
                    Invoice.user_id == user_id,
                    Invoice.customer_phone == customer_phone,
                    Invoice.payment_status.in_(
                        [PaymentStatus.UNPAID, PaymentStatus.PARTIAL, PaymentStatus.OVERDUE]
                    ),
                    Invoice.status != InvoiceStatus.CANCELLED,
                )
                .order_by(Invoice.invoice_date.asc(), Invoice.id.asc())
                .with_for_update()
                .all()
            )
        elif customer_id:
            invoices = (
                db.query(Invoice)
                .filter(
                    Invoice.user_id == user_id,
                    Invoice.customer_id == customer_id,
                    Invoice.payment_status.in_(
                        [PaymentStatus.UNPAID, PaymentStatus.PARTIAL, PaymentStatus.OVERDUE]
                    ),
                    Invoice.status != InvoiceStatus.CANCELLED,
                )
                .order_by(Invoice.invoice_date.asc(), Invoice.id.asc())
                .with_for_update()
                .all()
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide customer_phone, customer_id, or invoice_id",
            )

        if not invoices:
            raise HTTPException(
                status_code=404,
                detail="No pending invoices found for this record",
            )

        # Explicit invoice settlement must not silently overpay.
        if payload.invoice_id:
            balance = max(
                0.0,
                float(invoices[0].total_amount or 0.0)
                - float(invoices[0].paid_amount or 0.0),
            )
            if payment_amount > balance + 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Payment exceeds invoice balance. "
                        f"Outstanding: ₹{balance:.2f}, "
                        f"Received: ₹{payment_amount:.2f}"
                    ),
                )

        remaining = payment_amount
        applied_total = 0.0
        settled_invoices = []

        p_method_str = (payload.payment_method or "CASH").upper().strip()
        p_method_enum = PaymentMethod.__members__.get(
            p_method_str,
            PaymentMethod.CASH,
        )

        for inv in invoices:
            if remaining <= 0.01:
                break

            balance = max(
                0.0,
                float(inv.total_amount or 0.0)
                - float(inv.paid_amount or 0.0),
            )
            if balance <= 0.01:
                continue

            apply_amt = min(remaining, balance)
            new_paid = round(float(inv.paid_amount or 0.0) + apply_amt, 2)
            inv.paid_amount = new_paid

            if new_paid >= float(inv.total_amount or 0.0) - 0.01:
                inv.paid_amount = round(float(inv.total_amount or 0.0), 2)
                inv.payment_status = PaymentStatus.PAID
                inv.status = InvoiceStatus.PAID
            else:
                inv.payment_status = PaymentStatus.PARTIAL
                inv.status = InvoiceStatus.PARTIAL

            # One user action may FIFO-settle multiple invoices.
            # Only its first Payment row carries the operation key.
            db.add(
                Payment(
                    invoice_id=inv.id,
                    payment_method=p_method_enum,
                    amount=round(apply_amt, 2),
                    notes=payload.notes or "Khata Payment Settlement",
                    idempotency_key=idempotency_key if not settled_invoices else None,
                )
            )

            remaining = round(remaining - apply_amt, 2)
            applied_total = round(applied_total + apply_amt, 2)
            settled_invoices.append(inv.invoice_number)

        if applied_total <= 0.01:
            raise HTTPException(
                status_code=400,
                detail="No outstanding invoice balance was available for this payment.",
            )

        db.commit()

        return {
            "success": True,
            "duplicate": False,
            "message": f"Payment of ₹{payment_amount:.2f} recorded successfully",
            "applied_amount": applied_total,
            "unapplied_change": max(0.0, round(payment_amount - applied_total, 2)),
            "settled_invoices": settled_invoices,
            "idempotency_key": idempotency_key,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error("Error recording khata payment: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Payment transaction failed safely.",
        )


@router.post("/update-deadline")
def update_khata_deadline(
    payload: DeadlineUpdateRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set or update payment deadline date for customer's pending invoices.
    """
    try:
        try:
            target_date = datetime.strptime(payload.due_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        query = db.query(Invoice).filter(
            Invoice.user_id == user_id,
            Invoice.payment_status.in_([PaymentStatus.UNPAID, PaymentStatus.PARTIAL, PaymentStatus.OVERDUE]),
            Invoice.status != InvoiceStatus.CANCELLED
        )

        if payload.customer_phone:
            query = query.filter(Invoice.customer_phone == payload.customer_phone)
        elif payload.customer_id:
            query = query.filter(Invoice.customer_id == payload.customer_id)
        else:
            raise HTTPException(status_code=400, detail="Must specify customer_phone or customer_id")

        invoices = query.all()
        if not invoices:
            raise HTTPException(status_code=404, detail="No pending invoices found for customer")

        for inv in invoices:
            inv.due_date = target_date

        db.commit()

        return {
            "success": True,
            "message": f"Updated due date to {target_date} for {len(invoices)} pending invoice(s)",
            "due_date": str(target_date)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating deadline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whatsapp-reminders")
def get_whatsapp_batch_reminders(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of overdue customers with preformatted WhatsApp reminder messages.
    """
    try:
        shop_user = db.query(User).filter(User.id == user_id).first()
        shop_name = shop_user.user_name if shop_user else "Store"

        pending_resp = get_pending_khata_customers(search=None, user_id=user_id, db=db)
        customers = pending_resp.get("customers", [])

        reminders = []
        for c in customers:
            if c["total_balance"] > 0:
                phone = c["customer_phone"]
                name = c["customer_name"]
                bal = c["total_balance"]
                due = c["earliest_due_date"] or "As soon as possible"

                msg = (
                    f"Dear {name},\n\n"
                    f"This is a friendly reminder from *{shop_name}* regarding your pending balance of *₹{bal:.2f}*.\n"
                    f"Due Date: {due}\n\n"
                    f"Kindly settle your payment at your earliest convenience. Thank you!"
                )

                reminders.append({
                    "customer_name": name,
                    "customer_phone": phone,
                    "balance": bal,
                    "is_overdue": c["is_overdue"],
                    "days_overdue": c["days_overdue"],
                    "message": msg
                })

        return {
            "success": True,
            "count": len(reminders),
            "reminders": reminders
        }
    except Exception as e:
        logger.error(f"Error building whatsapp reminders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))