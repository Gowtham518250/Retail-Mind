"""Retail Mind owner subscriptions and Cashfree recurring billing."""
import base64
import calendar
import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, date
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_db
from models import User, ShopProfile
from security import owner_only

logger = logging.getLogger(__name__)
router = APIRouter()
CASHFREE_API_VERSION = os.getenv("CASHFREE_API_VERSION", "2025-01-01")

PLANS = {
    "FREE": {"name": "Free Starter", "daily": 0},
    "BASIC": {"name": "Basic", "daily": 7},
    "PRO": {"name": "Pro", "daily": 25},
    "BUSINESS": {"name": "Business", "daily": 75},
}

class CreateSubscriptionBody(BaseModel):
    plan_code: str = Field(min_length=4, max_length=24)
    billing_interval: str = Field(default="MONTHLY", pattern="^(MONTHLY|YEARLY)$")

def _shop_id(owner: dict) -> int:
    return int(owner["user_id"])

def _cashfree_config():
    app_id = (os.getenv("CASHFREE_APP_ID") or "").strip()
    secret = (os.getenv("CASHFREE_SECRET_KEY") or "").strip()
    env = (os.getenv("CASHFREE_ENV") or "sandbox").strip().lower()
    if not app_id or not secret:
        raise HTTPException(status_code=503, detail="Cashfree is not configured on the Retail Mind backend.")
    if env not in {"sandbox", "production"}:
        raise HTTPException(status_code=503, detail="CASHFREE_ENV must be sandbox or production.")
    base = "https://sandbox.cashfree.com/pg" if env == "sandbox" else "https://api.cashfree.com/pg"
    return app_id, secret, base

def _cashfree_headers(app_id, secret, idem=None):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-version": CASHFREE_API_VERSION,
        "x-client-id": app_id,
        "x-client-secret": secret,
    }
    if idem:
        headers["x-idempotency-key"] = idem
    return headers

def _plan_payload(row):
    return {
        "plan_code": row["plan_code"],
        "name": row["name"],
        "monthly_amount_paise": int(row["monthly_amount_paise"]),
        "yearly_amount_paise": int(row["yearly_amount_paise"]),
        "currency": "INR",
        "daily_ai_query_limit": int(row["daily_ai_query_limit"]),
        "features": [str(key).replace("_", " ").title() for key, enabled in (row["features"] or {}).items() if enabled],
        "recommended": row["plan_code"] == "PRO",
    }

@router.get("/api/billing/plans")
def get_billing_plans(db: Session = Depends(get_db), owner: dict = Depends(owner_only)):
    rows = db.execute(text("SELECT * FROM rm_subscription_plans WHERE is_active=TRUE ORDER BY CASE plan_code WHEN 'FREE' THEN 0 WHEN 'BASIC' THEN 1 WHEN 'PRO' THEN 2 ELSE 3 END")).mappings().all()
    return {"plans": [_plan_payload(row) for row in rows]}

@router.get("/api/billing/usage")
def get_ai_usage(db: Session = Depends(get_db), owner: dict = Depends(owner_only)):
    shop_id = _shop_id(owner)
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    subscription = db.execute(text("""
        SELECT s.status, s.current_period_end, s.grace_period_end, p.plan_code, p.name, p.daily_ai_query_limit
        FROM rm_shop_subscriptions s JOIN rm_subscription_plans p ON p.plan_code=s.plan_code
        WHERE s.shop_id=:shop_id
          AND (s.status='ACTIVE' AND (s.current_period_end IS NULL OR s.current_period_end >= NOW())
            OR s.status='GRACE_PERIOD' AND s.current_period_end IS NOT NULL AND s.grace_period_end >= NOW())
        ORDER BY s.created_at DESC LIMIT 1
    """), {"shop_id": shop_id}).mappings().first()
    plan_code = subscription["plan_code"] if subscription else "FREE"
    plan_name = subscription["name"] if subscription else "Free Starter"
    limit = int(subscription["daily_ai_query_limit"]) if subscription else 0
    usage = db.execute(text("SELECT used_count FROM rm_ai_daily_usage WHERE shop_id=:shop AND usage_date=:day"), {"shop": shop_id, "day": today}).first()
    used = int(usage[0]) if usage else 0
    return {"plan_code": plan_code, "plan_name": plan_name, "subscription_status": subscription["status"] if subscription else "FREE", "usage": {"daily_limit": limit, "used": used, "remaining": max(0, limit-used), "resets_at": datetime.combine(today + timedelta(days=1), datetime.min.time()).replace(tzinfo=ZoneInfo("Asia/Kolkata")).isoformat()}}

