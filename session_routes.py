from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from db import get_db
from session_service import SessionService
from models import User

router = APIRouter(prefix="/api/session", tags=["Session Management"])


class RefreshRequest(BaseModel):
    refresh_token: str
    device_id: Optional[str] = "DefaultDevice"


@router.post("/refresh")
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    """
    Refresh an access token without forcing a login.

    The production login endpoint issues JWT refresh tokens, while the
    legacy SessionService also supports DB-backed opaque refresh tokens.
    Accept both formats here so the mobile client's existing /api/session/refresh
    call remains compatible with the actual login flow.
    """
    token = (req.refresh_token or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    # Primary production path: login currently issues a JWT refresh token.
    try:
        from security import decode_token, create_access_token, create_refresh_token

        payload = decode_token(token)
        if payload.get("type") == "refresh":
            raw_user_id = payload.get("sub")
            if raw_user_id is None:
                raise HTTPException(status_code=401, detail="Invalid refresh token")

            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                raise HTTPException(status_code=401, detail="Invalid refresh token subject")

            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="User not found or inactive")

            role = getattr(user, "user_type", None) or payload.get("role") or "OWNER"
            new_access_token = create_access_token(
                data={
                    "sub": str(user.id),
                    "role": role,
                    "user_type": role,
                }
            )
            new_refresh_token = create_refresh_token(user.id, role)

            return {
                "success": True,
                "user_id": user.id,
                "user_name": user.user_name,
                "email": user.email,
                "role": role,
                "user_type": role,
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
                "message": "Session refreshed successfully",
            }
    except HTTPException:
        raise
    except Exception:
        # Not a JWT refresh token; fall through to the DB-backed legacy
        # SessionService for tokens created by older app versions.
        pass

    # Compatibility path for older DB-backed refresh tokens.
    result = SessionService.refresh_access_token(db, token, req.device_id)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


class LogoutRequest(BaseModel):
    access_token: str


@router.post("/logout")
def logout(req: LogoutRequest, db: Session = Depends(get_db)):
    """Logs the user out of the current device."""
    success = SessionService.logout(db, req.access_token)
    if not success:
        return {"status": "Already logged out or invalid token"}
    return {"status": "Logged out successfully"}


@router.post("/logout-all")
def logout_all_devices(user_id: int = Body(..., embed=True), db: Session = Depends(get_db)):
    """Logs the user out of all devices for security."""
    count = SessionService.logout_all_devices(db, user_id)
    return {"status": f"Logged out from {count} devices"}


@router.get("/active/{user_id}")
def get_active_sessions(user_id: int, db: Session = Depends(get_db)):
    """Returns a list of all active sessions for the user."""
    return {"sessions": SessionService.get_active_sessions(db, user_id)}


class OfflineData(BaseModel):
    user_id: int
    data_type: str
    payload: dict


@router.post("/offline/queue")
def sync_offline_data(req: OfflineData, db: Session = Depends(get_db)):
    """Queues offline generated data into the DB for processing."""
    return SessionService.queue_offline_data(db, req.user_id, req.data_type, req.payload)


@router.post("/offline/sync")
def sync_all_offline_data(user_id: int = Body(..., embed=True), db: Session = Depends(get_db)):
    """Synchronizes all offline data queued for the user."""
    return SessionService.sync_offline_queue(db, user_id)
