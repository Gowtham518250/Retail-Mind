"""Central server-side subscription entitlement checks.

Use require_shop_feature() inside paid feature endpoints. The lookup is deliberately
fail-closed: missing/expired subscriptions receive the FREE feature set.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_db
from security import owner_only

router = APIRouter()


def get_shop_entitlements(db: Session, shop_id: int) -> dict:
    row = db.execute(text("""
        SELECT p.plan_code, p.name AS plan_name, p.features,
               p.daily_ai_query_limit, s.status, s.current_period_end,
               s.grace_period_end
        FROM rm_shop_subscriptions s
        JOIN rm_subscription_plans p ON p.plan_code = s.plan_code
        WHERE s.shop_id = :shop
          AND (
            (s.status = 'ACTIVE' AND
              (s.current_period_end IS NULL OR s.current_period_end >= NOW()))
            OR
            (s.status = 'GRACE_PERIOD' AND
              s.current_period_end IS NOT NULL AND s.grace_period_end >= NOW())
          )
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT 1
    """), {"shop": shop_id}).mappings().first()

    if not row:
        return {
            "plan_code": "FREE",
            "plan_name": "Free Starter",
            "status": "FREE",
            "features": {
                "sales": True,
                "khata": True,
                "attendance": True,
                "basic_inventory": True,
            },
            "daily_ai_query_limit": 0,
        }

    features = row["features"] or {}
    return {
        "plan_code": row["plan_code"],
        "plan_name": row["plan_name"],
        "status": row["status"],
        "features": {str(key): bool(value) for key, value in features.items()},
        "daily_ai_query_limit": int(row["daily_ai_query_limit"] or 0),
    }


def require_shop_feature(db: Session, shop_id: int, feature_code: str) -> dict:
    """Raise 403 with upgrade metadata unless the active plan grants this feature."""
    if not feature_code or not feature_code.replace("_", "").isalnum():
        raise ValueError("Invalid feature code")
    entitlement = get_shop_entitlements(db, shop_id)
    if entitlement["features"].get(feature_code) is not True:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "SUBSCRIPTION_REQUIRED",
                "feature": feature_code,
                "current_plan": entitlement["plan_code"],
                "message": "This feature is not included in your current plan.",
                "upgrade_path": "/subscriptions",
            },
        )
    return entitlement


@router.get("/api/billing/feature-access/{feature_code}")
def check_feature_access(
    feature_code: str,
    db: Session = Depends(get_db),
    owner: dict = Depends(owner_only),
):
    entitlement = get_shop_entitlements(db, int(owner["user_id"]))
    allowed = entitlement["features"].get(feature_code) is True
    return {
        "allowed": allowed,
        "feature": feature_code,
        "plan_code": entitlement["plan_code"],
        "plan_name": entitlement["plan_name"],
        "daily_ai_query_limit": entitlement["daily_ai_query_limit"],
        "upgrade_path": None if allowed else "/subscriptions",
    }
