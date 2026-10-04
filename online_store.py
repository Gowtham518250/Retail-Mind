"""
🏪 ONLINE STORE API — AI Shop Pro Enterprise Backend
Covers:
  - Customer Registration & Login (separate from Owner)
  - Discover nearby shops (by city/area or GPS coords)
  - Browse shop inventory 
  - Place an order
  - Track order status in real-time
  - Owner dashboard: view/accept/reject/dispatch orders
"""

import math
import json
import logging
import secrets
import hashlib
import os
import re
from urllib.parse import quote
from typing import Optional, List
from datetime import datetime, timezone, timedelta, date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from db import get_db
from models import (
    User,
    ShopProfile,
    Product,
    OnlineOrder,
    Invoice,
    InvoiceLineItem,
    UniversalTransaction,
    OnlineCustomerAuth,
    OnlineOrderDeliveryOtp,
    ShopReview,
    OnlineOrderReturn,
    CustomerPasswordReset,
    CustomerPasswordResetOtp,
    sales,
)
from security import (
    hash_password, verify_password, create_access_token,
    ROLE_CUSTOMER, ROLE_OWNER,
    check_login_lockout, record_login_failure, record_login_success,
    owner_only, customer_only, get_current_user, get_current_user_dict, sanitize_input,
    check_rate_limit,
)
try:
    from email_notifications import EmailNotificationService
except ImportError:
    EmailNotificationService = None

def get_active_discount(db: Session, shop_id: int, category: str) -> float:
    try:
        from models import FlashSale
        now = datetime.utcnow()
        active = db.query(FlashSale).filter(
            FlashSale.user_id == shop_id,
            FlashSale.category == category,
            FlashSale.is_active == True,
            FlashSale.end_time > now
        ).order_by(FlashSale.start_time.desc()).first()
        if active:
            return float(active.discount_pct)
    except Exception:
        pass
    return 0.0

logger = logging.getLogger(__name__)
from realtime import publish_realtime_event
from audit_logging import AuditAction, AuditService


router = APIRouter(prefix="/store", tags=["Online Store"])


def _reverse_online_order_financials(db: Session, order: OnlineOrder, shop_id: int, reason: str) -> None:
    """Restore reserved stock and reverse financial side effects when they exist."""
    items = json.loads(order.items_json or "[]")

    for item in items:
        product_id = item.get("product_id")
        quantity = float(item.get("quantity", 0) or 0)
        if not product_id or quantity <= 0:
            continue
        product = db.query(Product).with_for_update().filter(
            Product.id == int(product_id),
            Product.user_id == shop_id,
        ).first()
        if product:
            product.current_stock = (product.current_stock or 0) + quantity

    tagged_sales = db.query(sales).filter(
        sales.shopkeeper_id == shop_id,
        sales.reference_order_id == order.id,
    ).all()

    invoice = db.query(Invoice).filter(
        Invoice.source == "ONLINE_ORDER",
        Invoice.notes.like(f"%Online Order #{order.id}%"),
        Invoice.user_id == shop_id,
    ).first()

    # A PENDING order has reserved stock but has not yet created sales/invoice records.
    # Only write financial reversal entries when ACCEPT already created those records.
    if tagged_sales:
        db.query(sales).filter(
            sales.shopkeeper_id == shop_id,
            sales.reference_order_id == order.id,
        ).delete(synchronize_session=False)

    if invoice:
        invoice.status = "CANCELLED"
        invoice.payment_status = "UNPAID"
        invoice.paid_amount = 0

    if tagged_sales or invoice:
        reversal_ref = f"ONL-{order.id}-REVERSAL"
        existing_reversal = db.query(UniversalTransaction).filter(
            UniversalTransaction.shop_id == shop_id,
            UniversalTransaction.reference_id == reversal_ref,
        ).first()
        if not existing_reversal:
            db.add(UniversalTransaction(
                shop_id=shop_id,
                tx_type="EXPENSE",
                category="SALE_REVERSAL",
                amount=float(order.total_amount or 0),
                reference_id=reversal_ref,
                description=f"{reason}: Online Order #{order.id}",
                tx_date=datetime.now(),
            ))


# =====================
# CUSTOMER AUTH SCHEMAS
# =====================
class CustomerRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    # email is optional — Flutter app registers with phone only
    email: Optional[str] = None
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    password: str = Field(..., min_length=6)
    city: Optional[str] = None
    address: Optional[str] = None
    role: Optional[str] = "CUSTOMER"
    is_active: Optional[bool] = True
    # accept shop_id and firebase_id_token sent by Flutter/web but not strictly required
    shop_id: Optional[int] = None
    firebase_id_token: Optional[str] = None

    @field_validator("email")
    def validate_email(cls, v):
        if v is None or v.strip() == "":
            return None
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("value is not a valid email address")
        return v.lower().strip()

class CustomerLogin(BaseModel):
    # Support login by email OR phone
    email: Optional[str] = None
    phone: Optional[str] = None
    password: str

    @field_validator("email")
    def validate_email(cls, v):
        if v is None or v.strip() == "":
            return None
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("value is not a valid email address")
        return v.lower().strip()

class CustomerLoginPhone(BaseModel):
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    password: str

class CustomerForgot(BaseModel):
    """Legacy compatibility payload for the customer password-reset request."""
    email: Optional[str] = None
    phone: Optional[str] = None
    shop_id: Optional[int] = Field(None, ge=1)

    @field_validator("email")
    def validate_email(cls, v):
        if v is None or v.strip() == "":
            return None
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("value is not a valid email address")
        return v.lower().strip()

class CustomerPasswordResetOtpRequest(BaseModel):
    email: str

    @field_validator("email")
    def validate_email(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("value is not a valid email address")
        return v

class CustomerVerifyPasswordResetOtp(BaseModel):
    email: str
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("email")
    def validate_email(cls, v):
        return v.strip().lower()

class CustomerResetPassword(BaseModel):
    reset_token: str = Field(..., min_length=32, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=128)


class OrderItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, le=1000)

class PlaceOrder(BaseModel):
    shop_id: int
    items: List[OrderItem] = Field(..., min_length=1)
    delivery_address: str = Field(..., min_length=5)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=128)
    coupon_code: Optional[str] = Field(None, min_length=3, max_length=50)

class GuestOrder(BaseModel):
    shop_id: int
    customer_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    delivery_address: str = Field(..., min_length=5, max_length=500)
    items: List[OrderItem] = Field(..., min_length=1, max_length=50)
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=128)
    coupon_code: Optional[str] = Field(None, min_length=3, max_length=50)
    firebase_id_token: Optional[str] = Field(None, description="Firebase Auth ID token for phone verification (optional)")
class OwnerOrderAction(BaseModel):
    """Optional verification payload for owner order state changes."""
    customer_otp: Optional[str] = Field(
        None,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )


class OrderRating(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=500)


_SHOPPING_STOP_WORDS = {
    "a","an","the","for","of","in","on","at","to","with","from","near","me",
    "shop","shops","store","stores","product","products","item","items",
    "cheap","cheapest","low","lowest","price","prices","budget","best","top",
    "good","highest","rated","rating","ratings","under","below","less","than",
    "show","find","give","want","need","please","available","online","nearby",
}


def _shopping_tokens(query: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    return [t for t in tokens if len(t) >= 2 and t not in _SHOPPING_STOP_WORDS][:6]


def _extract_max_price(query: str) -> Optional[float]:
    match = re.search(
        r"(?:under|below|less\s+than|upto|up\s+to)\s*(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)",
        query.lower(),
    )
    return float(match.group(1)) if match else None


def _shop_reputation(shop: ShopProfile) -> dict:
    rating = float(getattr(shop, "rating_score", 0.0) or 0.0)
    count = int(getattr(shop, "rating_count", 0) or 0)
    return {"rating": round(rating, 2), "rating_count": count}



# =====================
# CUSTOMER AUTH
# =====================
@router.post("/customer/register")
def register_customer(
    data: CustomerRegister,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
):
    """Register a new customer account — supports phone-only (no email required)"""

    # ── Normalize the account identity once ───────────────────────────────
    normalized_registration_email = (
        data.email.strip().lower() if data.email and data.email.strip() else None
    )
    name = sanitize_input(data.name, "name")

    # ── Phone is the primary customer identity. ──────────────────────────
    # Guest checkout historically created an inactive placeholder account
    # using the customer's phone. When that same customer later registers,
    # upgrade the placeholder in-place so the existing orders stay attached
    # to the same customer_id instead of being lost from order history.
    existing_phone = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.phone == data.phone
    ).first()

    if existing_phone:
        if existing_phone.is_active:
            raise HTTPException(
                status_code=409,
                detail="Phone number already registered. Please login instead.",
            )

        existing_phone.user_name = name
        existing_phone.email = normalized_registration_email
        existing_phone.city = data.city
        existing_phone.address = data.address
        existing_phone.password = hash_password(data.password)
        existing_phone.is_active = True
        customer = existing_phone
    else:
        customer = OnlineCustomerAuth(
            user_name=name,
            email=normalized_registration_email,
            phone=data.phone,
            city=data.city,
            address=data.address,
            password=hash_password(data.password),
            is_active=data.is_active if data.is_active is not None else True,
        )
        db.add(customer)

    # ── Email must remain unique when supplied. ──────────────────────────
    if normalized_registration_email:
        existing_email = db.query(OnlineCustomerAuth).filter(
            func.lower(func.trim(OnlineCustomerAuth.email)) ==
            normalized_registration_email
        ).first()
        if existing_email and existing_email.id != customer.id:
            raise HTTPException(status_code=409, detail="Email already registered.")

    try:
        db.commit()
        db.refresh(customer)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create customer account: {str(e)}")

    # Send Welcome Email with Credentials (only if email provided)
    try:
        if EmailNotificationService and data.email:
            subject, body = EmailNotificationService.welcome_credentials_template(data.name, "[HIDDEN FOR SECURITY]", "Customer")
            EmailNotificationService.create_notification(
                db=db,
                recipient_email=data.email,
                subject=subject,
                body=body,
                event_type="WELCOME"
            )
    except Exception as e:
        logger.error(f"Failed to send welcome email to customer: {e}")

    token = create_access_token({"sub": str(customer.id), "role": ROLE_CUSTOMER})
    return {
        "message": "Customer account created successfully.",
        "access_token": token,
        "token_type": "bearer",
        "customer_id": customer.id,
        "name": customer.user_name,
    }


