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
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
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
    plan_code: str = Field(min_length=3, max_length=24)
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

def _cashfree_activation_date(period_end: datetime) -> str:
    """Cashfree ACTIVATE accepts a date; convert the UTC DB timestamp to IST."""
    if period_end is None:
        raise ValueError("A billing period end is required to reactivate a scheduled cancellation.")
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=timezone.utc)
    return period_end.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()


def _cashfree_plan_id(plan_code: str, billing_interval: str, amount_paise: int) -> str:
    """Return a stable, price-versioned Cashfree plan identifier."""
    interval = "monthly" if billing_interval == "MONTHLY" else "yearly"
    return f"rm_{plan_code.strip().lower()}_{interval}_{int(amount_paise)}"


async def _ensure_cashfree_plan(
    client: httpx.AsyncClient,
    *,
    base: str,
    app_id: str,
    secret: str,
    plan_code: str,
    plan_name: str,
    billing_interval: str,
    amount_paise: int,
) -> str:
    """Create or reuse the remote Cashfree plan needed by CHANGE_PLAN.

    Cashfree's CHANGE_PLAN action requires a provider-side plan_id. The normal
    checkout currently creates subscriptions using inline plan_details, so
    create a deterministic provider plan only when an existing mandate needs
    to be moved to a different tier.
    """
    amount = round(int(amount_paise) / 100, 2)
    plan_id = _cashfree_plan_id(plan_code, billing_interval, amount_paise)
    headers = _cashfree_headers(app_id, secret)

    fetched = await client.get(f"{base}/plans/{plan_id}", headers=headers)
    if fetched.status_code == 200:
        return plan_id
    if fetched.status_code != 404:
        logger.error(
            "Cashfree plan lookup failed: plan_id=%s status=%s body=%s",
            plan_id, fetched.status_code, fetched.text[:500],
        )
        raise HTTPException(
            status_code=502,
            detail="Unable to verify the target recurring plan with Cashfree. Please retry.",
        )

    interval_type = "MONTH" if billing_interval == "MONTHLY" else "YEAR"
    payload = {
        "plan_id": plan_id,
        "plan_name": f"Retail Mind {plan_name} {billing_interval.title()}",
        "plan_type": "PERIODIC",
        "plan_currency": "INR",
        "plan_recurring_amount": amount,
        "plan_max_amount": amount,
        "plan_max_cycles": 0,
        "plan_intervals": 1,
        "plan_interval_type": interval_type,
        "plan_note": f"Retail Mind {plan_name} subscription",
    }
    created = await client.post(
        f"{base}/plans",
        headers=_cashfree_headers(app_id, secret, f"rm-plan-{plan_id}"),
        json=payload,
    )
    if created.status_code in (200, 201):
        return plan_id

    # A concurrent request or a previous timeout may have created the plan.
    # Confirm it exists before treating the create response as a failure.
    if created.status_code in (409, 422):
        verified = await client.get(f"{base}/plans/{plan_id}", headers=headers)
        if verified.status_code == 200:
            return plan_id

    logger.error(
        "Cashfree plan creation failed: plan_id=%s status=%s body=%s",
        plan_id, created.status_code, created.text[:700],
    )
    raise HTTPException(
        status_code=502,
        detail="Cashfree could not prepare the target subscription plan. Please retry or contact support.",
    )


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
    # Serialize checkout creation per shop to prevent duplicate Cashfree mandates.
    db.execute(text("SELECT pg_advisory_xact_lock(:shop_lock)"), {"shop_lock": shop_id})

    active = db.execute(text("""
        SELECT id, status, plan_code, billing_interval, amount_paise,
               cashfree_subscription_id, cancel_at_period_end, current_period_end
        FROM rm_shop_subscriptions
        WHERE shop_id=:shop
          AND status IN ('ACTIVE','GRACE_PERIOD')
          AND (
              current_period_end IS NULL
              OR current_period_end >= NOW()
              OR (status='GRACE_PERIOD' AND grace_period_end >= NOW())
          )
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    """), {"shop": shop_id}).mappings().first()
    if active:
        subscription_id = int(active["id"])
        current_status = str(active["status"] or "").upper()
        cashfree_subscription_id = str(active["cashfree_subscription_id"] or "").strip()
        current_plan = str(active["plan_code"] or "").upper()
        current_interval = str(active["billing_interval"] or "MONTHLY").upper()

        if current_status != "ACTIVE":
            raise HTTPException(status_code=409, detail={
                "code": "SUBSCRIPTION_NOT_CHANGEABLE",
                "subscription_id": subscription_id,
                "current_status": current_status,
                "message": "This subscription is in a payment grace period. Resolve the pending payment before changing plans.",
            })
        cancellation_pending = bool(active["cancel_at_period_end"])
        if cancellation_pending and not active["current_period_end"]:
            raise HTTPException(status_code=409, detail={
                "code": "SUBSCRIPTION_PERIOD_END_UNKNOWN",
                "subscription_id": subscription_id,
                "current_plan": current_plan,
                "message": "We cannot safely reactivate this subscription because its paid-through date is missing. Contact support to reconcile the Cashfree mandate.",
            })
        if not cashfree_subscription_id:
            raise HTTPException(status_code=409, detail={
                "code": "SUBSCRIPTION_MANDATE_MISSING",
                "subscription_id": subscription_id,
                "message": "The active subscription has no linked Cashfree mandate. Contact support so it can be reconciled safely.",
            })
        if current_plan == code and current_interval == body.billing_interval:
            raise HTTPException(status_code=409, detail={
                "code": "PLAN_ALREADY_ACTIVE",
                "subscription_id": subscription_id,
                "current_plan": current_plan,
                "message": "This plan is already active on your shop.",
            })

        app_id, secret, base = _cashfree_config()
        activation_accepted = False
        activation_date = (
            _cashfree_activation_date(active["current_period_end"])
            if cancellation_pending else None
        )
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                target_plan_id = await _ensure_cashfree_plan(
                    client,
                    base=base,
                    app_id=app_id,
                    secret=secret,
                    plan_code=code,
                    plan_name=str(plan["name"]),
                    billing_interval=body.billing_interval,
                    amount_paise=amount,
                )

                # Cashfree cancellation is an explicit mandate action. When the
                # owner has already requested cancellation, first schedule ACTIVATE
                # for the existing paid-through date; only then change the plan on
                # that same mandate. Never create a second mandate for this case.
                if cancellation_pending:
                    activation_response = await client.post(
                        f"{base}/subscriptions/{cashfree_subscription_id}/manage",
                        headers=_cashfree_headers(
                            app_id,
                            secret,
                            f"rm-activate-{subscription_id}-{activation_date}",
                        ),
                        json={
                            "subscription_id": cashfree_subscription_id,
                            "action": "ACTIVATE",
                            "action_details": {
                                "next_scheduled_time": activation_date,
                            },
                        },
                    )
                    if activation_response.status_code not in (200, 201):
                        logger.error(
                            "Cashfree reactivation failed: subscription_id=%s status=%s body=%s",
                            subscription_id,
                            activation_response.status_code,
                            activation_response.text[:700],
                        )
                        raise HTTPException(status_code=409, detail={
                            "code": "SUBSCRIPTION_REACTIVATION_FAILED",
                            "subscription_id": subscription_id,
                            "current_plan": current_plan,
                            "message": "Cashfree could not remove the scheduled cancellation. Your current plan is unchanged. Refresh status or contact support before retrying.",
                        })

                    activation_accepted = True
                    db.execute(text("""
                        UPDATE rm_shop_subscriptions
                        SET cancel_at_period_end=FALSE,
                            cancelled_at=NULL,
                            updated_at=NOW()
                        WHERE id=:id AND shop_id=:shop AND status='ACTIVE'
                    """), {"id": subscription_id, "shop": shop_id})

                change_response = await client.post(
                    f"{base}/subscriptions/{cashfree_subscription_id}/manage",
                    headers=_cashfree_headers(
                        app_id,
                        secret,
                        f"rm-change-plan-{subscription_id}-{target_plan_id}",
                    ),
                    json={
                        "subscription_id": cashfree_subscription_id,
                        "action": "CHANGE_PLAN",
                        "action_details": {"plan_id": target_plan_id},
                    },
                )

            if change_response.status_code not in (200, 201):
                logger.error(
                    "Cashfree plan change failed: subscription_id=%s target_plan=%s status=%s body=%s",
                    subscription_id, target_plan_id, change_response.status_code,
                    change_response.text[:700],
                )
                if activation_accepted:
                    raise HTTPException(status_code=502, detail={
                        "code": "SUBSCRIPTION_REACTIVATED_UPGRADE_FAILED",
                        "subscription_id": subscription_id,
                        "current_plan": current_plan,
                        "message": "The scheduled cancellation was removed and your current plan remains active, but Cashfree could not apply the selected upgrade. Refresh subscription status and retry.",
                    })
                raise HTTPException(status_code=502, detail={
                    "code": "CASHFREE_PLAN_CHANGE_FAILED",
                    "message": "Cashfree could not change the existing mandate. Your current subscription has been left unchanged. Please retry or contact support.",
                })

            db.execute(text("""
                UPDATE rm_shop_subscriptions
                SET plan_code=:plan,
                    billing_interval=:interval,
                    amount_paise=:amount,
                    cancel_at_period_end=FALSE,
                    cancelled_at=NULL,
                    updated_at=NOW()
                WHERE id=:id AND shop_id=:shop AND status='ACTIVE'
            """), {
                "plan": code,
                "interval": body.billing_interval,
                "amount": amount,
                "id": subscription_id,
                "shop": shop_id,
            })
            db.commit()
        except HTTPException:
            # If ACTIVATE succeeded but CHANGE_PLAN did not, retain the confirmed
            # cancellation reversal locally. Otherwise no local state changed.
            if activation_accepted:
                db.commit()
            else:
                db.rollback()
            raise
        except Exception as exc:
            if activation_accepted:
                db.commit()
            else:
                db.rollback()
            logger.exception(
                "Cashfree plan upgrade failed: shop_id=%s subscription_id=%s",
                shop_id,
                subscription_id,
            )
            raise HTTPException(status_code=502, detail={
                "code": (
                    "SUBSCRIPTION_REACTIVATED_UPGRADE_UNCONFIRMED"
                    if activation_accepted else "CASHFREE_PLAN_CHANGE_UNCONFIRMED"
                ),
                "message": (
                    "The scheduled cancellation was removed, but the selected plan change could not be confirmed. Refresh subscription status before retrying."
                    if activation_accepted else
                    "Cashfree could not confirm the plan change. Your current subscription was not changed. Refresh status before retrying."
                ),
            }) from exc
        return {
            "success": True,
            "plan_changed": True,
            "requires_checkout": False,
            "subscription_id": cashfree_subscription_id,
            "subscription_record_id": subscription_id,
            "plan_code": code,
            "billing_interval": body.billing_interval,
            "amount_paise": amount,
            "status": "ACTIVE",
            "cancellation_reversed": cancellation_pending,
            "message": (
                "Your scheduled cancellation was reversed and your existing subscription was upgraded. No second mandate was created."
                if cancellation_pending else
                "Your existing recurring subscription has been changed. No second mandate was created."
            ),
        }

    pending_rows = db.execute(text("""
        SELECT id, status, cashfree_subscription_id, created_at
        FROM rm_shop_subscriptions
        WHERE shop_id=:shop AND status IN ('CREATING','PENDING_AUTH')
        ORDER BY created_at DESC, id DESC
    """), {"shop": shop_id}).mappings().all()

    # Resolve abandoned checkouts conservatively. Never expire a recent CREATING row,
    # and never mark a remote Cashfree mandate cancelled until Cashfree confirms it.
    pending_app_id = pending_secret = pending_base = None
    for pending in pending_rows:
        if pending["status"] == "CREATING":
            stale = db.execute(text("""
                UPDATE rm_shop_subscriptions
                SET status='CREATE_FAILED', updated_at=NOW()
                WHERE id=:id AND status='CREATING'
                  AND created_at < NOW() - INTERVAL '10 minutes'
            """), {"id": pending["id"]})
            # Keep the transaction-scoped advisory lock until the new CREATING row is inserted.
            if getattr(stale, "rowcount", 0) == 0:
                raise HTTPException(status_code=409, detail={
                    "code": "CHECKOUT_CREATION_IN_PROGRESS",
                    "subscription_id": int(pending["id"]),
                    "message": "A subscription checkout is currently being created. Please wait a minute and retry.",
                })
            continue

        cashfree_id = pending["cashfree_subscription_id"]
        if not cashfree_id:
            db.execute(text("""
                UPDATE rm_shop_subscriptions
                SET status='CANCELLED', cancelled_at=NOW(), updated_at=NOW()
                WHERE id=:id AND status='PENDING_AUTH'
            """), {"id": pending["id"]})
            # Do not commit here: the advisory lock must cover all pending cleanup.

        if pending_app_id is None:
            pending_app_id, pending_secret, pending_base = _cashfree_config()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                cancel_response = await client.post(
                    f"{pending_base}/subscriptions/{cashfree_id}/manage",
                    headers=_cashfree_headers(
                        pending_app_id, pending_secret,
                        f"rm-retry-cancel-{pending['id']}",
                    ),
                    json={"subscription_id": cashfree_id, "action": "CANCEL"},
                )
            if cancel_response.status_code not in (200, 201):
                logger.warning(
                    "Could not cancel previous pending Cashfree subscription %s: %s %s",
                    cashfree_id, cancel_response.status_code, cancel_response.text[:500],
                )
                raise HTTPException(status_code=409, detail={
                    "code": "PENDING_CASHFREE_CHECKOUT",
                    "subscription_id": int(pending["id"]),
                    "message": "A previous checkout is still pending with Cashfree. Open or cancel that checkout before starting another plan.",
                })
            db.execute(text("""
                UPDATE rm_shop_subscriptions
                SET status='CANCELLED', cancelled_at=NOW(), updated_at=NOW()
                WHERE id=:id AND status='PENDING_AUTH'
            """), {"id": pending["id"]})
            # Do not commit here: keep the per-shop advisory lock until the new checkout row exists.
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
            # Cashfree returned no session. Keep the CREATING row for reconciliation:
            # the provider may already have opened a mandate despite the missing token.
            logger.error(
                "Cashfree created subscription without checkout session: shop_id=%s subscription_id=%s",
                shop_id, cf_id,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "CASHFREE_SESSION_MISSING",
                    "message": "Cashfree did not return a checkout session. This attempt is held for reconciliation to prevent duplicate mandates. Please contact support.",
                },
            )
        db.execute(text("UPDATE rm_shop_subscriptions SET status='PENDING_AUTH',subscription_session_id=:session,cashfree_subscription_id=:cfid,updated_at=NOW() WHERE cashfree_subscription_id=:old"), {"session":session_id,"cfid":cf_id,"old":local_sub_id})
        db.commit()
        return {"subscription_id": cf_id, "subscription_session_id": session_id, "environment": os.getenv("CASHFREE_ENV","sandbox").lower(), "status": "PENDING_AUTH"}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        # Do not mark an ambiguous network timeout as CREATE_FAILED: Cashfree may
        # have accepted the request even if Retail Mind never received its reply.
        # The CREATING row deliberately blocks a second mandate until reconciled.
        logger.exception(
            "Cashfree subscription creation outcome is unknown; reconciliation required: shop_id=%s subscription_id=%s",
            shop_id, local_sub_id,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "CASHFREE_CHECKOUT_OUTCOME_UNKNOWN",
                "message": "We could not confirm whether Cashfree created this checkout. To avoid duplicate recurring payments, this attempt is held for reconciliation. Please contact support before retrying.",
            },
        )

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

