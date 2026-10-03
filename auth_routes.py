import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from models import User, ShopProfile, Worker
from security import hash_password, verify_password, create_access_token, ROLE_OWNER, get_current_user, check_login_lockout, record_login_failure, record_login_success
from email_notifications import EmailNotificationService
from rate_limiter import rate_limit_endpoint, get_client_ip, ip_rate_limiter
import random
import time
from typing import Optional
import hashlib
import secrets
from datetime import timedelta
from models import PasswordReset
from jose import JWTError  # Required for refresh_token endpoint exception handling

router = APIRouter()
logger = logging.getLogger(__name__)

class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    user_type: Optional[str] = "OWNER"
    role: Optional[str] = "OWNER"
    is_active: Optional[bool] = True
    shop_name: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/register")
def register(user: UserCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    # Email is required and must be unique (we treat email as the primary login identifier)
    if not user.email or user.email.strip() == "":
        raise HTTPException(status_code=400, detail="Email is required")

    from sqlalchemy import func
    from sqlalchemy.exc import SQLAlchemyError

    # Check email uniqueness (case-insensitive) — return 409 Conflict
    if db.query(User).filter(func.lower(User.email) == user.email.strip().lower()).first():
        raise HTTPException(status_code=409, detail="This email is already registered. Please login instead.")

    # Usernames and shop names are display labels, not account identifiers.
    # Only email is globally unique; tenant identity is the generated user id.

    # Hash password securely
    hashed_password = hash_password(user.password)

    # Create new user AND shop profile atomically to avoid partial registration
    try:
        # Use a nested transaction (SAVEPOINT) so this handler can be called
        # even when the session already has an active transaction.
        with db.begin_nested():
            new_user = User(
                user_name=user.username,
                email=user.email.strip().lower(),  # Store email in lowercase for consistency
                password=hashed_password,
                user_type=user.user_type.upper() if user.user_type else "OWNER",
                is_active=user.is_active if user.is_active is not None else True
            )
            db.add(new_user)
            db.flush()  # ensure new_user.id is populated

            # Auto-create Shop Profile only if they are an OWNER
            if (new_user.user_type or user.user_type or "OWNER").upper() == "OWNER":
                shop_name_value = user.shop_name.strip() if user.shop_name and user.shop_name.strip() else f"{user.username}'s Shop"
                shop_profile = ShopProfile(shop_id=new_user.id, shop_name=shop_name_value)
                db.add(shop_profile)

        # Refresh to load generated fields and persist the user/shop to the database
        db.refresh(new_user)
        # Commit the transaction so a separate login request can see the newly created user
        try:
            db.commit()
        except Exception:
            # In case commit fails, rollback to leave DB in a consistent state
            db.rollback()
            raise
    except Exception as e:
        # Log full stack trace for debugging and rollback
        logger.exception("Registration failed: unexpected error")
        try:
            db.rollback()
        except Exception:
            logger.warning("Rollback failed during registration error handling")
        # Return a generic message to the client while preserving details in server logs
        raise HTTPException(status_code=500, detail="Registration failed: internal server error (see server logs)")

    # Send Welcome Email with Credentials in the background
    try:
        subject, body = EmailNotificationService.welcome_credentials_template(user.username, "[HIDDEN FOR SECURITY]", "Shop Owner")
        background_tasks.add_task(
            EmailNotificationService.send_email,
            recipient_email=user.email,
            subject=subject,
            body=body
        )
    except Exception as e:
        logger.error(f"Failed to queue welcome email: {e}")

    # Generate access token for immediate login after registration
    access_token = create_access_token(
        data={"sub": str(new_user.id), "role": new_user.user_type, "user_type": new_user.user_type}
    )

    registered_profile = (
        db.query(ShopProfile)
        .filter(ShopProfile.shop_id == new_user.id)
        .first()
    )

    return {
        "msg": "User registered successfully",
        "user_id": new_user.id,
        "access_token": access_token,
        "token_type": "bearer",
        "role": new_user.user_type,
        "user_type": new_user.user_type,
        "username": new_user.user_name,
        "shop_profile": {
            "id": registered_profile.id,
            "shop_id": registered_profile.shop_id,
            "shop_name": registered_profile.shop_name,
            "logo_url": registered_profile.logo_url,
        } if registered_profile else None,
    }

class SendOTPRequest(BaseModel):
    email: str
    purpose: Optional[str] = "Verification"

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str


class StoreResetOTPRequest(BaseModel):
    email: str
    otp: str


class VerifyResetOTPRequest(BaseModel):
    email: str
    otp: str
    password: str


class OwnerOTPRequest(BaseModel):
    email: Optional[str] = None
    purpose: Optional[str] = "Owner Verification"

class ResetWorkerPinRequest(BaseModel):
    email: Optional[str] = None
    otp: str
    worker_id: int
    new_pin: str



class StoreResetOTPRequestLegacy(BaseModel):
    email: str
    otp: str


class RequestPasswordReset(BaseModel):
    email: str


PASSWORD_RESET_OTP_PURPOSE = "PASSWORD_RESET_OTP"
OWNER_VERIFICATION_OTP_PURPOSE = "OWNER_VERIFICATION_OTP"


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.strip().encode()).hexdigest()