@router.post("/customer/login")
def customer_login(
    data: CustomerLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    """Customer login — supports login by email OR phone"""
    ip = request.client.host
    check_login_lockout(ip)

    if not data.email and not data.phone:
        raise HTTPException(status_code=422, detail="Provide either email or phone to login.")

    # Look up by phone first (Flutter app), then fall back to email
    user = None
    if data.phone:
        user = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.phone == data.phone).first()
    if not user and data.email:
        normalized_login_email = data.email.strip().lower()
        user = db.query(OnlineCustomerAuth).filter(
            func.lower(func.trim(OnlineCustomerAuth.email)) ==
            normalized_login_email
        ).first()

    if not user or not verify_password(data.password, user.password):
        record_login_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    record_login_success(ip)
    token = create_access_token({"sub": str(user.id), "role": ROLE_CUSTOMER})
    return {
        "access_token": token,
        "token_type": "bearer",
        "customer_id": user.id,
        "name": user.user_name,
        "email": user.email,
        "phone": user.phone,
        "address": user.address,
        "city": user.city,
        "customer": {
            "id": user.id,
            "name": user.user_name,
            "email": user.email,
            "phone": user.phone,
            "address": user.address,
            "city": user.city,
        },
    }


@router.get("/customer/me")
def get_current_customer(
    db: Session = Depends(get_db),
    current_user: dict = Depends(customer_only),
):
    """Return the authenticated storefront customer's account profile."""
    customer_id = int(current_user["user_id"])
    user = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.id == customer_id,
        OnlineCustomerAuth.is_active == True,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Customer account is no longer available.")

    return {
        "customer": {
            "id": user.id,
            "name": user.user_name,
            "email": user.email,
            "phone": user.phone,
            "address": user.address,
            "city": user.city,
        }
    }


@router.post("/customer/login/phone")
def customer_login_phone(
    data: CustomerLoginPhone,
    request: Request,
    db: Session = Depends(get_db),
):
    """Customer login via phone number — returns JWT with CUSTOMER role"""
    ip = request.client.host
    check_login_lockout(ip)

    user = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.phone == data.phone).first()
    if not user or not verify_password(data.password, user.password):
        record_login_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid phone or password.")

    record_login_success(ip)
    token = create_access_token({"sub": str(user.id), "role": ROLE_CUSTOMER})
    return {
        "access_token": token,
        "token_type": "bearer",
        "customer_id": user.id,
        "name": user.user_name,
        "email": user.email,
        "phone": user.phone,
    }


def _customer_reset_generic_message():
    return {
        "message": "If this account is registered with an email, a password reset OTP has been sent."
    }


def _generate_customer_reset_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def _customer_reset_token_hash(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


@router.post("/customer/request-password-reset-otp")
def request_customer_password_reset_otp(
    data: CustomerPasswordResetOtpRequest,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
):
    """Generate and email a backend-owned OTP for an online customer."""
    normalized_email = data.email.strip().lower()

    # Match normalized input against normalized stored data. This handles
    # existing accounts whose email was stored with different casing or
    # accidental leading/trailing spaces before registration was normalized.
    user = db.query(OnlineCustomerAuth).filter(
        func.lower(func.trim(OnlineCustomerAuth.email)) == normalized_email
    ).first()

    # Keep enumeration-resistant response behavior, but do not make the
    # frontend believe an OTP was sent when this customer has no matching
    # account/email. The caller can keep the same generic wording while using
    # success=false to avoid advancing to OTP verification.
    if not user or not user.email or not EmailNotificationService:
        return {
            "success": False,
            "email_sent": False,
            **_customer_reset_generic_message(),
        }

    existing = db.query(CustomerPasswordResetOtp).filter(
        CustomerPasswordResetOtp.customer_id == user.id,
        CustomerPasswordResetOtp.used == False,
    ).all()
    for challenge in existing:
        challenge.used = True

    otp = _generate_customer_reset_otp()
    challenge = CustomerPasswordResetOtp(
        customer_id=user.id,
        otp_hash=_customer_reset_token_hash(otp),
        otp_expires_at=datetime.utcnow() + timedelta(minutes=10),
        otp_attempts=0,
        verified_at=None,
        reset_token_hash=None,
        reset_token_expires_at=None,
        used=False,
    )
    db.add(challenge)

    subject, body = EmailNotificationService.send_otp_template(
        otp,
        "Customer Password Reset",
    )

    try:
        sent = EmailNotificationService.send_email(
            recipient_email=user.email,
            subject=subject,
            body=body,
        )
        if not sent:
            db.rollback()
            logger.error(
                "Customer password reset OTP delivery failed for customer_id=%s email=%s",
                user.id,
                user.email,
            )
            raise HTTPException(
                status_code=503,
                detail="Password reset email could not be delivered. Please try again later.",
            )

        db.commit()
        return {
            "success": True,
            "email_sent": True,
            **_customer_reset_generic_message(),
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception(
            "Customer password reset OTP request failed for customer_id=%s",
            user.id,
        )
        raise HTTPException(
            status_code=503,
            detail="Password reset email could not be delivered. Please try again later.",
        )


@router.post("/customer/verify-password-reset-otp")
def verify_customer_password_reset_otp(
    data: CustomerVerifyPasswordResetOtp,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
):
    """Verify the backend-generated OTP and issue a short-lived reset token."""
    normalized_email = data.email.strip().lower()

    user = db.query(OnlineCustomerAuth).filter(
        func.lower(func.trim(OnlineCustomerAuth.email)) == normalized_email
    ).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset OTP.",
        )

    challenge = db.query(CustomerPasswordResetOtp).filter(
        CustomerPasswordResetOtp.customer_id == user.id,
        CustomerPasswordResetOtp.used == False,
        CustomerPasswordResetOtp.otp_expires_at > datetime.utcnow(),
    ).order_by(CustomerPasswordResetOtp.id.desc()).with_for_update().first()

    if not challenge:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset OTP.",
        )

    if challenge.otp_attempts >= 5:
        challenge.used = True
        db.commit()
        raise HTTPException(
            status_code=429,
            detail="Too many incorrect OTP attempts. Request a new OTP.",
        )

    if challenge.otp_hash != _customer_reset_token_hash(data.otp):
        challenge.otp_attempts += 1
        if challenge.otp_attempts >= 5:
            challenge.used = True
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset OTP.",
        )

    reset_token = secrets.token_urlsafe(48)
    challenge.reset_token_hash = _customer_reset_token_hash(reset_token)
    challenge.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=10)
    challenge.verified_at = datetime.utcnow()
    challenge.otp_attempts = challenge.otp_attempts
    db.commit()

    return {
        "message": "OTP verified successfully.",
        "reset_token": reset_token,
        "expires_in": 600,
    }


@router.post("/customer/reset-password")
def reset_customer_password(
    data: CustomerResetPassword,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
):
    """Consume the verified OTP reset token and set the customer password."""
    token_hash = _customer_reset_token_hash(data.reset_token)

    challenge = db.query(CustomerPasswordResetOtp).filter(
        CustomerPasswordResetOtp.reset_token_hash == token_hash,
        CustomerPasswordResetOtp.used == False,
        CustomerPasswordResetOtp.verified_at.isnot(None),
        CustomerPasswordResetOtp.reset_token_expires_at > datetime.utcnow(),
    ).with_for_update().first()

    if not challenge:
        raise HTTPException(
            status_code=400,
            detail="Password reset authorization is invalid or expired. Request a new OTP.",
        )

    user = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.id == challenge.customer_id
    ).with_for_update().first()

    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Customer account is unavailable.")

    user.password = hash_password(data.new_password)
    challenge.used = True

    db.query(CustomerPasswordResetOtp).filter(
        CustomerPasswordResetOtp.customer_id == user.id,
        CustomerPasswordResetOtp.id != challenge.id,
        CustomerPasswordResetOtp.used == False,
    ).update({"used": True}, synchronize_session=False)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to reset password. Please try again.",
        )

    return {
        "message": "Password reset successfully. You can now sign in with your new password."
    }