@router.get("/api/billing/entitlements")
def get_entitlements(db: Session = Depends(get_db), owner: dict = Depends(owner_only)):
    shop_id = _shop_id(owner)
    sub = db.execute(text("""
        SELECT p.plan_code,p.features,p.daily_ai_query_limit,s.status
        FROM rm_shop_subscriptions s JOIN rm_subscription_plans p ON p.plan_code=s.plan_code
        WHERE s.shop_id=:shop AND s.status IN ('ACTIVE','GRACE_PERIOD')
          AND (s.current_period_end IS NULL OR s.current_period_end>=NOW() OR s.grace_period_end>=NOW())
        ORDER BY s.created_at DESC LIMIT 1
    """), {"shop": shop_id}).mappings().first()
    if not sub:
        return {"plan_code": "FREE", "features": {"sales": True, "khata": True, "attendance": True, "basic_inventory": True}, "daily_ai_query_limit": 0}
    return {"plan_code": sub["plan_code"], "features": sub["features"], "daily_ai_query_limit": int(sub["daily_ai_query_limit"]), "status": sub["status"]}

@router.get("/api/billing/subscriptions/current")
def get_current_subscription(db: Session = Depends(get_db), owner: dict = Depends(owner_only)):
    shop_id = _shop_id(owner)
    row = db.execute(text("""
        SELECT s.*, p.name AS plan_name, p.daily_ai_query_limit
        FROM rm_shop_subscriptions s JOIN rm_subscription_plans p ON p.plan_code=s.plan_code
        WHERE s.shop_id=:shop ORDER BY s.created_at DESC LIMIT 1
    """), {"shop": shop_id}).mappings().first()
    if not row:
        return {"plan_code": "FREE", "plan_name": "Free Starter", "status": "FREE", "daily_ai_query_limit": 0}
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k,v in dict(row).items() if k != "subscription_session_id"} | {"subscription_session_id": None}

