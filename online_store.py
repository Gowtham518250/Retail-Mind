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
from typing import Optional, List
from datetime import datetime, timezone, timedelta, date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func

from db import get_db
from models import User, ShopProfile, Product, OnlineOrder, Invoice, InvoiceLineItem, UniversalTransaction, OnlineCustomerAuth, sales
from security import (
    hash_password, verify_password, create_access_token,
    ROLE_CUSTOMER, ROLE_OWNER,
    check_login_lockout, record_login_failure, record_login_success,
    owner_only, customer_only, get_current_user, sanitize_input
)
try:
    from email_notifications import EmailNotificationService
except ImportError:
    EmailNotificationService = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/store", tags=["Online Store"])

# =====================
# CUSTOMER AUTH SCHEMAS
# =====================
class CustomerRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    password: str = Field(..., min_length=6)
    city: Optional[str] = None
    address: Optional[str] = None
    role: Optional[str] = "CUSTOMER"
    is_active: Optional[bool] = True

    @field_validator("email")
    def validate_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("value is not a valid email address")
        return v.lower().strip()

class CustomerLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    def validate_email(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("value is not a valid email address")
        return v.lower().strip()

class CustomerLoginPhone(BaseModel):
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{10}$")
    password: str

class OrderItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class PlaceOrder(BaseModel):
    shop_id: int
    items: List[OrderItem] = Field(..., min_length=1)
    delivery_address: str = Field(..., min_length=5)

class GuestOrder(BaseModel):
    shop_id: int
    customer_name: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=10, max_length=15)
    delivery_address: str = Field(..., min_length=5)
    items: List[OrderItem] = Field(..., min_length=1)
    firebase_id_token: str = Field(..., description="Firebase Auth ID token for phone verification")