@router.post("/customer/forgot-password")
def forgot_password(
    data: CustomerForgot,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
):
    """Compatibility alias for clients that still call /forgot-password."""
    if not data.email:
        return _customer_reset_generic_message()
    request = CustomerPasswordResetOtpRequest(email=data.email)
    return request_customer_password_reset_otp(request, db, _rl)


# =====================
# SHOP DISCOVERY
# =====================
@router.get("/marketplace/search")
def marketplace_search(
    q: str = Query("", max_length=80),
    mode: str = Query("all", pattern=r"^(all|shops|products)$"),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Global online marketplace search.

    Only shops that explicitly enabled online shopping are visible.
    """
    query = sanitize_input(q or "", "q").strip()
    shops = []
    products = []

    if not query:
        shop_rows = (
            db.query(ShopProfile)
            .filter(
                ShopProfile.is_online_store_enabled == True,
                (ShopProfile.is_active == True) | (ShopProfile.is_active.is_(None)),
            )
            .order_by(ShopProfile.shop_name.asc())
            .limit(limit)
            .all()
        )
    else:
        like = f"%{query}%"
        shop_rows = (
            db.query(ShopProfile)
            .filter(
                ShopProfile.is_online_store_enabled == True,
                (ShopProfile.is_active == True) | (ShopProfile.is_active.is_(None)),
                or_(
                    ShopProfile.shop_name.ilike(like),
                    ShopProfile.shop_type.ilike(like),
                    ShopProfile.shop_categories.ilike(like),
                    ShopProfile.shop_tagline.ilike(like),
                    ShopProfile.shop_description.ilike(like),
                    ShopProfile.city.ilike(like),
                    ShopProfile.address.ilike(like),
                ),
            )
            .order_by(ShopProfile.shop_name.asc())
            .limit(limit)
            .all()
        )

    if mode in ("all", "shops"):
        shops = [
            {
                "shop_id": shop.shop_id,
                "shop_name": shop.shop_name,
                "tagline": shop.shop_tagline or "",
                "description": shop.shop_description or "",
                "shop_type": shop.shop_type or "General",
                "address": shop.address or "",
                "city": shop.city or "",
                "state": shop.state or "",
                "postal_code": shop.postal_code or "",
                "phone": shop.phone or "",
                "website": shop.website or "",
                "logo_url": shop.logo_url,
                "categories": (
                    [item.strip() for item in str(shop.shop_categories or "").split(",") if item.strip()]
                    if shop.shop_categories and not str(shop.shop_categories).strip().startswith("[")
                    else shop.shop_categories
                ),
                "online_setup_fee": float(getattr(shop, "online_setup_fee", 0) or 0),
                "min_order": float(getattr(shop, "online_min_order", 0) or 0),
                "delivery_fee": float(getattr(shop, "online_delivery_fee", 0) or 0),
                "offer_delivery": bool(getattr(shop, "online_offer_delivery", True)),
                "offer_pickup": bool(getattr(shop, "online_offer_pickup", True)),
                "accept_cod": bool(getattr(shop, "online_accept_cod", True)),
                "accept_online": bool(getattr(shop, "online_accept_online", False)),
                **_shop_reputation(shop),
            }
            for shop in shop_rows
        ]

    if mode in ("all", "products") and query:
        tokens = _shopping_tokens(query)
        max_price = _extract_max_price(query)
        conditions = []
        for token in tokens or [query.lower()]:
            token_like = f"%{token}%"
            conditions.append(
                or_(
                    Product.product_name.ilike(token_like),
                    Product.category.ilike(token_like),
                    Product.description.ilike(token_like),
                )
            )
        product_query = (
            db.query(Product, ShopProfile)
            .join(ShopProfile, ShopProfile.shop_id == Product.user_id)
            .filter(
                ShopProfile.is_online_store_enabled == True,
                (ShopProfile.is_active == True) | (ShopProfile.is_active.is_(None)),
                Product.is_active == True,
                Product.current_stock > 0,
                or_(*conditions),
            )
        )
        if max_price is not None:
            product_query = product_query.filter(Product.unit_price <= max_price)
        rows = product_query.order_by(Product.unit_price.asc()).limit(limit * 3).all()
        products = [
            {
                "product_id": product.id,
                "product_name": product.product_name,
                "category": product.category,
                "price": float(product.unit_price),
                "stock_available": int(product.current_stock or 0),
                "shop_id": shop.shop_id,
                "shop_name": shop.shop_name,
                "shop_address": shop.address or "",
                "online_setup_fee": float(getattr(shop, "online_setup_fee", 0) or 0),
                "delivery_fee": float(getattr(shop, "online_delivery_fee", 0) or 0),
                "min_order": float(getattr(shop, "online_min_order", 0) or 0),
                **_shop_reputation(shop),
            }
            for product, shop in rows
        ]

    return {"query": query, "mode": mode, "shops": shops, "products": products}


@router.get("/ai/recommend")
def ai_shopping_recommendations(
    q: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(10, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Customer shopping assistant.

    This is a deterministic AI-style ranking layer: it understands common
    shopping intents (cheap/budget/under-price/highest-rated) and searches
    every online-enabled shop before ranking the best matches.
    """
    query = sanitize_input(q, "q").strip()
    lower = query.lower()
    wants_low_price = any(word in lower for word in ("cheap", "cheapest", "low price", "lowest price", "budget", "affordable"))
    wants_rating = any(word in lower for word in ("best", "highest rated", "top rated", "rating", "rated"))
    max_price = _extract_max_price(query)
    tokens = _shopping_tokens(query)

    conditions = []
    for token in tokens or [query.lower()]:
        like = f"%{token}%"
        conditions.append(
            or_(
                Product.product_name.ilike(like),
                Product.category.ilike(like),
                Product.description.ilike(like),
            )
        )

    product_query = (
        db.query(Product, ShopProfile)
        .join(ShopProfile, ShopProfile.shop_id == Product.user_id)
        .filter(
            ShopProfile.is_online_store_enabled == True,
            (ShopProfile.is_active == True) | (ShopProfile.is_active.is_(None)),
            Product.is_active == True,
            Product.current_stock > 0,
            or_(*conditions),
        )
    )
    if max_price is not None:
        product_query = product_query.filter(Product.unit_price <= max_price)

    rows = product_query.limit(250).all()
    candidates = []
    for product, shop in rows:
        rating = float(getattr(shop, "rating_score", 0.0) or 0.0)
        rating_count = int(getattr(shop, "rating_count", 0) or 0)
        price = float(product.unit_price)
        candidates.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "category": product.category,
            "price": price,
            "stock_available": int(product.current_stock or 0),
            "shop_id": shop.shop_id,
            "shop_name": shop.shop_name,
            "shop_address": shop.address or "",
            "rating": round(rating, 2),
            "rating_count": rating_count,
        })

    if wants_low_price:
        candidates.sort(key=lambda x: (x["price"], -x["rating"], -x["rating_count"]))
    elif wants_rating:
        candidates.sort(key=lambda x: (-x["rating"], -x["rating_count"], x["price"]))
    else:
        candidates.sort(key=lambda x: (x["price"], -x["rating"], -x["rating_count"]))

    recommendations = candidates[:limit]
    if not recommendations:
        response = "I couldn't find that product in any shop that has Online Shopping enabled."
    elif wants_low_price:
        response = f"I found {len(recommendations)} matching options and ranked them by lowest price, then shop rating."
    elif wants_rating:
        response = f"I found {len(recommendations)} matching options and ranked them by shop rating, then price."
    else:
        response = f"I found {len(recommendations)} matching options and ranked them by price and shop rating."

    return {
        "query": query,
        "intent": {
            "low_price": wants_low_price,
            "rating_priority": wants_rating,
            "max_price": max_price,
        },
        "response": response,
        "recommendations": recommendations,
    }


