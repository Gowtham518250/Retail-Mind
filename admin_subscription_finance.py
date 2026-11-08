"""Admin-only subscription revenue and cash-collection analytics.

Protects platform financial data with a dedicated server-side admin key.
Never expose these endpoints to shop-owner/customer tokens.
"""
import hmac
import os
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_db

def money(value):
    return round(int(value or 0) / 100, 2)


router = APIRouter(prefix="/api/admin/subscription-finance", tags=["Admin Subscription Finance"])


def require_platform_admin(x_admin_api_key: Optional[str] = Header(default=None, alias="X-Admin-API-Key")):
    configured = (os.getenv("RETAILMIND_ADMIN_API_KEY") or "").strip()
    if not configured:
        raise HTTPException(status_code=503, detail="Platform admin access is not configured.")
    supplied = (x_admin_api_key or "").strip()
    if not supplied or not hmac.compare_digest(supplied, configured):
        raise HTTPException(status_code=403, detail="Platform administrator access required.")
    return True


@router.get("/overview")
def subscription_finance_overview(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    _admin: bool = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Actual successful Cashfree collections plus current subscription KPIs."""
    today = date.today()
    end = end_date or today
    start = start_date or (end - timedelta(days=29))
    if start > end:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    if (end - start).days > 366:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 367 days.")

    params = {"start": start, "end_exclusive": end + timedelta(days=1)}
    totals = db.execute(text("""
        SELECT
          COALESCE(SUM(amount_paise) FILTER (
            WHERE status='SUCCESS' AND paid_at >= :start AND paid_at < :end_exclusive
          ), 0)::bigint AS collected_paise,
          COUNT(*) FILTER (
            WHERE status='SUCCESS' AND paid_at >= :start AND paid_at < :end_exclusive
          )::bigint AS successful_payment_count,
          COUNT(*) FILTER (
            WHERE status IN ('FAILED','PAYMENT_FAILED')
              AND created_at >= :start AND created_at < :end_exclusive
          )::bigint AS failed_payment_count,
          COUNT(*) FILTER (
            WHERE status='SUCCESS' AND payment_type='INITIAL'
              AND paid_at >= :start AND paid_at < :end_exclusive
          )::bigint AS initial_payment_count,
          COUNT(*) FILTER (
            WHERE status='SUCCESS' AND payment_type='RENEWAL'
              AND paid_at >= :start AND paid_at < :end_exclusive
          )::bigint AS renewal_payment_count
        FROM rm_subscription_payments
    """), params).mappings().one()

    current = db.execute(text("""
        SELECT
          COUNT(DISTINCT shop_id) FILTER (WHERE status='ACTIVE'
            AND (current_period_end IS NULL OR current_period_end >= NOW()))::bigint AS active_subscriptions,
          COUNT(DISTINCT shop_id) FILTER (WHERE status='GRACE_PERIOD'
            AND grace_period_end >= NOW())::bigint AS grace_period_subscriptions,
          COUNT(*) FILTER (WHERE status IN ('CANCELLED','EXPIRED'))::bigint AS cancelled_subscriptions,
          COALESCE(SUM(
            CASE WHEN status='ACTIVE' AND (current_period_end IS NULL OR current_period_end >= NOW())
              THEN CASE WHEN billing_interval='YEARLY' THEN amount_paise / 12.0 ELSE amount_paise END
              ELSE 0 END
          ),0)::bigint AS estimated_mrr_paise
        FROM rm_shop_subscriptions
    """)).mappings().one()

    new_subs = db.execute(text("""
        SELECT COUNT(*)::bigint AS count
        FROM rm_shop_subscriptions
        WHERE created_at >= :start AND created_at < :end_exclusive
          AND status NOT IN ('CREATE_FAILED')
    """), params).mappings().one()

    plans = db.execute(text("""
        SELECT p.plan_code, p.name,
          COUNT(DISTINCT s.shop_id) FILTER (
            WHERE s.status='ACTIVE' AND (s.current_period_end IS NULL OR s.current_period_end >= NOW())
          )::bigint AS active_subscribers,
          COALESCE(SUM(pay.amount_paise) FILTER (
            WHERE pay.status='SUCCESS' AND pay.paid_at >= :start AND pay.paid_at < :end_exclusive
          ),0)::bigint AS collected_paise
        FROM rm_subscription_plans p
        LEFT JOIN rm_shop_subscriptions s ON s.plan_code=p.plan_code
        LEFT JOIN rm_subscription_payments pay ON pay.subscription_id=s.id
        GROUP BY p.plan_code,p.name
        ORDER BY p.plan_code
    """), params).mappings().all()

    daily = db.execute(text("""
        SELECT paid_at::date AS day, COALESCE(SUM(amount_paise),0)::bigint AS collected_paise,
               COUNT(*)::bigint AS payment_count
        FROM rm_subscription_payments
        WHERE status='SUCCESS' AND paid_at >= :start AND paid_at < :end_exclusive
        GROUP BY paid_at::date ORDER BY day
    """), params).mappings().all()

    return {
        "currency": "INR",
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "revenue": {
            "collected": money(totals["collected_paise"]),
            "collected_paise": int(totals["collected_paise"] or 0),
            "successful_payments": int(totals["successful_payment_count"] or 0),
            "initial_payments": int(totals["initial_payment_count"] or 0),
            "renewal_payments": int(totals["renewal_payment_count"] or 0),
            "failed_payments": int(totals["failed_payment_count"] or 0),
            "estimated_mrr": money(current["estimated_mrr_paise"]),
            "estimated_arr": money(int(current["estimated_mrr_paise"] or 0) * 12),
        },
        "subscriptions": {
            "active": int(current["active_subscriptions"] or 0),
            "grace_period": int(current["grace_period_subscriptions"] or 0),
            "cancelled_or_expired_all_time": int(current["cancelled_subscriptions"] or 0),
            "new_in_period": int(new_subs["count"] or 0),
        },
        "by_plan": [{
            "plan_code": row["plan_code"],
            "plan_name": row["name"],
            "active_subscribers": int(row["active_subscribers"] or 0),
            "collected": money(row["collected_paise"]),
        } for row in plans],
        "daily_collections": [{
            "date": row["day"].isoformat(),
            "collected": money(row["collected_paise"]),
            "successful_payments": int(row["payment_count"] or 0),
        } for row in daily],
        "accounting_notes": {
            "basis": "Cashfree-confirmed successful subscription payments only",
            "excludes": ["pending mandates", "pending checkouts", "failed payments"],
            "refunds_and_platform_operating_expenses": "Not netted; current subscription schema has no reconciled refund or platform-expense ledger.",
            "mrr": "Estimated from currently active paid subscriptions; annual plans are divided by 12.",
        },
    }


@router.get("/payments")
def subscription_payment_ledger(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: bool = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=29))
    if start > end or (end - start).days > 366:
        raise HTTPException(status_code=422, detail="Invalid date range (maximum 367 days).")
    rows = db.execute(text("""
        SELECT pay.id, pay.shop_id, pay.subscription_id, pay.cashfree_payment_id,
               pay.amount_paise, pay.status, pay.payment_type, pay.paid_at,
               sub.plan_code, sub.billing_interval
        FROM rm_subscription_payments pay
        JOIN rm_shop_subscriptions sub ON sub.id=pay.subscription_id
        WHERE pay.created_at >= :start AND pay.created_at < :end_exclusive
        ORDER BY COALESCE(pay.paid_at,pay.created_at) DESC, pay.id DESC
        LIMIT :limit OFFSET :offset
    """), {"start": start, "end_exclusive": end + timedelta(days=1), "limit": limit, "offset": offset}).mappings().all()
    return {"items": [{
        "payment_id": row["id"], "shop_id": row["shop_id"],
        "subscription_id": row["subscription_id"], "cashfree_payment_id": row["cashfree_payment_id"],
        "amount": money(row["amount_paise"]), "currency": "INR", "status": row["status"],
        "payment_type": row["payment_type"], "paid_at": row["paid_at"].isoformat() if row["paid_at"] else None,
        "plan_code": row["plan_code"], "billing_interval": row["billing_interval"],
    } for row in rows], "limit": limit, "offset": offset}