def _new_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def _delete_pending_otps(db: Session, user_id: int, purpose: str) -> None:
    db.query(PasswordReset).filter(
        PasswordReset.user_id == user_id,
        PasswordReset.description == purpose,
    ).delete(synchronize_session=False)


def _store_db_otp(db: Session, user_id: int, otp: str, purpose: str, minutes: int = 10) -> None:
    _delete_pending_otps(db, user_id, purpose)
    db.add(
        PasswordReset(
            user_id=user_id,
            token_hash=_hash_otp(otp),
            expires_at=datetime.utcnow() + timedelta(minutes=minutes),
            description=purpose,
        )
    )


def _find_db_otp(db: Session, user_id: int, otp: str, purpose: str):
    return db.query(PasswordReset).filter(
        PasswordReset.user_id == user_id,
        PasswordReset.description == purpose,
        PasswordReset.token_hash == _hash_otp(otp),
        PasswordReset.expires_at > datetime.utcnow(),
    ).order_by(PasswordReset.id.desc()).first()


otp_cache = {}


@router.post("/send-otp")
def send_otp(
    request: SendOTPRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    normalized_email = request.email.strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email is required")

    otp_code = _new_otp()
    otp_cache[normalized_email] = {
        "otp_hash": _hash_otp(otp_code),
        "expires_at": time.time() + 600,
    }

    subject, body = EmailNotificationService.send_otp_template(
        otp_code,
        request.purpose or "Verification",
    )

    try:
        success = EmailNotificationService.send_email(
            recipient_email=normalized_email,
            subject=subject,
            body=body,
        )
        if not success:
            otp_cache.pop(normalized_email, None)
            raise HTTPException(
                status_code=500,
                detail="Failed to send OTP email. Check backend email configuration.",
            )
        logger.info("Backend OTP sent successfully to %s", normalized_email)
        return {"msg": "OTP sent successfully"}
    except HTTPException:
        raise
    except Exception as e:
        otp_cache.pop(normalized_email, None)
        logger.exception("Failed while sending OTP email: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to send OTP email. Check backend email configuration.",
        )


@router.post("/verify-otp")
def verify_otp(request: VerifyOTPRequest):
    normalized_email = request.email.strip().lower()
    record = otp_cache.get(normalized_email)

    if not record:
        raise HTTPException(status_code=400, detail="OTP not requested or expired")

    if time.time() > record["expires_at"]:
        otp_cache.pop(normalized_email, None)
        raise HTTPException(status_code=400, detail="OTP expired")

    if record["otp_hash"] != _hash_otp(request.otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    otp_cache.pop(normalized_email, None)
    return {"msg": "OTP verified successfully"}


@router.post("/reset-worker-pin")
def reset_worker_pin(
    request: ResetWorkerPinRequest,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset a worker attendance PIN after owner-email OTP verification."""
    normalized_email = request.email.strip().lower()
    new_pin = request.new_pin.strip()

    if not __import__("re").fullmatch(r"\d{4}", new_pin):
        raise HTTPException(status_code=400, detail="Worker PIN must be exactly 4 digits")

    user = db.query(User).filter(User.id == current_user).first()
    if not user:
        raise HTTPException(status_code=401, detail="Authenticated owner not found")

    if (user.email or "").strip().lower() != normalized_email:
        raise HTTPException(
            status_code=403,
            detail="Verification email does not match the logged-in account",
        )

    record = _find_db_otp(
        db,
        user_id=user.id,
        otp=request.otp,
        purpose=OWNER_VERIFICATION_OTP_PURPOSE,
    )
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired owner verification OTP")

    worker = db.query(Worker).filter(
        Worker.id == request.worker_id,
        Worker.shopkeeper_id == current_user,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    worker.pin = new_pin
    try:
        db.delete(record)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reset worker PIN")

    return {
        "message": "Worker attendance PIN reset successfully",
        "worker_id": worker.id,
    }


@router.post("/send-owner-otp")
def send_owner_otp(
    request: OwnerOTPRequest,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user).first()
    if not user:
        raise HTTPException(status_code=401, detail="Authenticated user not found")

    normalized_email = (user.email or "").strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Owner account has no registered email")

    otp_code = _new_otp()
    _store_db_otp(
        db,
        user_id=user.id,
        otp=otp_code,
        purpose=OWNER_VERIFICATION_OTP_PURPOSE,
    )

    subject, body = EmailNotificationService.send_otp_template(
        otp_code,
        request.purpose or "Owner Verification",
    )

    try:
        success = EmailNotificationService.send_email(
            recipient_email=normalized_email,
            subject=subject,
            body=body,
        )
        if not success:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to send owner verification OTP. Check backend email configuration.",
            )
        db.commit()
        return {"msg": "Owner verification OTP sent successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Owner OTP email failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to send owner verification OTP. Check backend email configuration.",
        )


@router.post("/verify-owner-otp")
def verify_owner_otp(
    request: VerifyOTPRequest,
    current_user: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_email = request.email.strip().lower()
    user = db.query(User).filter(User.id == current_user).first()
    if not user:
        raise HTTPException(status_code=401, detail="Authenticated user not found")

    if (user.email or "").strip().lower() != normalized_email:
        raise HTTPException(status_code=403, detail="Verification email does not match the logged-in account")

    record = _find_db_otp(
        db,
        user_id=user.id,
        otp=request.otp,
        purpose=OWNER_VERIFICATION_OTP_PURPOSE,
    )
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired owner verification OTP")

    try:
        db.delete(record)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to complete owner verification")

    return {"msg": "Owner verification OTP verified successfully"}


@router.post("/request-password-reset-otp")
def request_password_reset_otp(
    request: RequestPasswordReset,
    db: Session = Depends(get_db),
):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email)).first()

    # Deliberately keep the response generic so account existence is not disclosed.
    if not user:
        return {"msg": "If the email exists, a password-reset OTP has been sent"}

    otp_code = _new_otp()
    _store_db_otp(
        db,
        user_id=user.id,
        otp=otp_code,
        purpose=PASSWORD_RESET_OTP_PURPOSE,
    )

    subject, body = EmailNotificationService.send_otp_template(
        otp_code,
        "Password Reset",
    )

    try:
        success = EmailNotificationService.send_email(
            recipient_email=email,
            subject=subject,
            body=body,
        )
        if not success:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to send password-reset OTP. Check backend email configuration.",
            )
        db.commit()
        return {"msg": "If the email exists, a password-reset OTP has been sent"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Password-reset OTP email failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Failed to send password-reset OTP. Check backend email configuration.",
        )


class CheckResetOTPRequest(BaseModel):
    email: str
    otp: str


@router.post("/check-reset-otp")
def check_reset_otp(
    request: CheckResetOTPRequest,
    db: Session = Depends(get_db),
):
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset OTP")

    record = _find_db_otp(
        db,
        user_id=user.id,
        otp=request.otp,
        purpose=PASSWORD_RESET_OTP_PURPOSE,
    )
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset OTP")

    return {"msg": "Reset OTP verified successfully"}


@router.post("/store-reset-otp")
def store_reset_otp_legacy(request: StoreResetOTPRequestLegacy):
    # Kept only as a compatibility response for older clients.
    # New clients must use /request-password-reset-otp so the backend generates
    # and emails the OTP. The server never accepts a client-generated OTP.
    raise HTTPException(
        status_code=410,
        detail="Client-generated reset OTPs are no longer supported. Request a new OTP.",
    )


@router.post("/verify-reset-otp")
def verify_reset_otp(request: VerifyResetOTPRequest, db: Session = Depends(get_db)):
    """Verify a backend-generated password-reset OTP and reset the user's password."""
    email = request.email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email)).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset OTP")

    record = _find_db_otp(
        db,
        user_id=user.id,
        otp=request.otp,
        purpose=PASSWORD_RESET_OTP_PURPOSE,
    )
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset OTP")

    user.password = hash_password(request.password)
    try:
        db.delete(record)
        # Also invalidate any older reset OTPs for this user.
        _delete_pending_otps(db, user.id, PASSWORD_RESET_OTP_PURPOSE)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reset password")

    return {"msg": "Password reset successfully"}


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


@router.post("/request-password-reset")
def request_password_reset(data: RequestPasswordReset, db: Session = Depends(get_db)):
    # Generate a server-side reset token and return it so frontend can email it.
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email)).first()
    if not user:
        # Don't reveal whether the email exists; return generic message
        return {"msg": "If the email exists, a reset token was generated"}

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    pr = PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
    db.add(pr)
    db.commit()

    # Return token to the caller (frontend) so it can send/email the reset link
    return {"msg": "Reset token generated", "token": token, "expires_in": 1800}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    now = datetime.utcnow()
    pr = db.query(PasswordReset).filter(PasswordReset.token_hash == token_hash, PasswordReset.expires_at > now).first()
    if not pr:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).get(pr.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found for token")

    # Update password
    user.password = hash_password(data.password)
    # Invalidate token
    try:
        db.delete(pr)
        db.commit()
    except Exception:
        db.rollback()

    return {"msg": "Password reset successfully"}

@router.post("/login")
@rate_limit_endpoint(max_requests=5, window_seconds=60)
def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    try:
        ip = get_client_ip(request)
        
        # Check if IP is blocked due to too many failed attempts
        if ip_rate_limiter.is_blocked(ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again in 5 minutes.",
            )
        
        check_login_lockout(ip)
        
        # Case-insensitive email lookup
        db_user = db.query(User).filter(User.email.ilike(user.email)).first()
        
        if not db_user or not verify_password(user.password, db_user.password):
            # Record failed attempt
            if ip_rate_limiter.record_failure(ip):
                logger.warning(f"IP {ip} blocked due to too many failed login attempts")
            
            record_login_failure(ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        if not db_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Please contact support.",
            )
        
        # Record successful login and reset failure counter
        ip_rate_limiter.record_success(ip)
        record_login_success(ip)

        # Get user role from database
        user_role = getattr(db_user, 'user_type', ROLE_OWNER) or ROLE_OWNER

        # Create access token with user role
        access_token = create_access_token(
            data={"sub": str(db_user.id), "role": user_role, "user_type": user_role}
        )
        
        # Guarantee that every OWNER account has exactly one shop profile before
        # the login response is returned. This also repairs legacy accounts that
        # were created before the automatic shop-profile creation existed.
        shop_profile = None
        if str(user_role).upper() == str(ROLE_OWNER).upper():
            from shop_management import ShopService
            shop_profile = ShopService.get_shop_profile(db, db_user.id)

        # Create refresh token for secure token renewal
        from security import create_refresh_token
        refresh_token = create_refresh_token(db_user.id, user_role)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "role": user_role,
            "user_type": user_role,
            "user_id": db_user.id,
            "username": db_user.user_name,
            "shop_profile": {
                "id": shop_profile.id,
                "shop_id": shop_profile.shop_id,
                "shop_name": shop_profile.shop_name,
                "shop_type": shop_profile.shop_type,
                "logo_url": shop_profile.logo_url,
                "is_online_store_enabled": bool(shop_profile.is_online_store_enabled),
            } if shop_profile else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed unexpectedly for {user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred. Please try again."
        )

@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token.
    This implements secure token renewal without requiring re-login.
    """
    try:
        from security import decode_token, create_access_token, create_refresh_token
        
        # Decode refresh token
        payload = decode_token(request.refresh_token)
        
        # Validate it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type. Expected refresh token."
            )
        
        # Extract user_id and role
        user_id = int(payload.get("sub"))
        role = payload.get("role")
        
        # Verify user still exists and is active
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user or not db_user.is_active:
            raise HTTPException(
                status_code=401,
                detail="User not found or inactive"
            )
        
        # Create new access token
        new_access_token = create_access_token(
            data={"sub": str(db_user.id), "role": role, "user_type": role}
        )
        
        # Create new refresh token (rotate refresh tokens for security)
        new_refresh_token = create_refresh_token(db_user.id, role)
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "role": role,
            "user_type": role,
            "user_id": db_user.id
        }
        
    except JWTError as e:
        logger.error(f"JWTError on refresh: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )
    except Exception as e:
        logger.error(f"Token refresh failed unexpectedly: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


class FCMTokenRequest(BaseModel):
    fcm_token: str

@router.post("/fcm-token")
def register_fcm_token(request: FCMTokenRequest, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """Register device FCM token for push notifications"""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.fcm_token = request.fcm_token
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to register FCM token: {str(e)}")
    
    return {"msg": "FCM token registered successfully"}
@router.get("/sales")
def get_sales(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get all sales/invoices for a user to restore when app data is cleared.
    This endpoint is used by the frontend to download sales history from the cloud.
    """
    try:
        from models import Invoice, InvoiceLineItem
        from sqlalchemy import desc
        
        # Get all invoices for this user
        invoices = db.query(Invoice).filter(
            Invoice.user_id == user_id
        ).order_by(desc(Invoice.created_at)).all()
        
        sales_data = []
        for invoice in invoices:
            # Flatten invoices into legacy sales objects expected by the frontend
            line_items = db.query(InvoiceLineItem).filter(
                InvoiceLineItem.invoice_id == invoice.id
            ).all()

            if not line_items:
                # If there are no line items, just create a placeholder
                sales_record = {
                    'id': invoice.id,
                    'sale_id': invoice.invoice_number,
                    'invoice_id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'customer_name': invoice.customer_name,
                    'product_name': 'Unknown Product',
                    'product': 'Unknown Product',
                    'price': float(invoice.total_amount),
                    'quantity': 1,
                    'total': float(invoice.total_amount),
                    'totalAmount': float(invoice.total_amount),
                    'date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                    'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                    'payment_status': invoice.payment_status,
                }
                sales_data.append(sales_record)
            else:
                for idx, item in enumerate(line_items):
                    sales_record = {
                        'id': f"{invoice.id}_{idx}", # Unique ID for the flattened item
                        'sale_id': invoice.invoice_number, # CRUCIAL: Frontend groups bills using sale_id!
                        'invoice_id': invoice.id,
                        'invoice_number': invoice.invoice_number,
                        'customer_name': invoice.customer_name,
                        'product_name': item.description or 'Unknown',
                        'product': item.description or 'Unknown',
                        'item': item.description or 'Unknown',
                        'price': float(item.unit_price),
                        'quantity': item.quantity,
                        'total': float(item.line_total),
                        'totalAmount': float(item.line_total),
                        'final_amount': float(item.line_total),
                        'date': invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                        'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                        'payment_status': invoice.payment_status,
                    }
                    sales_data.append(sales_record)
        
        return sales_data
    except Exception as e:
        logger.error(f"Error fetching sales: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch sales: {str(e)}")

from fastapi import Form
@router.post("/sales")
def create_sale_legacy(
    user_id: int = Depends(get_current_user),
    product_name: str = Form(None),
    product: str = Form(None),
    item: str = Form(None),
    itemName: str = Form(None),
    price: float = Form(0.0),
    quantity: int = Form(1),
    total: float = Form(0.0),
    date: str = Form(None),
    sale_id: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Handle legacy frontend sales sync.
    """
    try:
        from models import sales, Invoice, InvoiceLineItem
        from datetime import datetime, date as date_obj
        
        sale_date = datetime.now().date()
        if date:
            try:
                sale_date = datetime.strptime(date, "%Y-%m-%d").date()
            except:
                pass
        
        # Resolve the product name from any of the fields the frontend might send
        actual_product_name = product_name or product or item or itemName or "Unknown Product"
                
        # Also create an Invoice so it shows up correctly in the new system
        invoice_number = sale_id if sale_id else f"INV-{int(time.time())}"
        
        from models import ShopProfile
        shop = db.query(ShopProfile).filter(ShopProfile.shop_id == user_id).first()
        shop_id = shop.id if shop else None
        
        # Check if invoice already exists to deduplicate
        existing_invoice = db.query(Invoice).filter(
            Invoice.user_id == user_id, 
            Invoice.invoice_number == str(invoice_number)
        ).first()
        
        if existing_invoice:
            # Check if this exact line item is already in the invoice
            existing_line = db.query(InvoiceLineItem).filter(
                InvoiceLineItem.invoice_id == existing_invoice.id,
                InvoiceLineItem.description == actual_product_name,
                InvoiceLineItem.unit_price == price,
                InvoiceLineItem.quantity == quantity
            ).first()
            
            if not existing_line:
                # Add new line item to existing invoice
                new_line = InvoiceLineItem(
                    invoice_id=existing_invoice.id,
                    description=actual_product_name,
                    quantity=quantity,
                    unit_price=price,
                    line_total=total
                )
                db.add(new_line)
                
                # Update invoice total
                existing_invoice.total_amount = float(existing_invoice.total_amount) + total
                existing_invoice.paid_amount = float(existing_invoice.paid_amount) + total
                
                # Deduct inventory based on product name
                from models import Product, StockMovement
                from sqlalchemy import func
                product_match = db.query(Product).with_for_update().filter(
                    Product.user_id == user_id,
                    func.lower(Product.product_name) == actual_product_name.lower()
                ).first()
                
                if product_match:
                    if (product_match.current_stock or 0) < quantity:
                        db.rollback()
                        raise HTTPException(400, f"Insufficient stock for {actual_product_name}")
                    product_match.current_stock -= quantity
                    movement = StockMovement(
                        product_id=product_match.id,
                        movement_type="OUT",
                        quantity=quantity,
                        reason="Sale via Sync (Merged)",
                        reference_id=str(invoice_number)
                    )
                    db.add(movement)
                
                db.commit()
            
            return {"msg": "Sale synced (merged into existing invoice)", "invoice_id": existing_invoice.id}
        
        # Otherwise, create a new invoice
        new_invoice = Invoice(
            user_id=user_id,
            invoice_number=str(invoice_number),
            total_amount=total,
            paid_amount=total,
            payment_status="PAID",
            payment_method="CASH",
            invoice_date=sale_date
        )
        db.add(new_invoice)
        db.flush()
        
        new_line = InvoiceLineItem(
            invoice_id=new_invoice.id,
            description=actual_product_name,
            quantity=quantity,
            unit_price=price,
            line_total=total
        )
        db.add(new_line)
        
        # Deduct inventory based on product name
        from models import Product, StockMovement
        from sqlalchemy import func
        product_match = db.query(Product).with_for_update().filter(
            Product.user_id == user_id,
            func.lower(Product.product_name) == actual_product_name.lower()
        ).first()
        
        if product_match:
            if (product_match.current_stock or 0) < quantity:
                db.rollback()
                raise HTTPException(400, f"Insufficient stock for {actual_product_name}")
            product_match.current_stock -= quantity
            movement = StockMovement(
                product_id=product_match.id,
                movement_type="OUT",
                quantity=quantity,
                reason="Sale via Sync",
                reference_id=str(invoice_number)
            )
            db.add(movement)
        
        db.commit()
        
        return {"msg": "Sale saved successfully", "invoice_id": new_invoice.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating sale: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create sale: {str(e)}")