@router.post("/api/billing/subscriptions")
async def create_subscription(body: CreateSubscriptionBody, db: Session = Depends(get_db), owner: dict = Depends(owner_only)):
    shop_id = _shop_id(owner)
    code = body.plan_code.strip().upper()
    if code not in {"BASIC", "PRO", "BUSINESS"}:
        raise HTTPException(status_code=400, detail="Choose a paid Retail Mind plan.")
    plan = db.execute(text("SELECT * FROM rm_subscription_plans WHERE plan_code=:code AND is_active=TRUE"), {"code": code}).mappings().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    amount = int(plan["monthly_amount_paise"] if body.billing_interval == "MONTHLY" else plan["yearly_amount_paise"])
    if amount <= 0:
        raise HTTPException(status_code=400, detail="This plan cannot be billed.")
    # An active paid mandate must not be silently replaced: doing so can create
    # overlapping recurring mandates. A pending authorization, however, is an
    # abandoned/incomplete checkout and can be cancelled at Cashfree before retry.
    active = db.execute(text("""
        SELECT id, status, plan_code, cancel_at_period_end, current_period_end
        FROM rm_shop_subscriptions
        WHERE shop_id=:shop
          AND status IN ('ACTIVE','GRACE_PERIOD')
          AND (current_period_end IS NULL OR current_period_end >= NOW()
               OR (status='GRACE_PERIOD' AND grace_period_end >= NOW()))
        ORDER BY created_at DESC, id DESC LIMIT 1
    """), {"shop": shop_id}).mappings().first()
    if active:
        raise HTTPException(status_code=409, detail={
            "code": "ACTIVE_SUBSCRIPTION_EXISTS",
            "subscription_id": int(active["id"]),
            "current_plan": active["plan_code"],
            "cancel_at_period_end": bool(active["cancel_at_period_end"]),
            "current_period_end": active["current_period_end"].isoformat() if active["current_period_end"] else None,
            "message": "Your shop already has an active paid subscription. It cannot start a second recurring mandate. Use the subscription management flow to change or cancel the current plan.",
        })

    pending_rows = db.execute(text("""
        SELECT id, status, cashfree_subscription_id, created_at
        FROM rm_shop_subscriptions
        WHERE shop_id=:shop AND status IN ('CREATING','PENDING_AUTH')
        ORDER BY created_at DESC, id DESC
    """), {"shop": shop_id}).mappings().all()
    app_id, secret, base = _cashfree_config()
    for pending in pending_rows:
        # A CREATING row may belong to an in-flight request. Only mark it failed
        # after a generous timeout; never assume Cashfree created a mandate.
        if pending["status"] == "CREATING":
            stale = db.execute(text("""
                UPDATE rm_shop_subscriptions SET status='CREATE_FAILED', updated_at=NOW()
                WHERE id=:id AND status='CREATING' AND created_at < NOW() - INTERVAL '10 minutes'
            """), {"id": pending["id"]})
            db.commit()
            if getattr(stale, "rowcount", 0) == 0:
                raise HTTPException(status_code=409, detail="A subscription checkout is currently being created. Please wait a minute and retry.")
            continue

        cashfree_id = pending["cashfree_subscription_id"]
        if not cashfree_id:
            db.execute(text("UPDATE rm_shop_subscriptions SET status='CANCELLED',cancelled_at=NOW(),updated_at=NOW() WHERE id=:id AND status='PENDING_AUTH'"), {"id": pending["id"]})
            db.commit()
            continue
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                cancel_response = await client.post(
                    f"{base}/subscriptions/{cashfree_id}/manage",
                    headers=_cashfree_headers(app_id, secret, f"rm-retry-cancel-{pending['id']}"),
                    json={"subscription_id": cashfree_id, "action": "CANCEL"},
                )
            if cancel_response.status_code not in (200, 201):
                logger.warning("Could not cancel previous pending Cashfree subscription %s: %s %s", cashfree_id, cancel_response.status_code, cancel_response.text[:500])
                raise HTTPException(status_code=409, detail="A previous checkout is still pending with Cashfree. Please open the existing checkout or cancel it from Subscription Management before trying another plan.")
            db.execute(text("""
                UPDATE rm_shop_subscriptions
                SET status='CANCELLED', cancelled_at=NOW(), updated_at=NOW()
                WHERE id=:id AND status='PENDING_AUTH'
            """), {"id": pending["id"]})
            db.commit()
        except HTTPException:
            raise
        except Exception:
            db.rollback()
            logger.exception("Failed to cancel abandoned pending subscription %s", pending["id"])
            raise HTTPException(status_code=503, detail="Could not safely close the previous pending checkout. Please retry shortly.")

    user = db.query(User).filter(User.id == shop_id, User.user_type == "OWNER", User.is_active == True).first()
    profile = db.query(ShopProfile).filter(ShopProfile.shop_id == shop_id).first()
    if not user:
        raise HTTPException(status_code=403, detail="Only an active shop owner can subscribe.")
    phone = (getattr(profile, "phone", None) or getattr(profile, "contact_person_phone", None) or "").strip()
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10 or len(digits) > 15:
        raise HTTPException(status_code=422, detail="Add a valid shop contact phone number in Shop Profile before subscribing.")
    app_id, secret, base = _cashfree_config()
    local_id = str(uuid.uuid4())
    local_sub_id = f"rm_{shop_id}_{local_id.replace('-', '')[:20]}"
    db.execute(text("""
        INSERT INTO rm_shop_subscriptions
          (shop_id,plan_code,billing_interval,amount_paise,status,cashfree_subscription_id,created_at,updated_at)
        VALUES (:shop,:plan,:interval,:amount,'CREATING',:cfid,NOW(),NOW())
    """), {"shop":shop_id,"plan":code,"interval":body.billing_interval,"amount":amount,"cfid":local_sub_id})
    db.commit()
    amount_rupees = amount / 100
    plan_interval = "MONTH" if body.billing_interval == "MONTHLY" else "YEAR"
    auth_amount = float(os.getenv("CASHFREE_AUTHORIZATION_AMOUNT", "1"))
    payload = {
        "subscription_id": local_sub_id,
        "customer_details": {"customer_name": user.user_name[:100], "customer_email": user.email, "customer_phone": digits[-10:]},
        "plan_details": {
            "plan_name": f"Retail Mind {plan['name']} {body.billing_interval.title()}",
            "plan_type": "PERIODIC",
            "plan_currency": "INR",
            "plan_amount": amount_rupees,
            "plan_max_amount": amount_rupees,
            "plan_max_cycles": 0,
            "plan_interval_type": plan_interval,
            "plan_intervals": 1,
            "plan_note": f"Retail Mind {plan['name']} subscription",
        },
        "authorization_details": {"authorization_amount": auth_amount, "authorization_amount_refund": True},
        "subscription_tags": {"shop_id": str(shop_id), "plan_code": code, "billing_interval": body.billing_interval},
    }
    return_url = (os.getenv("CASHFREE_SUBSCRIPTION_RETURN_URL") or "").strip()
    if return_url:
        payload["subscription_meta"] = {"return_url": return_url}
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(f"{base}/subscriptions", headers=_cashfree_headers(app_id, secret, f"rm-create-{local_id}"), json=payload)
        if response.status_code not in (200, 201):
            logger.error("Cashfree create subscription failed: status=%s body=%s", response.status_code, response.text[:1000])
            db.execute(text("UPDATE rm_shop_subscriptions SET status='CREATE_FAILED',updated_at=NOW() WHERE cashfree_subscription_id=:id"), {"id":local_sub_id})
            db.commit()
            raise HTTPException(status_code=502, detail="Cashfree could not create the subscription. Check backend Cashfree configuration and account permissions.")
        data = response.json()
        session_id = data.get("subscription_session_id")
        cf_id = data.get("subscription_id") or local_sub_id
        if not session_id:
            db.execute(text("UPDATE rm_shop_subscriptions SET status='CREATE_FAILED',updated_at=NOW() WHERE cashfree_subscription_id=:id AND status='CREATING'"), {"id": local_sub_id})
            db.commit()
            raise HTTPException(status_code=502, detail="Cashfree did not return a subscription checkout session. You can safely retry.")
        db.execute(text("UPDATE rm_shop_subscriptions SET status='PENDING_AUTH',subscription_session_id=:session,cashfree_subscription_id=:cfid,updated_at=NOW() WHERE cashfree_subscription_id=:old"), {"session":session_id,"cfid":cf_id,"old":local_sub_id})
        db.commit()
        return {"subscription_id": cf_id, "subscription_session_id": session_id, "environment": os.getenv("CASHFREE_ENV","sandbox").lower(), "status": "PENDING_AUTH"}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Cashfree subscription creation error")
        raise HTTPException(status_code=502, detail="Unable to start Cashfree checkout. Please retry.")

