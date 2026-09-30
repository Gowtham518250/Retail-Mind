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
from typing import Optional, List
from datetime import datetime, timezone, timedelta, date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Header
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func

from db import get_db
from models import User, ShopProfile, Product, OnlineOrder, Invoice, InvoiceLineItem, UniversalTransaction, OnlineCustomerAuth, sales
from idempotency_manager import IdempotencyManager
from realtime_events import event_hub
from audit_logging import AuditService, AuditAction
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

router = APIRouter(prefix="/store", tags=["Online Store"])

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
    # Support forgot by email or phone
    email: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("email")
    def validate_email(cls, v):
        if v is None or v.strip() == "":
            return None
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("value is not a valid email address")
        return v.lower().strip()

class OrderItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, le=1000)

class PlaceOrder(BaseModel):
    shop_id: int
    items: List[OrderItem] = Field(..., min_length=1)
    delivery_address: str = Field(..., min_length=5)

class GuestOrder(BaseModel):
    shop_id: int
    customer_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    delivery_address: str = Field(..., min_length=5, max_length=500)
    items: List[OrderItem] = Field(..., min_length=1, max_length=50)
    firebase_id_token: Optional[str] = Field(None, description="Firebase Auth ID token for phone verification (optional)")


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

    # ── Uniqueness check by PHONE (primary) ──────────────────────────────
    existing_phone = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.phone == data.phone
    ).first()
    if existing_phone:
        raise HTTPException(status_code=409, detail="Phone number already registered. Please login instead.")

    # ── Uniqueness check by EMAIL only when email is provided ────────────
    if data.email:
        existing_email = db.query(OnlineCustomerAuth).filter(
            OnlineCustomerAuth.email == data.email
        ).first()
        if existing_email:
            raise HTTPException(status_code=409, detail="Email already registered.")

    name = sanitize_input(data.name, "name")
    customer = OnlineCustomerAuth(
        user_name=name,
        email=data.email,  # may be None if not provided
        phone=data.phone,
        city=data.city,
        address=data.address,
        password=hash_password(data.password),
        is_active=data.is_active if data.is_active is not None else True,
    )
    db.add(customer)
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
        user = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.email == data.email).first()

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
        "customer": {"id": user.id, "name": user.user_name, "phone": user.phone},
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


@router.post("/customer/forgot-password")
def forgot_password(
    data: CustomerForgot,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
):
    """Generate a new temporary password and email it to the customer.

    🔧 FIX: this previously queried the customer and then did nothing with
    the result — no email was ever sent, no password was ever changed. It
    just returned a generic success message regardless, which made the
    "forgot password" flow completely non-functional while looking like
    it worked from the client's perspective.

    Always returns the same generic message whether or not the account
    exists, to avoid leaking which emails are registered.
    """
    user = None
    if data.email:
        user = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.email == data.email).first()
    elif data.phone:
        user = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.phone == data.phone).first()

    if user and user.email:
        try:
            # Generate a secure, random temporary password (not a
            # predictable/short one) and store only its bcrypt hash.
            temp_password = secrets.token_urlsafe(9)  # ~12 char URL-safe string
            user.password = hash_password(temp_password)
            db.commit()

            if EmailNotificationService:
                subject, body = EmailNotificationService.welcome_credentials_template(
                    user.user_name, temp_password, "Customer (Password Reset)"
                )
                EmailNotificationService.create_notification(
                    db=db,
                    recipient_email=user.email,
                    subject=subject,
                    body=body,
                    event_type="PASSWORD_RESET",
                )
        except Exception as e:
            logger.error(f"Failed to process password reset for customer: {e}")
            db.rollback()

    return {"message": "If this account is registered with an email, a new password has been sent to it."}


