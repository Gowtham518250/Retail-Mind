"""Atomic per-shop daily AI quota gate for /askquery and /askquery/voice."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text

from db import sessionLocal
from security import get_current_user_dict
from fastapi.security import HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
BUSINESS_TZ = ZoneInfo("Asia/Kolkata")
AI_PATHS = {"/askquery", "/askquery/voice"}

class SubscriptionAIQuotaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method != "POST" or request.url.path not in AI_PATHS:
            return await call_next(request)

        db = sessionLocal()
        reservation = None
        try:
            auth = request.headers.get("authorization", "")
            if not auth.lower().startswith("bearer "):
                return JSONResponse({"detail": "Authentication required."}, status_code=401)
            try:
                user = get_current_user_dict(
                    HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth.split(" ", 1)[1].strip())
                )
            except Exception:
                return JSONResponse({"detail": "Invalid access token."}, status_code=401)
            if user.get("role") != "OWNER":
                return JSONResponse({"detail": "AI shop queries are available to shop owners only."}, status_code=403)

            shop_id = int(user["user_id"])
            now = datetime.now(BUSINESS_TZ)
            usage_date = now.date()
            plan = db.execute(text("""
                SELECT p.daily_ai_query_limit
                FROM rm_shop_subscriptions s
                JOIN rm_subscription_plans p ON p.plan_code=s.plan_code
                WHERE s.shop_id=:shop
                  AND ((s.status='ACTIVE' AND (s.current_period_end IS NULL OR s.current_period_end >= NOW()))
                    OR (s.status='GRACE_PERIOD' AND s.current_period_end IS NOT NULL AND s.grace_period_end >= NOW()))
                ORDER BY s.created_at DESC LIMIT 1
            """), {"shop": shop_id}).first()
            limit = int(plan[0]) if plan else 0

            db.execute(text("""
                INSERT INTO rm_ai_daily_usage(shop_id,usage_date,used_count,reserved_count)
                VALUES(:shop,:day,0,0) ON CONFLICT(shop_id,usage_date) DO NOTHING
            """), {"shop": shop_id, "day": usage_date})
            reservation = db.execute(text("""
                UPDATE rm_ai_daily_usage
                SET reserved_count=reserved_count+1, updated_at=NOW()
                WHERE shop_id=:shop AND usage_date=:day
                  AND used_count+reserved_count < :limit
                RETURNING used_count,reserved_count
            """), {"shop": shop_id, "day": usage_date, "limit": limit}).first()
            if not reservation:
                usage = db.execute(text("""
                    SELECT used_count FROM rm_ai_daily_usage
                    WHERE shop_id=:shop AND usage_date=:day
                """), {"shop": shop_id, "day": usage_date}).first()
                used = int(usage[0]) if usage else 0
                db.commit()
                return JSONResponse({
                    "detail": "Your daily AI query allowance has been used. Upgrade your plan or try again after midnight IST.",
                    "code": "AI_QUERY_LIMIT_REACHED",
                    "daily_limit": limit,
                    "used": used,
                    "remaining": max(0, limit-used),
                    "timezone": "Asia/Kolkata",
                }, status_code=429)
            db.commit()

            try:
                response = await call_next(request)
            except Exception:
                db.execute(text("""
                    UPDATE rm_ai_daily_usage SET reserved_count=GREATEST(0,reserved_count-1),updated_at=NOW()
                    WHERE shop_id=:shop AND usage_date=:day
                """), {"shop": shop_id, "day": usage_date})
                db.commit()
                raise

            if 200 <= response.status_code < 300:
                db.execute(text("""
                    UPDATE rm_ai_daily_usage
                    SET reserved_count=GREATEST(0,reserved_count-1),
                        used_count=used_count+1,updated_at=NOW()
                    WHERE shop_id=:shop AND usage_date=:day
                """), {"shop": shop_id, "day": usage_date})
            else:
                db.execute(text("""
                    UPDATE rm_ai_daily_usage
                    SET reserved_count=GREATEST(0,reserved_count-1),updated_at=NOW()
                    WHERE shop_id=:shop AND usage_date=:day
                """), {"shop": shop_id, "day": usage_date})
            db.commit()
            return response
        except Exception:
            db.rollback()
            logger.exception("AI quota middleware failed")
            return JSONResponse({"detail": "Unable to validate AI usage right now. Please retry."}, status_code=503)
        finally:
            db.close()
