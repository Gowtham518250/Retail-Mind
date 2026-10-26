"""
UPI Ledger Service
Track detected UPI events separately from confirmed collections.
Only CONFIRM records contribute to collected-payment totals.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException

from models import UpiLedger, UpiStatus


def _normalize_reference(value: Optional[str]) -> Optional[str]:
    """Normalize bank/UPI reference formatting across SMS and notifications."""
    normalized = "".join(ch for ch in (value or "").strip().upper() if ch.isalnum())
    if len(normalized) < 4 or normalized in {"NA", "NAN", "NONE", "NULL", "UNKNOWN", "NOTAVAILABLE"}:
        return None
    return normalized


def _same_upi_payment(existing, *, shop_id: int, invoice_id: int, amount: Decimal, upi_id: str) -> bool:
    try:
        old_amount = Decimal(str(existing.amount))
    except (TypeError, ValueError):
        return False
    old_upi_id = (existing.upi_id or "").strip().casefold()
    new_upi_id = (upi_id or "").strip().casefold()
    return (
        int(existing.shop_id or 0) == int(shop_id)
        and int(existing.invoice_id or 0) == int(invoice_id)
        and abs(old_amount - amount) < Decimal("0.01")
        and (not old_upi_id or not new_upi_id or old_upi_id == new_upi_id)
    )


def _status_total(
    db: Session,
    shop_id: int,
    status: UpiStatus,
    *,
    day: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Decimal:
    query = db.query(func.sum(UpiLedger.amount)).filter(
        UpiLedger.shop_id == shop_id,
        UpiLedger.status == status,
    )
    if day is not None:
        query = query.filter(func.date(UpiLedger.payment_date) == day)
    if start_date is not None:
        query = query.filter(UpiLedger.payment_date >= start_date)
    if end_date is not None:
        query = query.filter(UpiLedger.payment_date < end_date)
    return query.scalar() or Decimal("0")


def _status_count(
    db: Session,
    shop_id: int,
    status: UpiStatus,
    *,
    day: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> int:
    query = db.query(func.count(UpiLedger.id)).filter(
        UpiLedger.shop_id == shop_id,
        UpiLedger.status == status,
    )
    if day is not None:
        query = query.filter(func.date(UpiLedger.payment_date) == day)
    if start_date is not None:
        query = query.filter(UpiLedger.payment_date >= start_date)
    if end_date is not None:
        query = query.filter(UpiLedger.payment_date < end_date)
    return int(query.scalar() or 0)


class UpiLedgerService:
    @staticmethod
    def record_upi_payment(
        db: Session,
        shop_id: int,
        invoice_id: int,
        upi_id: str,
        amount: Decimal,
        customer_upi: str = None,
        upi_reference: str = None,
    ) -> dict:
        """Record a referenced receipt idempotently as pending reconciliation.

        A notification without a usable bank/UPI reference is only a candidate;
        do not write it as a financial ledger row until a merchant verifies it.
        """
        try:
            normalized_amount = Decimal(str(amount))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Invalid payment amount.")
        if not normalized_amount.is_finite() or normalized_amount <= Decimal("0"):
            raise HTTPException(status_code=422, detail="Payment amount must be positive.")

        reference = _normalize_reference(upi_reference)
        if reference is None:
            return {
                "ledger_id": None,
                "status": "needs_confirmation",
                "recorded": False,
                "duplicate": False,
                "reason": "missing_transaction_reference",
                "amount": float(normalized_amount),
            }

        existing = db.query(UpiLedger).filter_by(upi_reference=reference).first()
        if existing is not None:
            if not _same_upi_payment(
                existing,
                shop_id=shop_id,
                invoice_id=invoice_id,
                amount=normalized_amount,
                upi_id=upi_id,
            ):
                raise HTTPException(
                    status_code=409,
                    detail="This UPI reference already exists with different payment details. Review it manually.",
                )
            return {
                "ledger_id": existing.id,
                "status": "duplicate",
                "recorded": True,
                "duplicate": True,
                "amount": float(normalized_amount),
            }

        ledger_entry = UpiLedger(
            shop_id=shop_id,
            invoice_id=invoice_id,
            upi_id=upi_id,
            amount=normalized_amount,
            customer_upi=customer_upi,
            upi_reference=reference,
            status=UpiStatus.PENDING,
        )
        db.add(ledger_entry)
        try:
            db.commit()
        except IntegrityError:
            # Concurrent replays can both pass the initial lookup. The unique
            # reference constraint remains the final guard; reread after rollback.
            db.rollback()
            raced = db.query(UpiLedger).filter_by(upi_reference=reference).first()
            if raced is not None and _same_upi_payment(
                raced,
                shop_id=shop_id,
                invoice_id=invoice_id,
                amount=normalized_amount,
                upi_id=upi_id,
            ):
                return {
                    "ledger_id": raced.id,
                    "status": "duplicate",
                    "recorded": True,
                    "duplicate": True,
                    "amount": float(normalized_amount),
                }
            raise HTTPException(
                status_code=409,
                detail="This UPI reference was recorded concurrently with conflicting details.",
            )
        return {
            "ledger_id": ledger_entry.id,
            "status": "recorded",
            "recorded": True,
            "duplicate": False,
            "amount": float(normalized_amount),
        }

    @staticmethod
    def confirm_upi_payment(db: Session, upi_reference: str) -> bool:
        """Confirm a pending ledger item; keep this operation idempotent."""
        reference = _normalize_reference(upi_reference)
        if reference is None:
            return False
        entry = db.query(UpiLedger).filter_by(upi_reference=reference).first()
        if entry is None:
            return False
        if entry.status == UpiStatus.CONFIRM:
            return True
        if entry.status != UpiStatus.PENDING:
            # Failed/refunded entries must not be silently resurrected.
            return False
        entry.status = UpiStatus.CONFIRM
        db.commit()
        return True

    @staticmethod
    def get_today_upi_summary(db: Session, shop_id: int) -> dict:
        """Return confirmed collections and the other statuses separately."""
        today = date.today()
        confirmed_total = _status_total(db, shop_id, UpiStatus.CONFIRM, day=today)
        pending_total = _status_total(db, shop_id, UpiStatus.PENDING, day=today)
        failed_total = _status_total(db, shop_id, UpiStatus.FAILED, day=today)
        refunded_total = _status_total(db, shop_id, UpiStatus.REFUND, day=today)

        pending_count = _status_count(db, shop_id, UpiStatus.PENDING, day=today)
        confirmed_count = _status_count(db, shop_id, UpiStatus.CONFIRM, day=today)
        failed_count = _status_count(db, shop_id, UpiStatus.FAILED, day=today)
        refunded_count = _status_count(db, shop_id, UpiStatus.REFUND, day=today)

        return {
            # Backwards-compatible key now means collected/confirmed funds only.
            "today_upi_total": float(confirmed_total),
            "confirmed_upi_total": float(confirmed_total),
            "pending_upi_total": float(pending_total),
            "failed_upi_total": float(failed_total),
            "refunded_upi_total": float(refunded_total),
            "pending_transactions": pending_count,
            "confirmed_transactions": confirmed_count,
            "failed_transactions": failed_count,
            "refunded_transactions": refunded_count,
            "unmatched_count": pending_count,
        }

    @staticmethod
    def get_upi_by_id(db: Session, shop_id: int) -> dict:
        """Break down today's confirmed collections by the receiving UPI ID."""
        today = date.today()
        results = db.query(
            UpiLedger.upi_id,
            func.sum(UpiLedger.amount).label("total"),
            func.count(UpiLedger.id).label("count"),
        ).filter(
            UpiLedger.shop_id == shop_id,
            func.date(UpiLedger.payment_date) == today,
            UpiLedger.status == UpiStatus.CONFIRM,
        ).group_by(UpiLedger.upi_id).all()

        breakdown = []
        for upi_id, total, count in results:
            breakdown.append({
                "upi_id": upi_id,
                "amount": float(total or 0),
                "transaction_count": int(count or 0),
            })
        return {"upi_breakdown": breakdown}

    @staticmethod
    def get_unmatched_payments(db: Session, shop_id: int, limit: int = 10) -> list:
        """List pending transactions requiring reconciliation."""
        entries = db.query(UpiLedger).filter(
            UpiLedger.shop_id == shop_id,
            UpiLedger.status == UpiStatus.PENDING,
        ).order_by(UpiLedger.payment_date.desc()).limit(limit).all()
        return [{
            "id": entry.id,
            "upi_id": entry.upi_id,
            "customer_upi": entry.customer_upi,
            "amount": float(entry.amount),
            "payment_date": entry.payment_date.isoformat(),
            "upi_reference": entry.upi_reference,
            "invoice_id": entry.invoice_id,
        } for entry in entries]

    @staticmethod
    def get_monthly_upi_report(db: Session, shop_id: int, year: int, month: int) -> dict:
        """Report confirmed collections separately from pending, failed, and refunds."""
        # Use datetimes for DateTime column comparisons so database drivers
        # do not need to coerce a date-only bound into a timestamp.
        start_date = datetime(year, month, 1)
        end_date = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        confirmed_total = _status_total(
            db, shop_id, UpiStatus.CONFIRM,
            start_date=start_date, end_date=end_date,
        )
        pending_total = _status_total(
            db, shop_id, UpiStatus.PENDING,
            start_date=start_date, end_date=end_date,
        )
        failed_total = _status_total(
            db, shop_id, UpiStatus.FAILED,
            start_date=start_date, end_date=end_date,
        )
        refunded_total = _status_total(
            db, shop_id, UpiStatus.REFUND,
            start_date=start_date, end_date=end_date,
        )

        confirmed_count = _status_count(
            db, shop_id, UpiStatus.CONFIRM,
            start_date=start_date, end_date=end_date,
        )
        pending_count = _status_count(
            db, shop_id, UpiStatus.PENDING,
            start_date=start_date, end_date=end_date,
        )
        failed_count = _status_count(
            db, shop_id, UpiStatus.FAILED,
            start_date=start_date, end_date=end_date,
        )
        refunded_count = _status_count(
            db, shop_id, UpiStatus.REFUND,
            start_date=start_date, end_date=end_date,
        )

        return {
            "period": f"{month}/{year}",
            # Existing monthly total/count now report confirmed collections only.
            "total_upi": float(confirmed_total),
            "transaction_count": confirmed_count,
            "avg_transaction": float(confirmed_total / confirmed_count) if confirmed_count > 0 else 0,
            "pending_upi_total": float(pending_total),
            "failed_upi_total": float(failed_total),
            "refunded_upi_total": float(refunded_total),
            "pending_transactions": pending_count,
            "failed_transactions": failed_count,
            "refunded_transactions": refunded_count,
        }