@router.get("/shops")
def list_online_shops(
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """List all public online-enabled shops for customer web/app discovery."""
    rows = (
        db.query(ShopProfile)
        .filter(
            ShopProfile.is_online_store_enabled == True,
            (ShopProfile.is_active == True) | (ShopProfile.is_active.is_(None)),
        )
        .order_by(ShopProfile.shop_name.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "shops": [
            {
                "shop_id": shop.shop_id,
                "shop_name": shop.shop_name,
                "shop_type": shop.shop_type or "General",
                "tagline": shop.shop_tagline or "",
                "description": shop.shop_description or "",
                "address": shop.address or "",
                "city": shop.city or "",
                "state": shop.state or "",
                "postal_code": shop.postal_code or "",
                "phone": shop.phone or "",
                "email": shop.email or "",
                "website": shop.website or "",
                "logo_url": shop.logo_url,
                "categories": _safe_json_list(shop.shop_categories) if '_safe_json_list' in globals() else [],
                **_shop_reputation(shop),
            }
            for shop in rows
        ],
        "count": len(rows),
    }


@router.get("/shops/nearby")
def find_nearby_shops(
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 5.0,
    skip: int = 0,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """
    Find shops near a location.
    Supports two modes:
    1. ?city=Mumbai — simple string matching
    2. ?lat=19.0&lng=72.8&radius_km=5 — GPS radius (Haversine formula)
    Only returns shops with is_online_store_enabled=True
    """
    query = db.query(ShopProfile).filter(ShopProfile.is_online_store_enabled == True, (ShopProfile.is_active == True) | (ShopProfile.is_active.is_(None)))

    if city:
        city_clean = sanitize_input(city, "city")
        query = query.filter(ShopProfile.address.ilike(f"%{city_clean}%"))

    if lat is not None and lng is not None:
        # Bounding box pre-filter for DB speed (BUG-B12)
        # 1 degree lat is approx 111 km
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * math.cos(math.radians(lat))) if math.cos(math.radians(lat)) != 0 else 0
        
        query = query.filter(
            ShopProfile.latitude != None,
            ShopProfile.longitude != None,
            ShopProfile.latitude.between(lat - lat_delta, lat + lat_delta),
            ShopProfile.longitude.between(lng - lng_delta, lng + lng_delta)
        )
        
    all_shops = query.all()

    if lat is not None and lng is not None:
        # Filter exact distance by Haversine
        def haversine(lat1, lon1, lat2, lon2):
            """Calculate distance in km between two lat/lng points"""
            if lat2 is None or lon2 is None: return float("inf")
            R = 6371  # Earth radius in km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        all_shops = [s for s in all_shops if haversine(lat, lng, s.latitude, s.longitude) <= radius_km]

    all_shops = all_shops[skip:skip + limit]

    return {
        "shops": [
            {
                "shop_id": s.shop_id,
                "shop_name": s.shop_name,
                "address": s.address,
                "phone": s.phone,
                "logo_url": s.logo_url,
                "shop_type": s.shop_type or "General",
                "tagline": s.shop_tagline or "",
                "description": s.shop_description or "",
                "city": s.city or "",
                "state": s.state or "",
                "website": s.website or "",
                **_shop_reputation(s),
            }
            for s in all_shops
        ],
        "count": len(all_shops),
    }


@router.get("/shops/{shop_id}/products")
def browse_shop_products(
    shop_id: str,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """Browse products for a specific online shop"""
    try:
        shop_id_int = int(''.join(filter(str.isdigit, shop_id))) if any(c.isdigit() for c in shop_id) else 1
    except ValueError:
        shop_id_int = 1

    # Marketplace visibility is opt-in: disabled shops are never exposed.
    profile = db.query(ShopProfile).filter(
        ShopProfile.shop_id == shop_id_int,
        ShopProfile.is_online_store_enabled == True,
        (ShopProfile.is_active == True) | (ShopProfile.is_active.is_(None)),
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Shop not found or Online Shopping is disabled.")

    # Show ALL active products (even if stock is 0 — shopkeeper may not have updated)
    q = db.query(Product).filter(
        Product.user_id == shop_id_int,
        Product.is_active == True,
    )
    if category:
        q = q.filter(Product.category == category)

    products = q.offset(skip).limit(limit).all()

    return {
        "shop_name": profile.shop_name,
        "shop_tagline": profile.shop_tagline or "",
        "shop_description": profile.shop_description or "",
        "shop_type": profile.shop_type or "General",
        "shop_phone": profile.phone or "",
        "shop_website": profile.website or "",
        "shop_address": profile.address or "",
        "shop_city": profile.city or "",
        "shop_state": profile.state or "",
        "shop_postal_code": profile.postal_code or "",
        "shop_logo_url": profile.logo_url,
        "shop_categories": profile.shop_categories or "",
        "rating": round(float(getattr(profile, "rating_score", 0.0) or 0.0), 2),
        "rating_count": int(getattr(profile, "rating_count", 0) or 0),
        "online_setup_fee": float(getattr(profile, "online_setup_fee", 0) or 0),
        "min_order": float(getattr(profile, "online_min_order", 0) or 0),
        "delivery_fee": float(getattr(profile, "online_delivery_fee", 0) or 0),
        "offer_delivery": bool(getattr(profile, "online_offer_delivery", True)),
        "offer_pickup": bool(getattr(profile, "online_offer_pickup", True)),
        "accept_cod": bool(getattr(profile, "online_accept_cod", True)),
        "accept_online": bool(getattr(profile, "online_accept_online", False)),
        "is_online": True,
        "products": [
            (lambda p, discount: {
                "id": p.id,
                "name": p.product_name,
                "category": p.category,
                "price": round(float(p.unit_price) * (1.0 - discount / 100.0), 2) if discount > 0 else float(p.unit_price),
                "original_price": float(p.unit_price),
                "discount_pct": discount,
                "flash_sale_active": discount > 0,
                "stock_available": p.current_stock if p.current_stock is not None else 999,
                "description": p.description,
            })(p, get_active_discount(db, shop_id_int, p.category))
            for p in products
        ],
    }


# =====================
# ORDER PLACEMENT
# =====================
@router.post("/order")
def place_order(
    data: PlaceOrder,
    db: Session = Depends(get_db),
    current_user: dict = Depends(customer_only),
    _rl: None = Depends(check_rate_limit),
):
    """Place an online order at a specific shop"""
    customer_id = current_user["user_id"]

    idempotency_key = (data.idempotency_key or "").strip() or None
    if idempotency_key:
        existing_order = db.query(OnlineOrder).filter(
            OnlineOrder.shop_id == data.shop_id,
            OnlineOrder.customer_id == customer_id,
            OnlineOrder.idempotency_key == idempotency_key,
        ).first()
        if existing_order:
            profile = db.query(ShopProfile).filter(
                ShopProfile.shop_id == data.shop_id
            ).first()
            return {
                "message": "Order already placed.",
                "order_id": existing_order.id,
                "shop_name": profile.shop_name if profile else "",
                "total_amount": float(existing_order.total_amount),
                "items": json.loads(existing_order.items_json),
                "status": existing_order.order_status,
                "duplicate": True,
            }

    # Online ordering is opt-in and enforced server-side.
    profile = db.query(ShopProfile).filter(
        ShopProfile.shop_id == data.shop_id,
        ShopProfile.is_online_store_enabled == True,
        (ShopProfile.is_active == True) | (ShopProfile.is_active.is_(None)),
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Shop not found or Online Shopping is disabled.")

    # Validate all items and calculate subtotal. Add the configured online-only
    # setup fee once per order; never alter the product/POS price.
    order_items = []
    inventory_changes = []
    items_subtotal = 0.0

    for item in data.items:
        product = db.query(Product).with_for_update().filter(
            Product.id == item.product_id,
            Product.user_id == data.shop_id,
            Product.is_active == True,
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found in this shop.")
        if product.current_stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.product_name}'. Available: {product.current_stock}"
            )
        product.current_stock -= item.quantity
        inventory_changes.append({
            "product_id": product.id,
            "quantity": item.quantity,
            "new_stock": float(product.current_stock),
        })
        discount = get_active_discount(db, data.shop_id, product.category)
        price = float(product.unit_price)
        if discount > 0:
            price = round(price * (1.0 - discount / 100.0), 2)
        line_total = price * item.quantity
        items_subtotal += line_total
        order_items.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": item.quantity,
            "unit_price": price,
            "line_total": line_total,
            "discount_pct": discount,
        })

    delivery_address = sanitize_input(data.delivery_address, "delivery_address")
    online_setup_fee = round(float(getattr(profile, "online_setup_fee", 0) or 0), 2)
    min_order = round(float(getattr(profile, "online_min_order", 0) or 0), 2)
    delivery_fee = round(float(getattr(profile, "online_delivery_fee", 0) or 0), 2)
    offer_delivery = bool(getattr(profile, "online_offer_delivery", True))
    offer_pickup = bool(getattr(profile, "online_offer_pickup", True))
    accept_cod = bool(getattr(profile, "online_accept_cod", True))
    accept_online = bool(getattr(profile, "online_accept_online", False))

    if min_order > 0 and items_subtotal < min_order:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum online order is ₹{min_order:.2f}. Add ₹{max(0.0, min_order - items_subtotal):.2f} more.",
        )
    if not offer_delivery and not offer_pickup:
        raise HTTPException(status_code=400, detail="This shop is not accepting online delivery or pickup orders.")
    if not accept_cod and not accept_online:
        raise HTTPException(status_code=400, detail="This shop has no online payment method enabled.")

    discount_amount = 0.0
    coupon_code = (data.coupon_code or "").strip().upper() or None

    if coupon_code:
        from models import RetailCoupon
        from growth_suite import _coupon_value
        coupon = db.query(RetailCoupon).filter(
            RetailCoupon.shop_id == data.shop_id,
            RetailCoupon.code == coupon_code,
            RetailCoupon.is_active.is_(True),
        ).first()
        now = datetime.now(timezone.utc)
        if not coupon:
            raise HTTPException(status_code=400, detail="Invalid or inactive coupon.")
        if coupon.starts_at and coupon.starts_at > now:
            raise HTTPException(status_code=400, detail="Coupon is not active yet.")
        if coupon.expires_at and coupon.expires_at < now:
            raise HTTPException(status_code=400, detail="Coupon has expired.")
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise HTTPException(status_code=400, detail="Coupon usage limit reached.")
        discount_amount = _coupon_value(coupon, items_subtotal)
        if discount_amount <= 0:
            raise HTTPException(status_code=400, detail="Order does not meet the coupon requirements.")
        coupon.used_count = int(coupon.used_count or 0) + 1

    delivery_charge = delivery_fee if offer_delivery else 0.0
    total_amount = round(
        max(0.0, items_subtotal - discount_amount)
        + online_setup_fee
        + delivery_charge,
        2,
    )

    order = OnlineOrder(
        shop_id=data.shop_id,
        customer_id=customer_id,
        total_amount=total_amount,
        online_setup_fee=online_setup_fee,
        coupon_code=coupon_code,
        discount_amount=discount_amount,
        delivery_address=delivery_address,
        items_json=json.dumps(order_items),
        order_status="PENDING",
        idempotency_key=idempotency_key,
    )
    db.add(order)
    try:
        db.commit()
        db.refresh(order)
    except Exception as e:
        logger.error(f"Failed to save online order (shop_id={data.shop_id}, customer_id={customer_id}): {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to place order right now. Please try again later.")

    publish_realtime_event({
        "event_id": str(uuid4()),
        "type": "order.created",
        "shop_id": data.shop_id,
        "order_id": order.id,
        "customer_id": customer_id,
        "status": "PENDING",
        "total_amount": float(total_amount),
    })
    publish_realtime_event({
        "event_id": str(uuid4()),
        "type": "inventory.changed",
        "shop_id": data.shop_id,
        "reference_type": "ONLINE_ORDER",
        "reference_id": str(order.id),
        "changes": inventory_changes,
    })

    return {
        "message": "Order placed successfully! The shop will confirm shortly.",
        "order_id": order.id,
        "shop_name": profile.shop_name,
        "subtotal": round(items_subtotal, 2),
        "discount_amount": discount_amount,
        "coupon_code": coupon_code,
        "online_setup_fee": online_setup_fee,
        "delivery_fee": delivery_charge,
        "min_order": min_order,
        "accept_cod": accept_cod,
        "accept_online": accept_online,
        "total_amount": total_amount,
        "items": order_items,
        "status": "PENDING",
    }


@router.post("/guest-order")
def place_guest_order(
    data: GuestOrder,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
):
    """Place an online order as a guest (no auth required)"""
    logger.info(f"Received guest order: shop_id={data.shop_id}, customer={data.customer_name}, phone={data.phone}, items_count={len(data.items)}")
    
    # 1. Verify Firebase Phone Auth Token (if provided)
    if data.firebase_id_token:
        try:
            import firebase_admin
            if not firebase_admin._apps:
                raise HTTPException(status_code=503, detail="Firebase not configured. Please contact support.")
                
            from firebase_admin import auth
            decoded_token = auth.verify_id_token(data.firebase_id_token)
            phone_number = decoded_token.get('phone_number')
            
            if not phone_number:
                raise HTTPException(status_code=400, detail="Invalid token: No phone number associated with this login.")
                
            # Ensure the verified phone matches the one provided (stripping non-digits for comparison if needed, or exact match)
            # Firebase phone numbers include country code (e.g., +919876543210).
            # We check if the provided phone is a substring of the verified phone to allow local format (e.g., 9876543210)
            if data.phone not in phone_number:
                logger.warning(f"Verified phone number does not match provided phone number: {data.phone} vs {phone_number}")
                
        except HTTPException:
            raise  # Re-raise — a rejected token must not silently fall through
        except Exception as e:
            logger.error(f"Firebase token verification failed: {e}")
            logger.warning("Falling back to unverified phone number for guest order.")
    else:
        logger.info(f"No Firebase token provided for guest checkout, proceeding with unverified phone {data.phone}")

    idempotency_key = (data.idempotency_key or "").strip() or None
    if idempotency_key:
        existing_order = db.query(OnlineOrder).filter(
            OnlineOrder.shop_id == data.shop_id,
            OnlineOrder.idempotency_key == idempotency_key,
        ).first()
        if existing_order:
            existing_customer = db.query(OnlineCustomerAuth).filter(
                OnlineCustomerAuth.id == existing_order.customer_id
            ).first()
            if existing_customer and existing_customer.phone == data.phone:
                profile = db.query(ShopProfile).filter(
                    ShopProfile.shop_id == data.shop_id
                ).first()
                return {
                    "message": "Guest order already placed.",
                    "order_id": existing_order.id,
                    "shop_name": profile.shop_name if profile else "",
                    "total_amount": float(existing_order.total_amount),
                    "items": json.loads(existing_order.items_json),
                    "status": existing_order.order_status,
                    "duplicate": True,
                }

    # 2. Validate shop
    try:
        profile = db.query(ShopProfile).filter(
            ShopProfile.shop_id == data.shop_id,
            ShopProfile.is_online_store_enabled == True,
        ).first()
        if not profile:
            logger.error(f"Shop not found or Online Shopping disabled: shop_id={data.shop_id}")
            raise HTTPException(
                status_code=404,
                detail="Shop not found or Online Shopping is disabled.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating shop: {e}")
        raise HTTPException(status_code=500, detail="Error validating shop.")

    # 3. Find or create guest customer in OnlineCustomerAuth
    customer = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.phone == data.phone).first()
    if not customer:
        import secrets
        customer = OnlineCustomerAuth(
            user_name=sanitize_input(data.customer_name, "name"),
            email=f"guest_{data.phone}@example.com",
            phone=data.phone,
            address=sanitize_input(data.delivery_address, "address"),
            password=hash_password(secrets.token_urlsafe(32)),
            is_active=False  # Mark as guest/inactive
        )
        db.add(customer)
        try:
            db.commit()
            db.refresh(customer)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to register guest customer: {str(e)}")
        
    customer_id = customer.id

    # 3. Validate items and calculate subtotal
    order_items = []
    inventory_changes = []
    items_subtotal = 0.0

    for item in data.items:
        product = db.query(Product).with_for_update().filter(
            Product.id == item.product_id,
            Product.user_id == data.shop_id,
            Product.is_active == True,
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found.")
        if product.current_stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.product_name}'. Available: {product.current_stock}"
            )
        product.current_stock -= item.quantity
        inventory_changes.append({
            "product_id": product.id,
            "quantity": item.quantity,
            "new_stock": float(product.current_stock),
        })
        discount = get_active_discount(db, data.shop_id, product.category)
        price = float(product.unit_price)
        if discount > 0:
            price = round(price * (1.0 - discount / 100.0), 2)
        line_total = price * item.quantity
        items_subtotal += line_total
        order_items.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": item.quantity,
            "unit_price": price,
            "line_total": line_total,
            "discount_pct": discount,
        })

    # 4. Create Order
    online_setup_fee = round(float(getattr(profile, "online_setup_fee", 0) or 0), 2)
    discount_amount = 0.0
    coupon_code = (data.coupon_code or "").strip().upper() or None
    if coupon_code:
        from models import RetailCoupon
        from growth_suite import _coupon_value
        coupon = db.query(RetailCoupon).filter(
            RetailCoupon.shop_id == data.shop_id,
            RetailCoupon.code == coupon_code,
            RetailCoupon.is_active.is_(True),
        ).first()
        now = datetime.now(timezone.utc)
        if not coupon:
            raise HTTPException(status_code=400, detail="Invalid or inactive coupon.")
        if coupon.starts_at and coupon.starts_at > now:
            raise HTTPException(status_code=400, detail="Coupon is not active yet.")
        if coupon.expires_at and coupon.expires_at < now:
            raise HTTPException(status_code=400, detail="Coupon has expired.")
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise HTTPException(status_code=400, detail="Coupon usage limit reached.")
        discount_amount = _coupon_value(coupon, items_subtotal)
        if discount_amount <= 0:
            raise HTTPException(status_code=400, detail="Order does not meet the coupon requirements.")
        coupon.used_count = int(coupon.used_count or 0) + 1

    total_amount = round(max(0.0, items_subtotal - discount_amount) + online_setup_fee, 2)
    order = OnlineOrder(
        shop_id=data.shop_id,
        customer_id=customer_id,
        total_amount=total_amount,
        online_setup_fee=online_setup_fee,
        coupon_code=coupon_code,
        discount_amount=discount_amount,
        delivery_address=sanitize_input(data.delivery_address, "address"),
        items_json=json.dumps(order_items),
        order_status="PENDING",
        idempotency_key=idempotency_key,
    )
    db.add(order)
    try:
        db.commit()
        db.refresh(order)
    except Exception as e:
        logger.error(f"Failed to save guest order (shop_id={data.shop_id}, phone={data.phone}): {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to place your order right now. Please try again later.")
    
    # 5. Send FCM Push Notification to Shop Owner
    try:
        from firebase_admin import messaging
        shop_owner = db.query(User).filter(User.id == data.shop_id).first()
        if shop_owner and shop_owner.fcm_token:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="New Online Order! 🎉",
                    body=f"You received a new order for ₹{total_amount:.2f} from {customer.user_name}.",
                ),
                data={
                    "order_id": str(order.id),
                    "type": "NEW_ORDER"
                },
                token=shop_owner.fcm_token,
            )
            messaging.send(message)
            logger.info(f"FCM notification sent to shop owner {shop_owner.id}")
    except Exception as e:
        logger.error(f"Failed to send FCM notification: {e}")

    publish_realtime_event({
        "event_id": str(uuid4()),
        "type": "order.created",
        "shop_id": data.shop_id,
        "order_id": order.id,
        "customer_id": customer.id,
        "status": "PENDING",
        "total_amount": float(total_amount),
    })
    publish_realtime_event({
        "event_id": str(uuid4()),
        "type": "inventory.changed",
        "shop_id": data.shop_id,
        "reference_type": "ONLINE_ORDER",
        "reference_id": str(order.id),
        "changes": inventory_changes,
    })

    return {
        "message": "Guest order placed successfully!",
        "order_id": order.id,
        "shop_name": profile.shop_name,
        "discount_amount": discount_amount,
        "coupon_code": coupon_code,
        "online_setup_fee": online_setup_fee,
        "total_amount": total_amount,
        "status": "PENDING",
    }