@router.post("/api/billing/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(subscription_id: int, db: Session = Depends(get_db), owner: dict = Depends(owner_only)):
    shop_id = _shop_id(owner)
    row = db.execute(text("SELECT * FROM rm_shop_subscriptions WHERE id=:id AND shop_id=:shop"), {"id":subscription_id,"shop":shop_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    if not row["cashfree_subscription_id"]:
        raise HTTPException(status_code=409, detail="This subscription has no Cashfree mandate to cancel.")
    app_id, secret, base = _cashfree_config()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{base}/subscriptions/{row['cashfree_subscription_id']}/manage", headers=_cashfree_headers(app_id,secret,f"rm-cancel-{row['id']}"), json={"subscription_id":row["cashfree_subscription_id"],"action":"CANCEL"})
        if response.status_code not in (200,201):
            raise HTTPException(status_code=502, detail="Cashfree could not cancel the mandate. Please retry or contact support.")
        db.execute(text("UPDATE rm_shop_subscriptions SET cancel_at_period_end=TRUE,updated_at=NOW() WHERE id=:id"), {"id":subscription_id})
        db.commit()
        return {"success": True, "message": "Cancellation requested. Access remains until the paid period ends."}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Cashfree cancellation failed")
        raise HTTPException(status_code=502, detail="Unable to cancel the Cashfree subscription.")

@router.post("/api/billing/cashfree/webhook")
async def cashfree_subscription_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    signature = request.headers.get("x-webhook-signature", "")
    timestamp = request.headers.get("x-webhook-timestamp", "")
    secret = (os.getenv("CASHFREE_WEBHOOK_SECRET") or os.getenv("CASHFREE_SECRET_KEY") or "").strip()
    if not secret or not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")
    expected = base64.b64encode(hmac.new(secret.encode(), (timestamp + raw.decode("utf-8")).encode(), hashlib.sha256).digest()).decode()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")
    event_type = str(payload.get("type") or payload.get("event_type") or "UNKNOWN")
    event_key = request.headers.get("x-idempotency-key") or hashlib.sha256(raw).hexdigest()
    inserted = db.execute(text("""
        INSERT INTO rm_subscription_webhook_events(event_key,event_type,payload)
        VALUES(:key,:type,CAST(:payload AS jsonb)) ON CONFLICT(event_key) DO NOTHING RETURNING id
    """), {"key":event_key,"type":event_type,"payload":json.dumps(payload)}).first()
    if not inserted:
        db.commit()
        return {"success": True, "duplicate": True}
    data = payload.get("data") or {}
    details = data.get("subscription_details") or data.get("subscription") or {}
    payment = data.get("payment_details") or data.get("payment") or {}
    cf_id = details.get("subscription_id") or data.get("subscription_id") or details.get("cf_subscription_id")
    if cf_id:
        row = db.execute(text("SELECT * FROM rm_shop_subscriptions WHERE cashfree_subscription_id=:id"), {"id":str(cf_id)}).mappings().first()
    else:
        row = None
    if row:
        now = datetime.utcnow()
        if event_type == "SUBSCRIPTION_AUTH_STATUS":
            auth = data.get("authorization_details") or details.get("authorization_details") or {}
            auth_status = str(auth.get("authorization_status") or data.get("authorization_status") or "PENDING").upper()
            db.execute(text("UPDATE rm_shop_subscriptions SET mandate_status=:status,updated_at=NOW() WHERE id=:id"), {"status":auth_status,"id":row["id"]})
        elif event_type == "SUBSCRIPTION_PAYMENT_SUCCESS":
            payment_id = payment.get("cf_payment_id") or payment.get("payment_id") or data.get("cf_payment_id")
            amount_raw = payment.get("payment_amount") or payment.get("amount") or row["amount_paise"] / 100
            amount_paise = int(round(float(amount_raw) * 100))
            inserted_payment = db.execute(text("""
                INSERT INTO rm_subscription_payments(subscription_id,shop_id,cashfree_payment_id,amount_paise,status,payment_type,paid_at)
                VALUES(:sub,:shop,:pid,:amount,'SUCCESS',:payment_type,:paid)
                ON CONFLICT(cashfree_payment_id) DO NOTHING
                RETURNING id
            """), {"sub":row["id"],"shop":row["shop_id"],"pid":str(payment_id) if payment_id else None,"amount":amount_paise,"payment_type":"INITIAL" if row["current_period_start"] is None else "RENEWAL","paid":now}).first()
            if inserted_payment:
                period_start = row["current_period_end"] if row["current_period_end"] and row["current_period_end"] > now else now
                if row["billing_interval"] == "YEARLY":
                    next_year = period_start.year + 1
                    period_end = period_start.replace(year=next_year, day=min(period_start.day, calendar.monthrange(next_year, period_start.month)[1]))
                else:
                    next_month = period_start.month + 1
                    next_year = period_start.year + (1 if next_month > 12 else 0)
                    next_month = 1 if next_month > 12 else next_month
                    period_end = period_start.replace(year=next_year, month=next_month, day=min(period_start.day, calendar.monthrange(next_year, next_month)[1]))
                db.execute(text("""
                    UPDATE rm_shop_subscriptions SET status='ACTIVE',current_period_start=:start,
                        current_period_end=:end,grace_period_end=NULL,mandate_status=COALESCE(mandate_status,'AUTHORIZED'),updated_at=NOW()
                    WHERE id=:id
                """), {"start":period_start,"end":period_end,"id":row["id"]})
        elif event_type == "SUBSCRIPTION_PAYMENT_FAILED":
            if row["current_period_end"] is not None:
                db.execute(text("UPDATE rm_shop_subscriptions SET status='GRACE_PERIOD',grace_period_end=:end,updated_at=NOW() WHERE id=:id"), {"end":now+timedelta(days=3),"id":row["id"]})
            else:
                db.execute(text("UPDATE rm_shop_subscriptions SET status='PAYMENT_FAILED',grace_period_end=NULL,updated_at=NOW() WHERE id=:id"), {"id":row["id"]})
        elif event_type in {"SUBSCRIPTION_PAYMENT_CANCELLED","SUBSCRIPTION_STATUS_CHANGED"}:
            status_value = str(details.get("subscription_status") or data.get("subscription_status") or "").upper()
            if status_value in {"CANCELLED","CANCELED","COMPLETED","EXPIRED"}:
                if row["current_period_end"] and row["current_period_end"] >= now:
                    db.execute(text("UPDATE rm_shop_subscriptions SET cancel_at_period_end=TRUE,updated_at=NOW() WHERE id=:id"), {"id":row["id"]})
                else:
                    db.execute(text("UPDATE rm_shop_subscriptions SET status='CANCELLED',cancelled_at=:now,updated_at=NOW() WHERE id=:id"), {"now":now,"id":row["id"]})
    db.execute(text("UPDATE rm_subscription_webhook_events SET processed_at=NOW() WHERE event_key=:key"), {"key":event_key})
    db.commit()
    return {"success": True}