# =====================
# SHOP DISCOVERY
# =====================
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
    query = db.query(ShopProfile).filter(ShopProfile.is_online_store_enabled == True)

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

    # Try online-enabled first, fallback to any shop profile
    profile = db.query(ShopProfile).filter(
        ShopProfile.shop_id == shop_id_int,
        ShopProfile.is_online_store_enabled == True,
    ).first()
    if not profile:
        # Fallback: show products even if online store flag not set
        profile = db.query(ShopProfile).filter(
            ShopProfile.shop_id == shop_id_int,
        ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Shop not found.")

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
        "shop_phone": profile.phone or "",
        "shop_address": profile.address or "",
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
async def place_order(
    data: PlaceOrder,
    db: Session = Depends(get_db),
    current_user: dict = Depends(customer_only),
    _rl: None = Depends(check_rate_limit),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Place an online order atomically with retry-safe idempotency and realtime updates."""
    customer_id = current_user["user_id"]
    scoped_key = (
        f"{customer_id}:{data.shop_id}:{idempotency_key.strip()}"
        if idempotency_key and idempotency_key.strip()
        else None
    )
    if scoped_key:
        cached = IdempotencyManager.get_cached_response(scoped_key, "online_order_create")
        if cached:
            return {**cached, "idempotent_replay": True}

    profile = db.query(ShopProfile).filter(
        ShopProfile.shop_id == data.shop_id,
        ShopProfile.is_online_store_enabled == True,
    ).first()
    if not profile:
        profile = db.query(ShopProfile).filter(ShopProfile.shop_id == data.shop_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Shop not found or not accepting online orders.")

    order_items: list[dict] = []
    inventory_events: list[dict] = []
    total_amount = 0.0

    for item in data.items:
        product = db.query(Product).with_for_update().filter(
            Product.id == item.product_id,
            Product.user_id == data.shop_id,
            Product.is_active == True,
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found in this shop.")
        if product.current_stock is not None and product.current_stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.product_name}'. Available: {product.current_stock}",
            )

        previous_stock = float(product.current_stock or 0)
        product.current_stock = previous_stock - item.quantity

        discount = get_active_discount(db, data.shop_id, product.category)
        price = float(product.unit_price)
        if discount > 0:
            price = round(price * (1.0 - discount / 100.0), 2)
        line_total = price * item.quantity
        total_amount += line_total

        order_items.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": item.quantity,
            "unit_price": price,
            "line_total": line_total,
            "discount_pct": discount,
        })
        inventory_events.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "previous_stock": previous_stock,
            "new_stock": float(product.current_stock),
            "quantity": item.quantity,
            "reason": "ONLINE_ORDER",
        })

    order = OnlineOrder(
        shop_id=data.shop_id,
        customer_id=customer_id,
        total_amount=total_amount,
        delivery_address=sanitize_input(data.delivery_address, "delivery_address"),
        items_json=json.dumps(order_items),
        order_status="PENDING",
    )
    db.add(order)

    try:
        db.commit()
        db.refresh(order)
    except Exception as e:
        db.rollback()
        logger.error("Failed to save online order (shop_id=%s, customer_id=%s): %s", data.shop_id, customer_id, e)
        raise HTTPException(status_code=500, detail="Unable to place order right now. Please try again later.")

    response = {
        "message": "Order placed successfully! The shop will confirm shortly.",
        "order_id": order.id,
        "shop_name": profile.shop_name,
        "total_amount": total_amount,
        "items": order_items,
        "status": "PENDING",
        "inventory_updated": True,
        "inventory_events": inventory_events,
        "created_at": order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat(),
    }
    if scoped_key:
        IdempotencyManager.set_cached_response(scoped_key, "online_order_create", response)

    try:
        AuditService.log_action(
            db=db,
            user_id=customer_id,
            action=AuditAction.CREATE,
            table_name="online_orders",
            record_id=order.id,
            new_values={"shop_id": data.shop_id, "total_amount": total_amount, "status": "PENDING"},
            description=f"Online order #{order.id} placed",
        )
    except Exception as audit_error:
        logger.warning("Online order audit logging failed: %s", audit_error)

    await event_hub.owner_event(data.shop_id, {
        "type": "online_order_created",
        "order_id": order.id,
        "customer_id": customer_id,
        "shop_id": data.shop_id,
        "status": "PENDING",
        "total_amount": total_amount,
        "items": order_items,
        "inventory": inventory_events,
        "created_at": response["created_at"],
    })
    await event_hub.customer_event(customer_id, {
        "type": "order_status_changed",
        "order_id": order.id,
        "shop_id": data.shop_id,
        "status": "PENDING",
        "total_amount": total_amount,
        "items": order_items,
        "created_at": response["created_at"],
    })
    return response


@router.post("/guest-order")
async def place_guest_order(
    data: GuestOrder,
    db: Session = Depends(get_db),
    _rl: None = Depends(check_rate_limit),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Place a guest order atomically with retry-safe idempotency and realtime owner updates."""
    logger.info(
        "Received guest order: shop_id=%s, customer=%s, phone=%s, items_count=%s",
        data.shop_id, data.customer_name, data.phone, len(data.items),
    )

    scoped_key = (
        f"guest:{data.phone}:{data.shop_id}:{idempotency_key.strip()}"
        if idempotency_key and idempotency_key.strip()
        else None
    )
    if scoped_key:
        cached = IdempotencyManager.get_cached_response(scoped_key, "guest_order_create")
        if cached:
            return {**cached, "idempotent_replay": True}

    if data.firebase_id_token:
        try:
            import firebase_admin
            if not firebase_admin._apps:
                raise HTTPException(status_code=503, detail="Firebase not configured. Please contact support.")
            from firebase_admin import auth
            decoded_token = auth.verify_id_token(data.firebase_id_token)
            phone_number = decoded_token.get("phone_number")
            if not phone_number:
                raise HTTPException(status_code=400, detail="Invalid token: No phone number associated with this login.")
            if data.phone not in phone_number:
                logger.warning(
                    "Verified phone number does not match provided phone number: %s vs %s",
                    data.phone, phone_number,
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Firebase token verification failed: %s", e)
            logger.warning("Falling back to unverified phone number for guest order.")
    else:
        logger.info("No Firebase token provided for guest checkout, proceeding with phone %s", data.phone)

    profile = db.query(ShopProfile).filter(
        ShopProfile.shop_id == data.shop_id,
        ShopProfile.is_online_store_enabled == True,
    ).first()
    if not profile:
        profile = db.query(ShopProfile).filter(ShopProfile.shop_id == data.shop_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Shop not found or not accepting online orders.")

    customer = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.phone == data.phone
    ).first()
    if not customer:
        import secrets
        customer = OnlineCustomerAuth(
            user_name=sanitize_input(data.customer_name, "name"),
            email=f"guest_{data.phone}@example.com",
            phone=data.phone,
            address=sanitize_input(data.delivery_address, "address"),
            password=hash_password(secrets.token_urlsafe(32)),
            is_active=False,
        )
        db.add(customer)
        db.flush()
    else:
        customer.user_name = sanitize_input(data.customer_name, "name")
        customer.address = sanitize_input(data.delivery_address, "address")

    order_items: list[dict] = []
    inventory_events: list[dict] = []
    total_amount = 0.0

    for item in data.items:
        product = db.query(Product).with_for_update().filter(
            Product.id == item.product_id,
            Product.user_id == data.shop_id,
            Product.is_active == True,
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found.")
        if product.current_stock is not None and product.current_stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.product_name}'. Available: {product.current_stock}",
            )
        previous_stock = float(product.current_stock or 0)
        product.current_stock = previous_stock - item.quantity
        discount = get_active_discount(db, data.shop_id, product.category)
        price = float(product.unit_price)
        if discount > 0:
            price = round(price * (1.0 - discount / 100.0), 2)
        line_total = price * item.quantity
        total_amount += line_total
        order_items.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": item.quantity,
            "unit_price": price,
            "line_total": line_total,
            "discount_pct": discount,
        })
        inventory_events.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "previous_stock": previous_stock,
            "new_stock": float(product.current_stock),
            "quantity": item.quantity,
            "reason": "GUEST_ONLINE_ORDER",
        })

    order = OnlineOrder(
        shop_id=data.shop_id,
        customer_id=customer.id,
        total_amount=total_amount,
        delivery_address=sanitize_input(data.delivery_address, "address"),
        items_json=json.dumps(order_items),
        order_status="PENDING",
    )
    db.add(order)
    try:
        db.commit()
        db.refresh(order)
    except Exception as e:
        db.rollback()
        logger.error("Failed to save guest order: %s", e)
        raise HTTPException(status_code=500, detail="Unable to place your order right now. Please try again later.")

    response = {
        "message": "Guest order placed successfully!",
        "order_id": order.id,
        "shop_name": profile.shop_name,
        "total_amount": total_amount,
        "status": "PENDING",
        "inventory_updated": True,
        "inventory_events": inventory_events,
        "created_at": order.created_at.isoformat() if order.created_at else datetime.utcnow().isoformat(),
    }
    if scoped_key:
        IdempotencyManager.set_cached_response(scoped_key, "guest_order_create", response)

    try:
        AuditService.log_action(
            db=db,
            action=AuditAction.CREATE,
            table_name="online_orders",
            record_id=order.id,
            new_values={"shop_id": data.shop_id, "customer_id": customer.id, "total_amount": total_amount, "status": "PENDING"},
            description=f"Guest online order #{order.id} placed",
        )
    except Exception as audit_error:
        logger.warning("Guest order audit logging failed: %s", audit_error)

    await event_hub.owner_event(data.shop_id, {
        "type": "online_order_created",
        "order_id": order.id,
        "customer_id": customer.id,
        "shop_id": data.shop_id,
        "status": "PENDING",
        "total_amount": total_amount,
        "items": order_items,
        "inventory": inventory_events,
        "created_at": response["created_at"],
        "guest": True,
    })

    # Push remains best-effort; realtime websocket is the immediate channel.
    try:
        from firebase_admin import messaging
        shop_owner = db.query(User).filter(User.id == data.shop_id).first()
        if shop_owner and shop_owner.fcm_token:
            messaging.send(
                messaging.Message(
                    notification=messaging.Notification(
                        title="New Online Order! 🎉",
                        body=f"You received a new order for ₹{total_amount:.2f} from {customer.user_name}.",
                    ),
                    data={"order_id": str(order.id), "type": "NEW_ORDER"},
                    token=shop_owner.fcm_token,
                )
            )
    except Exception as e:
        logger.info("Owner FCM notification skipped/failed: %s", e)

    return response