@router.get("/my-orders")
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(customer_only),
):
    """Customer: View all their orders plus any verified review left for each delivered order."""
    customer_id = current_user["user_id"]
    orders = db.query(OnlineOrder).filter(
        OnlineOrder.customer_id == customer_id
    ).order_by(OnlineOrder.created_at.desc()).all()

    order_ids = [o.id for o in orders]
    reviews_by_order = {}
    return_by_order = {}
    if order_ids:
        review_rows = db.query(ShopReview).filter(ShopReview.order_id.in_(order_ids)).all()
        reviews_by_order = {r.order_id: r for r in review_rows}

        return_rows = (
            db.query(OnlineOrderReturn)
            .filter(OnlineOrderReturn.order_id.in_(order_ids))
            .order_by(OnlineOrderReturn.created_at.desc())
            .all()
        )
        # Keep the most recent return request for each order.
        for return_row in return_rows:
            if return_row.order_id not in return_by_order:
                return_by_order[return_row.order_id] = return_row

    return {
        "orders": [
            {
                "order_id": o.id,
                "shop_id": o.shop_id,
                "shop_name": (
                    db.query(ShopProfile.shop_name)
                    .filter(ShopProfile.shop_id == o.shop_id)
                    .scalar()
                    or f"Shop #{o.shop_id}"
                ),
                "status": o.order_status,
                "subtotal": round(float(o.total_amount) - float(getattr(o, "online_setup_fee", 0) or 0), 2),
                "online_setup_fee": float(getattr(o, "online_setup_fee", 0) or 0),
                "total_amount": float(o.total_amount),
                "delivery_address": o.delivery_address,
                "items": json.loads(o.items_json),
                "created_at": o.created_at,
                "review": (
                    {
                        "rating": review.rating,
                        "comment": review.comment,
                        "created_at": review.created_at,
                    }
                    if (review := reviews_by_order.get(o.id))
                    else None
                ),
                "can_cancel": o.order_status in {"PENDING", "ACCEPTED"},
                "return_request": (
                    {
                        "id": return_req.id,
                        "status": return_req.status,
                        "reason": return_req.reason,
                        "refund_amount": float(return_req.refund_amount or 0),
                        "stock_restored": bool(return_req.stock_restored),
                        "created_at": return_req.created_at,
                        "processed_at": return_req.processed_at,
                    }
                    if (return_req := return_by_order.get(o.id))
                    else None
                ),
            }
            for o in orders
        ]
    }