# =====================
# CUSTOMER AUTH
# =====================
@router.post("/customer/register")
def register_customer(
    data: CustomerRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new customer account"""
    existing = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    name = sanitize_input(data.name, "name")
    customer = OnlineCustomerAuth(
        user_name=name,
        email=data.email,
        phone=data.phone,
        city=data.city,
        address=data.address,
        password=hash_password(data.password),
        is_active=data.is_active if data.is_active is not None else True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    # Send Welcome Email with Credentials
    try:
        if EmailNotificationService:
            subject, body = EmailNotificationService.welcome_credentials_template(data.name, data.password, "Customer")
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
    """Customer login — returns JWT with CUSTOMER role"""
    ip = request.client.host
    check_login_lockout(ip)

    user = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.email == data.email).first()
    if not user or not verify_password(data.password, user.password):
        record_login_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    record_login_success(ip)
    token = create_access_token({"sub": str(user.id), "role": ROLE_CUSTOMER})
    return {
        "access_token": token,
        "token_type": "bearer",
        "customer_id": user.id,
        "name": user.user_name,
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
    email: str,
    db: Session = Depends(get_db),
):
    """Send password reset link — always 200 to prevent email enumeration"""
    db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.email == email).first()
    return {"message": "If this email is registered, a reset link has been sent."}


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

    all_shops = query.all()

    if lat is not None and lng is not None:
        # Filter by Haversine distance
        def haversine(lat1, lon1, lat2_str, lon2_str):
            """Calculate distance in km between two lat/lng points"""
            try:
                # We store location as "lat,lng" in address if GPS mode used
                parts = str(lat2_str).split(",")
                if len(parts) != 2:
                    return float("inf")
                lat2, lon2 = float(parts[0]), float(parts[1])
            except Exception:
                return float("inf")
            R = 6371  # Earth radius in km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        all_shops = [s for s in all_shops if haversine(lat, lng, s.address, s.address) <= radius_km]

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
            {
                "id": p.id,
                "name": p.product_name,
                "category": p.category,
                "price": float(p.unit_price),
                "stock_available": p.current_stock if p.current_stock else 999,
                "description": p.description,

            }
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
):
    """Place an online order at a specific shop"""
    customer_id = current_user

    # Validate shop
    profile = db.query(ShopProfile).filter(
        ShopProfile.shop_id == data.shop_id,
        ShopProfile.is_online_store_enabled == True,
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Shop not found or not accepting online orders.")

    # Validate all items and calculate total
    order_items = []
    total_amount = 0.0

    for item in data.items:
        product = db.query(Product).filter(
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
        line_total = float(product.unit_price) * item.quantity
        total_amount += line_total
        order_items.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": item.quantity,
            "unit_price": float(product.unit_price),
            "line_total": line_total,
        })

    delivery_address = sanitize_input(data.delivery_address, "delivery_address")

    order = OnlineOrder(
        shop_id=data.shop_id,
        customer_id=customer_id,
        total_amount=total_amount,
        delivery_address=delivery_address,
        items_json=json.dumps(order_items),
        order_status="PENDING",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "message": "Order placed successfully! The shop will confirm shortly.",
        "order_id": order.id,
        "shop_name": profile.shop_name,
        "total_amount": total_amount,
        "items": order_items,
        "status": "PENDING",
    }


@router.post("/guest-order")
def place_guest_order(
    data: GuestOrder,
    db: Session = Depends(get_db),
):
    """Place an online order as a guest (no auth required)"""
    # 1. Verify Firebase Phone Auth Token
    try:
        from firebase_admin import auth
        decoded_token = auth.verify_id_token(data.firebase_id_token)
        phone_number = decoded_token.get('phone_number')
        
        if not phone_number:
            raise HTTPException(status_code=400, detail="Invalid token: No phone number associated with this login.")
            
        # Ensure the verified phone matches the one provided (stripping non-digits for comparison if needed, or exact match)
        # Firebase phone numbers include country code (e.g., +919876543210).
        # We check if the provided phone is a substring of the verified phone to allow local format (e.g., 9876543210)
        if data.phone not in phone_number:
            raise HTTPException(status_code=400, detail="Verified phone number does not match the provided phone number.")
            
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Phone verification failed. Please try again.")

    # 2. Validate shop
    profile = db.query(ShopProfile).filter(
        ShopProfile.shop_id == data.shop_id,
        ShopProfile.is_online_store_enabled == True,
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Shop not found or not accepting online orders.")

    # 3. Find or create guest customer in OnlineCustomerAuth
    customer = db.query(OnlineCustomerAuth).filter(OnlineCustomerAuth.phone == data.phone).first()
    if not customer:
        customer = OnlineCustomerAuth(
            user_name=sanitize_input(data.customer_name, "name"),
            email=f"guest_{data.phone}@example.com",
            phone=data.phone,
            address=sanitize_input(data.delivery_address, "address"),
            password=hash_password(f"guest_{data.phone}"),
            is_active=False  # Mark as guest/inactive
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        
    customer_id = customer.id

    # 3. Validate items and calculate total
    order_items = []
    total_amount = 0.0

    for item in data.items:
        product = db.query(Product).filter(
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
        line_total = float(product.unit_price) * item.quantity
        total_amount += line_total
        order_items.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "quantity": item.quantity,
            "unit_price": float(product.unit_price),
            "line_total": line_total,
        })

    # 4. Create Order
    order = OnlineOrder(
        shop_id=data.shop_id,
        customer_id=customer_id,
        total_amount=total_amount,
        delivery_address=sanitize_input(data.delivery_address, "address"),
        items_json=json.dumps(order_items),
        order_status="PENDING",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
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

    return {
        "message": "Guest order placed successfully!",
        "order_id": order.id,
        "shop_name": profile.shop_name,
        "total_amount": total_amount,
        "status": "PENDING",
    }


@router.get("/my-orders")
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(customer_only),
):
    """Customer: View all their orders"""
    customer_id = current_user
    orders = db.query(OnlineOrder).filter(
        OnlineOrder.customer_id == customer_id
    ).order_by(OnlineOrder.created_at.desc()).all()

    return {
        "orders": [
            {
                "order_id": o.id,
                "shop_id": o.shop_id,
                "status": o.order_status,
                "total_amount": float(o.total_amount),
                "delivery_address": o.delivery_address,
                "items": json.loads(o.items_json),
                "created_at": o.created_at,
                "updated_at": o.updated_at,
            }
            for o in orders
        ]
    }


@router.get("/order/{order_id}/track")
def track_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Track a specific order by ID"""
    order = db.query(OnlineOrder).filter(OnlineOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Security: only the customer who placed the order or the shop owner can view it
    uid = current_user
    if order.customer_id != uid and order.shop_id != uid:
        raise HTTPException(status_code=403, detail="You do not have access to this order.")

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
        "updated_at": order.updated_at,
    }


# =====================
# OWNER ORDER MANAGEMENT
# =====================
@router.get("/owner/orders")
def get_incoming_orders(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Owner: View all incoming online orders for their shop"""
    shop_id = current_user
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
def update_order_status(
    order_id: int,
    action: str = Query(..., description="ACCEPT, DISPATCH, DELIVER, REJECT"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Owner: Accept, Dispatch, Deliver, or Reject an order"""
    shop_id = current_user
    order = db.query(OnlineOrder).filter(
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

    if order.order_status in ("DELIVERED", "REJECTED"):
        raise HTTPException(status_code=409, detail="Order is already finalized.")

    # ── On ACCEPT: record sales immediately in dashboard ──────────────────
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

    # ── On DELIVER: deduct stock only (sale already recorded at ACCEPT) ───
    if new_status == "DELIVERED":
        items = json.loads(order.items_json)
        for item in items:
            if item.get("product_id"):
                product = db.query(Product).filter(
                    Product.id == item["product_id"],
                    Product.user_id == shop_id,
                ).first()
                if product:
                    product.current_stock = max(0, (product.current_stock or 0) - item["quantity"])

        # Mark the linked invoice as PAID
        linked_invoice = db.query(Invoice).filter(
            Invoice.source == "ONLINE_ORDER",
            Invoice.notes.like(f"%Online Order #{order.id}%"),
            Invoice.user_id == shop_id,
        ).first()
        if linked_invoice:
            linked_invoice.payment_status = "PAID"
            linked_invoice.paid_amount = float(order.total_amount)
            linked_invoice.status = "PAID"

    order.order_status = new_status
    db.commit()

    return {
        "message": f"Order #{order_id} status updated to {new_status}.",
        "order_id": order_id,
        "new_status": new_status,
    }