@router.get("/my-orders")
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(customer_only),
):
    """Customer: View all their orders from the backend source of truth."""
    customer_id = current_user["user_id"]
    orders = db.query(OnlineOrder).filter(
        OnlineOrder.customer_id == customer_id
    ).order_by(OnlineOrder.created_at.desc()).all()

    shop_cache: dict[int, str] = {}
    result = []
    for order in orders:
        if order.shop_id not in shop_cache:
            profile = db.query(ShopProfile).filter(ShopProfile.shop_id == order.shop_id).first()
            shop_cache[order.shop_id] = profile.shop_name if profile else f"Shop #{order.shop_id}"
        try:
            items = json.loads(order.items_json)
        except@router.get("/order/{order_id}/track")
def track_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dict),
):
    """Track an authenticated customer or owner order with a UI-ready timeline."""
    order = db.query(OnlineOrder).filter(OnlineOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    uid = current_user["user_id"]
    role = current_user.get("role", ROLE_OWNER)
    if role == ROLE_CUSTOMER and order.customer_id != uid:
        raise HTTPException(status_code=403, detail="You do not have access to this order.")
    if role == ROLE_OWNER and order.shop_id != uid:
        raise HTTPException(status_code=403, detail="You do not have access to this order.")

    status = str(order.order_status)
    steps = ["PENDING", "ACCEPTED", "DISPATCHED", "DELIVERED"]
    current_step = steps.index(status) if status in steps else 0
    timeline = [
        {"status": step, "completed": index <= current_step and status != "REJECTED"}
        for index, step in enumerate(steps)
    ]
    if status == "REJECTED":
        timeline = (
            [{"status": step, "completed": False} for step in steps]
            + [{"status": "REJECTED", "completed": True}]
        )

    try:
        items = json.loads(order.items_json)
    except Exception:
        items = []

    profile = db.query(ShopProfile).filter(ShopProfile.shop_id == order.shop_id).first()

    return {
        "order_id": order.id,
        "shop_id": order.shop_id,
        "shop_name": profile.shop_name if profile else f"Shop #{order.shop_id}",
        "status": status,
        "progress_step": current_step + 1,
        "total_steps": len(steps),
        "timeline": timeline,
        "total_amount": float(order.total_amount),
        "delivery_address": order.delivery_address,
        "items": items,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


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



@router.post("/owner/orders/{order_id}/action")
async def update_order_status(
    order_id: int,
    action: str = Query(..., description="ACCEPT, DISPATCH, DELIVER, REJECT"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Owner: change order status and publish realtime updates."""
    shop_id = current_user["user_id"]
    scoped_key = (
        f"{shop_id}:{order_id}:{action.upper()}:{idempotency_key.strip()}"
        if idempotency_key and idempotency_key.strip()
        else None
    )
    if scoped_key:
        cached = IdempotencyManager.get_cached_response(scoped_key, "online_order_status")
        if cached:
            return {**cached, "idempotent_replay": True}

    order = db.query(OnlineOrder).with_for_update().filter(
        OnlineOrder.id == order_id,
        OnlineOrder.shop_id == shop_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    old_status = str(order.order_status)
    action_upper = action.upper()
    action_map = {
        "ACCEPT": "ACCEPTED",
        "DISPATCH": "DISPATCHED",
        "DELIVER": "DELIVERED",
        "REJECT": "REJECTED",
    }
    new_status = action_map.get(action_upper)
    if not new_status:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Choose from: {list(action_map.keys())}",
        )

    if old_status in ("DELIVERED", "REJECTED"):
        raise HTTPException(status_code=409, detail="Order is already finalized.")
    if old_status != "PENDING" and new_status == "ACCEPTED":
        raise HTTPException(status_code=409, detail="Order is already accepted or finalized.")
    if old_status == "PENDING" and new_status == "DISPATCHED":
        raise HTTPException(status_code=409, detail="Accept the order before dispatching it.")

    try:
        items = json.loads(order.items_json)
    except Exception:
        items = []

    customer = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.id == order.customer_id
    ).first()
    customer_name = customer.user_name if customer else "Online Customer"
    customer_phone = customer.phone if customer else ""

    inventory_events: list[dict] = []

    # ACCEPT creates the canonical sale/invoice/journal exactly once because
    # this transition is only valid from PENDING.
    if new_status == "ACCEPTED":
        for item in items:
            sale_entry = sales(
                shopkeeper_id=shop_id,
                product_name=item.get("product_name", "Online Item"),
                price=item.get("unit_price", 0),
                quantity=item.get("quantity", 1),
                total=item.get("line_total", 0),
                sale_date=date.today(),
            )
            db.add(sale_entry)

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
            notes=f"Online Order #{order.id} | Delivery: {order.delivery_address}",
        )
        db.add(invoice)
        db.flush()

        for item in items:
            db.add(
                InvoiceLineItem(
                    invoice_id=invoice.id,
                    product_id=item.get("product_id"),
                    description=item.get("product_name", "Item"),
                    quantity=item.get("quantity", 1),
                    unit_price=item.get("unit_price", 0),
                    line_total=item.get("line_total", 0),
                )
            )

        db.add(
            UniversalTransaction(
                shop_id=shop_id,
                tx_type="INCOME",
                category="SALE",
                amount=float(order.total_amount),
                reference_id=f"ONL-{order.id}",
                description=f"Online Order Accepted: #{order.id} | {customer_name}",
                tx_date=datetime.now(),
            )
        )

    if new_status == "DELIVERED":
        linked_invoice = db.query(Invoice).filter(
            Invoice.source == "ONLINE_ORDER",
            Invoice.notes.like(f"%Online Order #{order.id}%"),
            Invoice.user_id == shop_id,
        ).first()
        if linked_invoice:
            linked_invoice.payment_status = "PAID"
            linked_invoice.paid_amount = float(order.total_amount)
            linked_invoice.status = "PAID"

    if new_status == "REJECTED":
        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity", 0)
            if not product_id or quantity <= 0:
                continue
            product = db.query(Product).with_for_update().filter(
                Product.id == product_id,
                Product.user_id == shop_id,
            ).first()
            if product:
                previous_stock = float(product.current_stock or 0)
                product.current_stock = previous_stock + quantity
                inventory_events.append({
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "previous_stock": previous_stock,
                    "new_stock": float(product.current_stock),
                    "quantity": quantity,
                    "reason": "ONLINE_ORDER_REJECT_RESTORE",
                })

    order.order_status = new_status
    try:
        db.commit()
        db.refresh(order)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update order status: {str(e)}",
        )

    response = {
        "message": f"Order #{order_id} status updated to {new_status}.",
        "order_id": order_id,
        "previous_status": old_status,
        "new_status": new_status,
        "status": new_status,
        "shop_id": shop_id,
        "customer_id": order.customer_id,
        "total_amount": float(order.total_amount),
        "items": items,
        "inventory_events": inventory_events,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
    if scoped_key:
        IdempotencyManager.set_cached_response(scoped_key, "online_order_status", response)

    try:
        AuditService.log_action(
            db=db,
            user_id=shop_id,
            action=AuditAction.UPDATE,
            table_name="online_orders",
            record_id=order.id,
            old_values={"status": old_status},
            new_values={"status": new_status},
            description=f"Order #{order.id}: {old_status} -> {new_status}",
        )
    except Exception as audit_error:
        logger.warning("Order audit logging failed: %s", audit_error)

    await event_hub.customer_event(order.customer_id, {
        "type": "order_status_changed",
        "order_id": order.id,
        "shop_id": shop_id,
        "status": new_status,
        "previous_status": old_status,
        "total_amount": float(order.total_amount),
        "items": items,
        "inventory_events": inventory_events,
        "created_at": response["created_at"],
    })
    await event_hub.owner_event(shop_id, {
        "type": "order_status_changed",
        "order_id": order.id,
        "shop_id": shop_id,
        "status": new_status,
        "previous_status": old_status,
        "total_amount": float(order.total_amount),
        "items": items,
        "inventory_events": inventory_events,
        "created_at": response["created_at"],
    })

    return response
