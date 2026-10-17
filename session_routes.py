from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from db import get_db
from session_service import SessionService
from models import User
from security import get_current_user

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
    #
    # FIX (dead legacy-fallback bug): this used to call security.decode_token(),
    # which converts *any* decode failure (bad signature, expired, or simply
    # "not a JWT at all") into an HTTPException(401). That HTTPException was
    # then immediately re-raised below, so the "fall through to the DB-backed
    # legacy SessionService" path documented in this docstring was dead code -
    # any user still holding a pre-JWT opaque refresh token got a hard 401 on
    # every refresh attempt and could never recover without a full re-login.
    #
    # We now decode the JWT directly and only treat a genuine JWTError as
    # "not a JWT refresh token", letting it fall through to the legacy path.
    from jose import JWTError, jwt as jose_jwt
    from security import SECRET_KEY, ALGORITHM, create_access_token, create_refresh_token

    payload = None
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        payload = None  # Not a (valid) JWT - fall through to legacy path below.

    if payload is not None and payload.get("type") == "refresh":
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

    # Compatibility path for older DB-backed refresh tokens.
    result = SessionService.refresh_access_token(db, token, req.device_id)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


class LogoutRequest(BaseModel):
    access_token: str


@router.post("/logout")
def logout(
    req: LogoutRequest,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log out only a token belonging to the authenticated user."""
    from security import decode_token

    token = (req.access_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing access token")

    # The bearer dependency authenticates the caller; independently validate
    # the body token before revoking it so a caller cannot log out another user.
    payload = decode_token(token)
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=400, detail="A refresh token cannot be logged out as an access session")
    raw_subject = payload.get("sub")
    try:
        token_user_id = int(raw_subject)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")

    if token_user_id != current_user:
        raise HTTPException(status_code=403, detail="Cannot log out another user's session")

    success = SessionService.logout(db, token)
    if not success:
        return {"status": "Already logged out or invalid token"}
    return {"status": "Logged out successfully"}


@router.post("/logout-all")
def logout_all_devices(user_id: int = Body(..., embed=True), current_user: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Logs the authenticated user out of all devices; never trust a caller-supplied identity."""
    if user_id != current_user:
        raise HTTPException(status_code=403, detail="Cannot manage sessions for another user")
    count = SessionService.logout_all_devices(db, current_user)
    return {"status": f"Logged out from {count} devices"}


@router.get("/active/{user_id}")
def get_active_sessions(user_id: int, current_user: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Returns active sessions for the authenticated user only."""
    if user_id != current_user:
        raise HTTPException(status_code=403, detail="Cannot view sessions for another user")
    return {"sessions": SessionService.get_active_sessions(db, current_user)}


class OfflineData(BaseModel):
    user_id: int
    data_type: str
    payload: dict


@router.post("/offline/queue")
def sync_offline_data(req: OfflineData, current_user: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Queues offline data only for the authenticated user."""
    if req.user_id != current_user:
        raise HTTPException(status_code=403, detail="Cannot queue data for another user")
    return SessionService.queue_offline_data(db, current_user, req.data_type, req.payload)


@router.post("/offline/sync")
def sync_all_offline_data(user_id: int = Body(..., embed=True), current_user: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Synchronizes offline data for the authenticated user only."""
    if user_id != current_user:
        raise HTTPException(status_code=403, detail="Cannot sync data for another user")
    return SessionService.sync_offline_queue(db, current_user)