@router.post("/order/{order_id}/cancel")
def cancel_customer_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(customer_only),
):
    """Customer cancellation before the order has been dispatched."""
    customer_id = current_user["user_id"]
    order = db.query(OnlineOrder).with_for_update().filter(
        OnlineOrder.id == order_id,
        OnlineOrder.customer_id == customer_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.order_status not in {"PENDING", "ACCEPTED"}:
        raise HTTPException(
            status_code=409,
            detail="This order can no longer be cancelled. Only pending or accepted orders can be cancelled.",
        )

    previous_status = order.order_status
    shop_id = order.shop_id
    _reverse_online_order_financials(db, order, shop_id, "Customer cancellation")

    order.order_status = "CANCELLED"
    db.commit()

    publish_realtime_event({
        "event_id": str(uuid4()),
        "type": "order.status_changed",
        "shop_id": shop_id,
        "order_id": order.id,
        "customer_id": customer_id,
        "previous_status": previous_status,
        "status": "CANCELLED",
        "total_amount": float(order.total_amount),
        "delivery_address": order.delivery_address,
        "items": json.loads(order.items_json),
        "created_at": order.created_at,
    })

    return {
        "success": True,
        "message": "Order cancelled successfully.",
        "order_id": order.id,
        "status": "CANCELLED",
    }


@router.get("/order/{order_id}/track")
def track_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dict),
):
    """Track a specific order by ID"""
    order = db.query(OnlineOrder).filter(OnlineOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Security: only the customer who placed the order or the shop owner can view it
    uid = current_user["user_id"]
    role = current_user.get("role", ROLE_OWNER)
    if role == ROLE_CUSTOMER and order.customer_id != uid:
        raise HTTPException(status_code=403, detail="You do not have access to this order.")
    if role == ROLE_OWNER and order.shop_id != uid:
        raise HTTPException(status_code=403, detail="You do not have access to this order.")

    STATUS_STEPS = ["PENDING", "ACCEPTED", "DISPATCHED", "DELIVERED"]
    current_step = STATUS_STEPS.index(order.order_status) if order.order_status in STATUS_STEPS else 0

    customer = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.id == order.customer_id
    ).first()
    shop_name = (
        db.query(ShopProfile.shop_name)
        .filter(ShopProfile.shop_id == order.shop_id)
        .scalar()
        or f"Shop #{order.shop_id}"
    )

    return {
        "order_id": order.id,
        "shop_id": order.shop_id,
        "shop_name": shop_name,
        "status": order.order_status,
        "progress_step": current_step + 1,
        "total_steps": len(STATUS_STEPS),
        "total_amount": float(order.total_amount),
        "delivery_address": order.delivery_address,
        "items": json.loads(order.items_json),
        "customer_name": customer.user_name if customer else "Customer",
        "customer_phone": customer.phone if customer else "",
        "created_at": order.created_at,
    }


# =====================
# OWNER ORDER MANAGEMENT
# =====================
@router.get("/order/{order_id}/guest-track")
def guest_track_order(
    order_id: int,
    phone: str = Query(..., min_length=10, description="Phone number used at checkout"),
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
):
    """Track an order without login, verified by the phone number used at checkout.

    Guest checkout never issues an auth token, so the authenticated
    /order/{id}/track endpoint is unreachable for guest customers. This
    endpoint lets a guest confirm their identity with the phone number
    they placed the order with instead.
    """
    order = db.query(OnlineOrder).filter(OnlineOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    customer = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.id == order.customer_id).first()
    if not customer or customer.phone != phone.strip():
        raise HTTPException(status_code=403, detail="Phone number does not match this order.")

    STATUS_STEPS = ["PENDING", "ACCEPTED", "DISPATCHED", "DELIVERED"]
    current_step = STATUS_STEPS.index(order.order_status) if order.order_status in STATUS_STEPS else 0

    return {
        "order_id": order.id,
        "status": order.order_status,
        "progress_step": current_step + 1,
        "total_steps": len(STATUS_STEPS),
        "total_amount": float(order.total_amount),
        "delivery_address": order.delivery_address,
        "items": json.loads(order.items_json),
        "created_at": order.created_at,
    }


@router.post("/order/{order_id}/rating")
def rate_completed_order(
    order_id: int,
    data: OrderRating,
    db: Session = Depends(get_db),
    current_user: dict = Depends(customer_only),
):
    customer_id = current_user["user_id"]
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == order_id,
        OnlineOrder.customer_id == customer_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.order_status != "DELIVERED":
        raise HTTPException(status_code=409, detail="You can rate an order only after delivery.")

    existing = db.query(ShopReview).filter(ShopReview.order_id == order.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="This order has already been rated.")

    review = ShopReview(
        order_id=order.id,
        shop_id=order.shop_id,
        customer_id=customer_id,
        rating=data.rating,
        comment=sanitize_input(data.comment or "", "comment") or None,
    )
    db.add(review)

    shop = db.query(ShopProfile).filter(ShopProfile.shop_id == order.shop_id).with_for_update().first()
    if not shop:
        raise HTTPException(status_code=404, detail="Shop profile not found.")
    current_count = int(getattr(shop, "rating_count", 0) or 0)
    current_score = float(getattr(shop, "rating_score", 0.0) or 0.0)
    shop.rating_score = round(((current_score * current_count) + data.rating) / (current_count + 1), 2)
    shop.rating_count = current_count + 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to save your rating right now.")

    return {
        "success": True,
        "shop_id": order.shop_id,
        "rating": shop.rating_score,
        "rating_count": shop.rating_count,
    }


@router.get("/owner/reviews")
def get_owner_reviews(
    skip: int = 0,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    shop_id = current_user["user_id"]
    rows = (
        db.query(ShopReview, OnlineCustomerAuth, OnlineOrder)
        .join(OnlineCustomerAuth, OnlineCustomerAuth.id == ShopReview.customer_id)
        .join(OnlineOrder, OnlineOrder.id == ShopReview.order_id)
        .filter(ShopReview.shop_id == shop_id)
        .order_by(ShopReview.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "reviews": [
            {
                "id": review.id,
                "order_id": review.order_id,
                "customer_id": review.customer_id,
                "customer_name": customer.user_name,
                "rating": review.rating,
                "comment": review.comment,
                "created_at": review.created_at,
                "items": json.loads(order.items_json or "[]"),
            }
            for review, customer, order in rows
        ],
        "total": len(rows),
    }


@router.get("/shops/{shop_id}/reviews")
def get_shop_reviews(
    shop_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ShopReview, OnlineCustomerAuth)
        .join(OnlineCustomerAuth, OnlineCustomerAuth.id == ShopReview.customer_id)
        .filter(ShopReview.shop_id == shop_id)
        .order_by(ShopReview.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "reviews": [
            {
                "id": review.id,
                "order_id": review.order_id,
                "customer_name": "Verified customer",
                "rating": review.rating,
                "comment": review.comment,
                "created_at": review.created_at,
            }
            for review, customer in rows
        ]
    }


@router.get("/owner/orders")
def get_incoming_orders(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Owner: View all incoming online orders for their shop"""
    shop_id = current_user["user_id"]
    q = db.query(OnlineOrder).filter(OnlineOrder.shop_id == shop_id)
    if status:
        q = q.filter(OnlineOrder.order_status == status.upper())
    orders = q.order_by(OnlineOrder.created_at.desc()).offset(skip).limit(limit).all()

    # Build response with customer info joined
    result = []
    for o in orders:
        customer = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.id == o.customer_id).first()
        result.append({
            "order_id": o.id,
            "customer_id": o.customer_id,
            "customer_name": customer.user_name if customer else "Guest",
            "customer_phone": customer.phone if customer else "",
            "status": o.order_status,
            "total_amount": float(o.total_amount),
            "delivery_address": o.delivery_address,
            "items": json.loads(o.items_json),
            "created_at": str(o.created_at),
        })

    return {
        "orders": result,
        "total": len(result),
    }



@router.post("/owner/orders/{order_id}/delivery-otp")
def request_order_delivery_otp(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Send a backend-generated OTP to the customer's registered email before delivery."""
    shop_id = current_user["user_id"]
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == order_id,
        OnlineOrder.shop_id == shop_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.order_status != "DISPATCHED":
        raise HTTPException(
            status_code=409,
            detail="Customer delivery OTP can only be requested for a dispatched order.",
        )

    customer = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.id == order.customer_id,
    ).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer account record for this order could not be found.",
        )

    customer_email = (customer.email or "").strip().lower()
    if not customer_email:
        raise HTTPException(
            status_code=409,
            detail="Customer does not have a registered email address. Add an email to the customer account before delivery.",
        )
    if not EmailNotificationService:
        raise HTTPException(
            status_code=503,
            detail="Email delivery is not configured on the server.",
        )

    now = datetime.utcnow()
    latest = db.query(OnlineOrderDeliveryOtp).filter(
        OnlineOrderDeliveryOtp.order_id == order.id,
        OnlineOrderDeliveryOtp.customer_id == customer.id,
        OnlineOrderDeliveryOtp.used == False,
    ).order_by(OnlineOrderDeliveryOtp.id.desc()).first()
    if latest and latest.created_at and now - latest.created_at < timedelta(seconds=60):
        remaining = 60 - int((now - latest.created_at).total_seconds())
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {max(1, remaining)} seconds before requesting another delivery OTP.",
        )

    # Invalidate every older challenge for this order before issuing a new one.
    db.query(OnlineOrderDeliveryOtp).filter(
        OnlineOrderDeliveryOtp.order_id == order.id,
        OnlineOrderDeliveryOtp.customer_id == customer.id,
        OnlineOrderDeliveryOtp.used == False,
    ).update({"used": True}, synchronize_session=False)

    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    challenge = OnlineOrderDeliveryOtp(
        order_id=order.id,
        customer_id=customer.id,
        otp_hash=hashlib.sha256(otp.encode("utf-8")).hexdigest(),
        otp_expires_at=now + timedelta(minutes=10),
        otp_attempts=0,
        used=False,
        created_at=now,
    )
    db.add(challenge)

    subject, body = EmailNotificationService.send_otp_template(
        otp,
        f"Order #{order.id} Delivery Verification",
    )

    try:
        sent = EmailNotificationService.send_email(
            recipient_email=customer_email,
            subject=subject,
            body=body,
        )
        if not sent:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail="Customer delivery OTP email could not be delivered. Please try again.",
            )

        db.commit()
        return {
            "success": True,
            "message": "Delivery OTP sent to the customer's registered email.",
            "email": _mask_delivery_email(customer_email),
            "expires_in": 600,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.exception(
            "Customer delivery OTP request failed for order_id=%s: %s",
            order.id,
            e,
        )
        raise HTTPException(
            status_code=503,
            detail="Customer delivery OTP email could not be delivered. Please try again.",
        )


def _mask_delivery_email(email: str) -> str:
    normalized = email.strip().lower()
    local, sep, domain = normalized.partition("@")
    if not sep or not local or not domain:
        return "***"
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


@router.post("/owner/orders/{order_id}/action")
def update_order_status(
    order_id: int,
    action: str = Query(..., description="ACCEPT, DISPATCH, DELIVER, REJECT"),
    data: Optional[OwnerOrderAction] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Owner: Accept, Dispatch, Deliver, or Reject an order"""
    shop_id = current_user["user_id"]
    order = db.query(OnlineOrder).with_for_update().filter(
        OnlineOrder.id == order_id,
        OnlineOrder.shop_id == shop_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    ACTION_MAP = {
        "ACCEPT": "ACCEPTED",
        "DISPATCH": "DISPATCHED",
        "DELIVER": "DELIVERED",
        "REJECT": "REJECTED",
    }
    new_status = ACTION_MAP.get(action.upper())
    if not new_status:
        raise HTTPException(status_code=400, detail=f"Invalid action. Choose from: {list(ACTION_MAP.keys())}")

    previous_status = order.order_status
    restored_inventory = []
    linked_invoice = None

    if order.order_status in ("DELIVERED", "REJECTED"):
        raise HTTPException(status_code=409, detail="Order is already finalized.")

    if new_status == "DELIVERED" and order.order_status != "DISPATCHED":
        raise HTTPException(
            status_code=409,
            detail="Order must be dispatched before it can be marked delivered.",
        )

    if order.order_status != "PENDING" and new_status == "ACCEPTED":
        raise HTTPException(status_code=409, detail="Order is already accepted or finalized.")

    # 🟢 On ACCEPT: record sales immediately in dashboard 🟢──────────────────
    if new_status == "ACCEPTED":
        items = json.loads(order.items_json)
        customer = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.id == order.customer_id).first()
        customer_name = customer.user_name if customer else "Online Customer"
        customer_phone = customer.phone if customer else ""

        # 1. Write one sales row per item → appears in Sales Dashboard
        for item in items:
            sale_entry = sales(
                shopkeeper_id=shop_id,
                product_name=item.get("product_name", "Online Item"),
                price=item.get("unit_price", 0),
                quantity=item.get("quantity", 1),
                total=item.get("line_total", 0),
                sale_date=date.today(),
                reference_order_id=order.id,
            )
            db.add(sale_entry)

        # 2. Create Invoice (ACCEPTED = COD/pending payment)
        invoice_num = f"ONL-{order.id}-{int(datetime.now().timestamp())}"
        invoice = Invoice(
            user_id=shop_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            invoice_number=invoice_num,
            invoice_date=date.today(),
            due_date=date.today(),
            subtotal=float(order.total_amount),
            tax=0,
            total_amount=float(order.total_amount),
            paid_amount=0,
            status="SENT",
            payment_status="UNPAID",
            source="ONLINE_ORDER",
            notes=f"Online Order #{order.id} | Delivery: {order.delivery_address}"
        )
        db.add(invoice)
        db.flush()

        # 3. Create InvoiceLineItems
        for item in items:
            db_line = InvoiceLineItem(
                invoice_id=invoice.id,
                product_id=item.get("product_id"),
                description=item.get("product_name", "Item"),
                quantity=item.get("quantity", 1),
                unit_price=item.get("unit_price", 0),
                line_total=item.get("line_total", 0),
            )
            db.add(db_line)

        # 4. Write to universal P&L journal
        tx = UniversalTransaction(
            shop_id=shop_id,
            tx_type="INCOME",
            category="SALE",
            amount=float(order.total_amount),
            reference_id=f"ONL-{order.id}",
            description=f"Online Order Accepted: #{order.id} | {customer_name}",
            tx_date=datetime.now(),
        )
        db.add(tx)

    # 🟢 On DELIVER: verify the OTP emailed to the customer, then mark invoice as PAID.
    if new_status == "DELIVERED":
        customer_otp = (data.customer_otp if data else None)
        if not customer_otp:
            raise HTTPException(
                status_code=400,
                detail="Customer delivery OTP is required before marking this order delivered.",
            )

        challenge = db.query(OnlineOrderDeliveryOtp).filter(
            OnlineOrderDeliveryOtp.order_id == order.id,
            OnlineOrderDeliveryOtp.customer_id == order.customer_id,
            OnlineOrderDeliveryOtp.used == False,
            OnlineOrderDeliveryOtp.otp_expires_at > datetime.utcnow(),
        ).order_by(OnlineOrderDeliveryOtp.id.desc()).with_for_update().first()

        if not challenge:
            raise HTTPException(
                status_code=400,
                detail="No valid customer delivery OTP was found. Send a new OTP and try again.",
            )

        if challenge.otp_attempts >= 5:
            challenge.used = True
            db.commit()
            raise HTTPException(
                status_code=429,
                detail="Too many incorrect OTP attempts. Send a new delivery OTP.",
            )

        expected_hash = hashlib.sha256(customer_otp.strip().encode("utf-8")).hexdigest()
        if challenge.otp_hash != expected_hash:
            challenge.otp_attempts += 1
            attempts_left = max(0, 5 - challenge.otp_attempts)
            if challenge.otp_attempts >= 5:
                challenge.used = True
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid customer delivery OTP."
                    if attempts_left == 0
                    else f"Invalid customer delivery OTP. {attempts_left} attempt(s) remaining."
                ),
            )

        # Consume the challenge in the same transaction as the delivery update.
        challenge.used = True
        challenge.verified_at = datetime.utcnow()

        # Mark the linked invoice as PAID.
        linked_invoice = db.query(Invoice).filter(
            Invoice.source == "ONLINE_ORDER",
            Invoice.notes.like(f"%Online Order #{order.id}%"),
            Invoice.user_id == shop_id,
        ).first()
        if linked_invoice:
            linked_invoice.payment_status = "PAID"
            linked_invoice.paid_amount = float(order.total_amount)
            linked_invoice.status = "PAID"
            
    # Delivery is the accounting settlement point for online orders.\n    # Reconcile the canonical sale/invoice records here as well as at ACCEPT so\n    # an order can never become DELIVERED without appearing in Sales/Dashboard.\n    if new_status == "DELIVERED":\n        items = json.loads(order.items_json)\n        customer = db.query(OnlineCustomerAuth).filter(\n            OnlineCustomerAuth.id == order.customer_id\n        ).first()\n        customer_name = customer.user_name if customer else "Online Customer"\n        customer_phone = customer.phone if customer else ""\n        delivery_date = date.today()\n\n        # 1) Ensure exactly one legacy sales row exists for every delivered\n        # online-order item. Existing ACCEPT-created rows are reused and their\n        # business date is moved to the actual delivery date.\n        for item in items:\n            product_name = item.get("product_name", "Online Item")\n            existing_sale = db.query(sales).filter(\n                sales.shopkeeper_id == shop_id,\n                sales.reference_order_id == order.id,\n                sales.product_name == product_name,\n            ).first()\n            if existing_sale:\n                existing_sale.sale_date = delivery_date\n                existing_sale.price = item.get("unit_price", 0)\n                existing_sale.quantity = item.get("quantity", 1)\n                existing_sale.total = item.get("line_total", 0)\n            else:\n                db.add(sales(\n                    shopkeeper_id=shop_id,\n                    product_name=product_name,\n                    price=item.get("unit_price", 0),\n                    quantity=item.get("quantity", 1),\n                    total=item.get("line_total", 0),\n                    sale_date=delivery_date,\n                    reference_order_id=order.id,\n                ))\n\n        # 2) Ensure the online order has a canonical invoice. This repairs\n        # orders accepted by older deployments where invoice creation failed\n        # or was skipped.\n        if linked_invoice is None:\n            linked_invoice = db.query(Invoice).filter(\n                Invoice.user_id == shop_id,\n                Invoice.source == "ONLINE_ORDER",\n                Invoice.notes.like(f"%Online Order #{order.id}%"),\n            ).first()\n\n        if linked_invoice is None:\n            invoice_num = f"ONL-{order.id}"\n            linked_invoice = db.query(Invoice).filter(\n                Invoice.user_id == shop_id,\n                Invoice.invoice_number == invoice_num,\n            ).first()\n            if linked_invoice is None:\n                linked_invoice = Invoice(\n                    user_id=shop_id,\n                    customer_name=customer_name,\n                    customer_phone=customer_phone,\n                    invoice_number=invoice_num,\n                    invoice_date=delivery_date,\n                    due_date=delivery_date,\n                    subtotal=float(order.total_amount),\n                    tax=0,\n                    total_amount=float(order.total_amount),\n                    paid_amount=0,\n                    status="SENT",\n                    payment_status="UNPAID",\n                    source="ONLINE_ORDER",\n                    notes=f"Online Order #{order.id} | Delivery: {order.delivery_address}",\n                )\n                db.add(linked_invoice)\n                db.flush()\n\n                for item in items:\n                    db.add(InvoiceLineItem(\n                        invoice_id=linked_invoice.id,\n                        product_id=item.get("product_id"),\n                        description=item.get("product_name", "Item"),\n                        quantity=item.get("quantity", 1),\n                        unit_price=item.get("unit_price", 0),\n                        line_total=item.get("line_total", 0),\n                    ))\n\n        # 3) Delivery is the moment the COD sale is completed. Keep the\n        # invoice date aligned with delivery and settle it as PAID.\n        linked_invoice.invoice_date = delivery_date\n        linked_invoice.payment_status = "PAID"\n        linked_invoice.paid_amount = float(order.total_amount)\n        linked_invoice.status = "PAID"\n\n        # 4) Ensure the dashboard/P&L journal has one SALE entry.\n        sale_reference = f"ONL-{order.id}"\n        existing_sale_tx = db.query(UniversalTransaction).filter(\n            UniversalTransaction.shop_id == shop_id,\n            UniversalTransaction.reference_id == sale_reference,\n            UniversalTransaction.category == "SALE",\n        ).first()\n        if existing_sale_tx is None:\n            db.add(UniversalTransaction(\n                shop_id=shop_id,\n                tx_type="INCOME",\n                category="SALE",\n                amount=float(order.total_amount),\n                reference_id=sale_reference,\n                description=f"Online Order Delivered: #{order.id} | {customer_name}",\n                tx_date=datetime.now(),\n            ))\n\n    # 🟢 On REJECT: restore reserved stock 🟢
    if new_status == "REJECTED":
        items = json.loads(order.items_json)
        for item in items:
            if item.get("product_id"):
                product = db.query(Product).with_for_update().filter(
                    Product.id == item["product_id"],
                    Product.user_id == shop_id,
                ).first()
                if product:
                    product.current_stock = (product.current_stock or 0) + item["quantity"]
                    restored_inventory.append({
                        "product_id": product.id,
                        "quantity": item["quantity"],
                        "new_stock": float(product.current_stock),
                    })

    order.order_status = new_status
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update order status: {str(e)}")

    loyalty_points_awarded = 0
    if new_status == "DELIVERED":
        try:
            from growth_suite import _award_delivery_points
            loyalty_points_awarded = int(_award_delivery_points(db, order) or 0)
            db.commit()
        except Exception as loyalty_error:
            db.rollback()
            logger.warning(
                "Online order loyalty award failed after delivery: %s",
                loyalty_error,
            )

    try:
        AuditService.log_action(
            db=db,
            user_id=shop_id,
            action=AuditAction.UPDATE,
            table_name="online_orders",
            record_id=order.id,
            old_values={"status": previous_status},
            new_values={"status": new_status},
            description=f"Online order #{order.id} changed from {previous_status} to {new_status}",
        )
        if linked_invoice is not None:
            AuditService.log_action(
                db=db,
                user_id=shop_id,
                action=AuditAction.UPDATE,
                table_name="invoices",
                record_id=linked_invoice.id,
                new_values={
                    "payment_status": "PAID",
                    "paid_amount": float(linked_invoice.paid_amount or 0),
                },
                description=f"Online order #{order.id} marked invoice paid on delivery",
            )
    except Exception as audit_error:
        logger.warning(
            "Online order audit logging failed after commit: %s",
            audit_error,
        )

    publish_realtime_event({
        "event_id": str(uuid4()),
        "type": "order.status_changed",
        "shop_id": shop_id,
        "order_id": order_id,
        "customer_id": order.customer_id,
        "previous_status": previous_status,
        "status": new_status,
        "total_amount": float(order.total_amount),
        "delivery_address": order.delivery_address,
        "items": json.loads(order.items_json),
        "created_at": order.created_at,
    })

    if linked_invoice is not None and new_status == "DELIVERED":
        publish_realtime_event({
            "event_id": str(uuid4()),
            "type": "payment.updated",
            "shop_id": shop_id,
            "invoice_id": linked_invoice.id,
            "invoice_number": linked_invoice.invoice_number,
            "amount": float(order.total_amount),
            "paid_amount": float(linked_invoice.paid_amount or 0),
            "payment_status": "PAID",
            "source": "ONLINE_ORDER_DELIVERY",
            "reference_id": f"ONL-{order.id}",
        })

    if linked_invoice is not None and new_status == "DELIVERED":
        # Notify realtime dashboard clients that the invoice itself changed.
        publish_realtime_event({
            "event_id": str(uuid4()),
            "type": "invoice.updated",
            "shop_id": shop_id,
            "invoice_id": linked_invoice.id,
            "invoice_number": linked_invoice.invoice_number,
            "status": "PAID",
            "payment_status": "PAID",
            "paid_amount": float(linked_invoice.paid_amount or 0),
            "total_amount": float(linked_invoice.total_amount or 0),
            "source": "ONLINE_ORDER_DELIVERY",
            "reference_id": f"ONL-{order.id}",
        })

    if restored_inventory:
        publish_realtime_event({
            "event_id": str(uuid4()),
            "type": "inventory.changed",
            "shop_id": shop_id,
            "reference_type": "ONLINE_ORDER_REJECT",
            "reference_id": str(order.id),
            "changes": restored_inventory,
        })

    return {
        "message": f"Order #{order_id} status updated to {new_status}.",
        "order_id": order_id,
        "new_status": new_status,
        "loyalty_points_awarded": loyalty_points_awarded,
    }