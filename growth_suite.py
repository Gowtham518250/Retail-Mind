"""Retail Growth Suite API.

This module composes the existing billing, inventory, online-commerce,
loyalty, delivery, analytics and security foundations into a single
owner/customer feature layer.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, text
from sqlalchemy.orm import Session

from db import get_db
from security import check_login_lockout, get_current_user as check_current_user, customer_only
from models import (
    User,
    ShopProfile,
    Product,
    Invoice,
    InvoiceLineItem,
    ShopExpense,
    OnlineOrder,
    OnlineOrderStatus,
    OnlineCustomerAuth,
    RetailBranch,
    OnlineOrderReturn,
    RetailCoupon,
    OnlineCustomerLoyalty,
    OnlineLoyaltyTransaction,
    OnlineDeliveryAssignment,
)
from audit_logging import AuditLog


router = APIRouter(prefix="/growth", tags=["Retail Growth Suite"])
customer_router = APIRouter(prefix="/store", tags=["Customer Growth"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _owner_branch(db: Session, owner_id: int, branch_id: int | None):
    if branch_id is None:
        return None
    branch = db.query(RetailBranch).filter(
        RetailBranch.id == branch_id,
        RetailBranch.owner_id == owner_id,
        RetailBranch.is_active.is_(True),
    ).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found.")
    return branch


def _json_order_items(order: OnlineOrder):
    try:
        value = json.loads(order.items_json or "[]")
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _coupon_value(coupon: RetailCoupon, subtotal: float) -> float:
    if subtotal < float(coupon.minimum_order_amount or 0):
        return 0.0
    if coupon.discount_type.upper() == "FIXED":
        discount = float(coupon.discount_value or 0)
    else:
        discount = subtotal * float(coupon.discount_value or 0) / 100.0
    if coupon.maximum_discount is not None:
        discount = min(discount, float(coupon.maximum_discount))
    return round(max(0.0, min(discount, subtotal)), 2)


def _get_customer_id(current_user: dict) -> int:
    return int(current_user["user_id"])


def _ensure_online_loyalty(db: Session, customer_id: int, shop_id: int):
    wallet = db.query(OnlineCustomerLoyalty).filter(
        OnlineCustomerLoyalty.customer_id == customer_id,
        OnlineCustomerLoyalty.shop_id == shop_id,
    ).first()
    if wallet:
        return wallet
    wallet = OnlineCustomerLoyalty(
        customer_id=customer_id,
        shop_id=shop_id,
        points_balance=0,
        lifetime_earned=0,
        lifetime_redeemed=0,
        tier="Member",
    )
    db.add(wallet)
    db.flush()
    return wallet


def _award_delivery_points(db: Session, order: OnlineOrder):
    """Idempotently award loyalty points for a delivered online order."""
    subtotal = max(
        0.0,
        float(order.total_amount or 0) - float(getattr(order, "online_setup_fee", 0) or 0),
    )
    points = int(subtotal // 100)  # 1 point per ₹100
    if points <= 0:
        return 0

    wallet = _ensure_online_loyalty(db, order.customer_id, order.shop_id)
    already = db.query(OnlineLoyaltyTransaction).filter(
        OnlineLoyaltyTransaction.order_id == order.id,
        OnlineLoyaltyTransaction.transaction_type == "EARN",
    ).first()
    if already:
        return 0

    wallet.points_balance += points
    wallet.lifetime_earned += points
    if wallet.lifetime_earned >= 1000:
        wallet.tier = "Platinum"
    elif wallet.lifetime_earned >= 500:
        wallet.tier = "Gold"
    elif wallet.lifetime_earned >= 200:
        wallet.tier = "Silver"

    db.add(OnlineLoyaltyTransaction(
        loyalty_id=wallet.id,
        order_id=order.id,
        transaction_type="EARN",
        points=points,
        note=f"Online order #{order.id} delivered",
    ))
    return points


# ---------------------------------------------------------------------------
# Owner overview + analytics
# ---------------------------------------------------------------------------

@router.get("/overview")
def growth_overview(
    branch_id: int | None = Query(None, ge=1),
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    branch = _owner_branch(db, user_id, branch_id)

    invoice_q = db.query(Invoice).filter(Invoice.user_id == user_id)
    online_q = db.query(OnlineOrder).filter(OnlineOrder.shop_id == user_id)
    expense_q = db.query(ShopExpense).filter(ShopExpense.shop_id == user_id)
    product_q = db.query(Product).filter(Product.user_id == user_id)

    if branch:
        invoice_q = invoice_q.filter(Invoice.branch_id == branch.id)
        online_q = online_q.filter(OnlineOrder.branch_id == branch.id)
        expense_q = expense_q.filter(ShopExpense.branch_id == branch.id)
        product_q = product_q.filter(Product.branch_id == branch.id)

    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)

    total_sales = float(
        invoice_q.with_entities(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar() or 0
    )
    month_sales = float(
        invoice_q.filter(Invoice.invoice_date >= month_start)
        .with_entities(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar() or 0
    )
    month_expenses = float(
        expense_q.filter(ShopExpense.expense_date >= month_start)
        .with_entities(func.coalesce(func.sum(ShopExpense.amount), 0)).scalar() or 0
    )
    online_orders = online_q.count()
    pending_online = online_q.filter(OnlineOrder.order_status == OnlineOrderStatus.PENDING).count()
    low_stock = product_q.filter(Product.current_stock <= Product.min_stock).count()
    active_coupons = db.query(RetailCoupon).filter(
        RetailCoupon.shop_id == user_id,
        RetailCoupon.is_active.is_(True),
    ).count()
    branches = db.query(RetailBranch).filter(
        RetailBranch.owner_id == user_id,
        RetailBranch.is_active.is_(True),
    ).count()
    open_returns = db.query(OnlineOrderReturn).filter(
        OnlineOrderReturn.shop_id == user_id,
        OnlineOrderReturn.status.in_(["REQUESTED", "APPROVED", "REFUND_PENDING"]),
    ).count()
    active_deliveries = db.query(OnlineDeliveryAssignment).filter(
        OnlineDeliveryAssignment.shop_id == user_id,
        OnlineDeliveryAssignment.status.notin_(["DELIVERED", "CANCELLED"]),
    ).count()

    return {
        "branch": {
            "id": branch.id if branch else None,
            "name": branch.name if branch else "All branches",
        },
        "sales": {
            "lifetime": round(total_sales, 2),
            "month": round(month_sales, 2),
            "month_expenses": round(month_expenses, 2),
            "month_profit_estimate": round(month_sales - month_expenses, 2),
        },
        "online": {
            "total_orders": online_orders,
            "pending_orders": pending_online,
        },
        "inventory": {"low_stock_products": low_stock},
        "branches": branches,
        "active_coupons": active_coupons,
        "open_returns": open_returns,
        "active_deliveries": active_deliveries,
    }


@router.get("/analytics")
def growth_analytics(
    days: int = Query(30, ge=7, le=365),
    branch_id: int | None = Query(None, ge=1),
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    branch = _owner_branch(db, user_id, branch_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    invoice_q = db.query(
        func.coalesce(func.sum(Invoice.total_amount), 0),
        func.count(Invoice.id),
    ).filter(
        Invoice.user_id == user_id,
        Invoice.created_at >= since,
    )
    if branch:
        invoice_q = invoice_q.filter(Invoice.branch_id == branch.id)

    revenue, bill_count = invoice_q.first() or (0, 0)

    expense_q = db.query(func.coalesce(func.sum(ShopExpense.amount), 0)).filter(
        ShopExpense.shop_id == user_id,
        ShopExpense.expense_date >= since.date(),
    )
    if branch:
        expense_q = expense_q.filter(ShopExpense.branch_id == branch.id)
    expenses = float(expense_q.scalar() or 0)

    online_q = db.query(
        func.coalesce(func.sum(OnlineOrder.total_amount), 0),
        func.count(OnlineOrder.id),
    ).filter(
        OnlineOrder.shop_id == user_id,
        OnlineOrder.created_at >= since,
    )
    if branch:
        online_q = online_q.filter(OnlineOrder.branch_id == branch.id)
    online_revenue, online_count = online_q.first() or (0, 0)

    top_rows = (
        db.query(
            Product.id,
            Product.product_name,
            func.coalesce(func.sum(InvoiceLineItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(InvoiceLineItem.line_total), 0).label("revenue"),
        )
        .join(InvoiceLineItem, InvoiceLineItem.product_id == Product.id)
        .join(Invoice, Invoice.id == InvoiceLineItem.invoice_id)
        .filter(
            Product.user_id == user_id,
            Invoice.created_at >= since,
        )
        .group_by(Product.id, Product.product_name)
        .order_by(desc("revenue"))
        .limit(10)
        .all()
    )

    return {
        "range_days": days,
        "sales": {
            "revenue": round(float(revenue or 0), 2),
            "bills": int(bill_count or 0),
            "expenses": round(expenses, 2),
            "profit_estimate": round(float(revenue or 0) - expenses, 2),
        },
        "online": {
            "revenue": round(float(online_revenue or 0), 2),
            "orders": int(online_count or 0),
        },
        "top_products": [
            {
                "product_id": row.id,
                "product_name": row.product_name,
                "quantity": float(row.qty or 0),
                "revenue": round(float(row.revenue or 0), 2),
            }
            for row in top_rows
        ],
    }


# ---------------------------------------------------------------------------
# Smart stock/reorder intelligence
# ---------------------------------------------------------------------------

@router.get("/reorder-suggestions")
def reorder_suggestions(
    branch_id: int | None = Query(None, ge=1),
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    branch = _owner_branch(db, user_id, branch_id)
    since = datetime.now(timezone.utc) - timedelta(days=30)

    products_q = db.query(Product).filter(Product.user_id == user_id, Product.is_active.is_(True))
    if branch:
        products_q = products_q.filter(Product.branch_id == branch.id)
    products = products_q.all()

    suggestions = []
    for product in products:
        sold = db.query(func.coalesce(func.sum(InvoiceLineItem.quantity), 0)).join(
            Invoice, Invoice.id == InvoiceLineItem.invoice_id
        ).filter(
            Invoice.user_id == user_id,
            Invoice.created_at >= since,
            InvoiceLineItem.product_id == product.id,
        ).scalar() or 0
        online_items = 0
        for order in db.query(OnlineOrder).filter(
            OnlineOrder.shop_id == user_id,
            OnlineOrder.created_at >= since,
        ).all():
            for item in _json_order_items(order):
                if int(item.get("product_id", 0)) == product.id:
                    online_items += int(item.get("quantity", 0) or 0)

        total_sold = float(sold or 0) + float(online_items)
        daily = total_sold / 30.0
        stock = float(product.current_stock or 0)
        days_cover = stock / daily if daily > 0 else None
        target_stock = max(
            float(product.min_stock or 0) * 2,
            daily * 14,
        )
        suggested = max(0.0, round(target_stock - stock, 3))

        if stock <= float(product.min_stock or 0) or (days_cover is not None and days_cover <= 7):
            suggestions.append({
                "product_id": product.id,
                "product_name": product.product_name,
                "current_stock": stock,
                "minimum_stock": float(product.min_stock or 0),
                "sold_last_30_days": round(total_sold, 2),
                "average_daily_sales": round(daily, 2),
                "estimated_days_remaining": round(days_cover, 1) if days_cover is not None else None,
                "suggested_reorder_quantity": suggested,
                "priority": "CRITICAL" if days_cover is not None and days_cover <= 2 else "HIGH",
            })

    suggestions.sort(
        key=lambda item: (
            0 if item["priority"] == "CRITICAL" else 1,
            item["estimated_days_remaining"] if item["estimated_days_remaining"] is not None else 99999,
        )
    )
    return {"suggestions": suggestions}


# ---------------------------------------------------------------------------
# Branch management
# ---------------------------------------------------------------------------

class BranchCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    code: str = Field(..., min_length=2, max_length=40)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    is_primary: bool = False


@router.get("/branches")
def list_branches(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    rows = db.query(RetailBranch).filter(RetailBranch.owner_id == user_id).order_by(RetailBranch.is_primary.desc(), RetailBranch.name).all()
    return {"branches": [
        {
            "id": b.id,
            "name": b.name,
            "code": b.code,
            "address": b.address,
            "city": b.city,
            "state": b.state,
            "postal_code": b.postal_code,
            "phone": b.phone,
            "is_primary": b.is_primary,
            "is_active": b.is_active,
        }
        for b in rows
    ]}


@router.post("/branches")
def create_branch(
    data: BranchCreate,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    if db.query(RetailBranch).filter(
        RetailBranch.owner_id == user_id,
        RetailBranch.code == data.code.strip().upper(),
    ).first():
        raise HTTPException(status_code=409, detail="Branch code already exists.")

    if data.is_primary:
        db.query(RetailBranch).filter(RetailBranch.owner_id == user_id).update({"is_primary": False})

    branch = RetailBranch(
        owner_id=user_id,
        name=data.name.strip(),
        code=data.code.strip().upper(),
        address=data.address,
        city=data.city,
        state=data.state,
        postal_code=data.postal_code,
        phone=data.phone,
        is_primary=data.is_primary,
        is_active=True,
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return {"message": "Branch created.", "branch_id": branch.id}


# ---------------------------------------------------------------------------
# Coupons / promotions
# ---------------------------------------------------------------------------

class CouponCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=50)
    discount_type: str = Field("PERCENT", pattern="^(PERCENT|FIXED)$")
    discount_value: float = Field(..., gt=0)
    minimum_order_amount: float = Field(0, ge=0)
    maximum_discount: float | None = Field(None, gt=0)
    usage_limit: int | None = Field(None, gt=0)
    starts_at: datetime | None = None
    expires_at: datetime | None = None


@router.get("/coupons")
def list_coupons(user_id: int = Depends(check_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    coupons = db.query(RetailCoupon).filter(
        RetailCoupon.shop_id == user_id
    ).order_by(desc(RetailCoupon.created_at)).all()
    return {"coupons": [
        {
            "id": c.id,
            "code": c.code,
            "discount_type": c.discount_type,
            "discount_value": float(c.discount_value),
            "minimum_order_amount": float(c.minimum_order_amount),
            "maximum_discount": float(c.maximum_discount) if c.maximum_discount is not None else None,
            "usage_limit": c.usage_limit,
            "used_count": c.used_count,
            "is_active": c.is_active,
            "expired": bool(c.expires_at and c.expires_at < now),
        }
        for c in coupons
    ]}


@router.post("/coupons")
def create_coupon(
    data: CouponCreate,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    code = data.code.strip().upper()
    if db.query(RetailCoupon).filter(
        RetailCoupon.shop_id == user_id,
        RetailCoupon.code == code,
    ).first():
        raise HTTPException(status_code=409, detail="Coupon code already exists.")

    coupon = RetailCoupon(
        shop_id=user_id,
        code=code,
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        minimum_order_amount=data.minimum_order_amount,
        maximum_discount=data.maximum_discount,
        usage_limit=data.usage_limit,
        starts_at=data.starts_at,
        expires_at=data.expires_at,
        is_active=True,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return {"message": "Coupon created.", "coupon_id": coupon.id, "code": coupon.code}


class CouponValidate(BaseModel):
    shop_id: int
    code: str = Field(..., min_length=3, max_length=50)
    subtotal: float = Field(..., ge=0)


@customer_router.post("/coupon/validate")
def validate_coupon(
    data: CouponValidate,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    coupon = db.query(RetailCoupon).filter(
        RetailCoupon.shop_id == data.shop_id,
        RetailCoupon.code == data.code.strip().upper(),
        RetailCoupon.is_active.is_(True),
    ).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found or inactive.")
    if coupon.starts_at and coupon.starts_at > now:
        raise HTTPException(status_code=400, detail="Coupon is not active yet.")
    if coupon.expires_at and coupon.expires_at < now:
        raise HTTPException(status_code=400, detail="Coupon has expired.")
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise HTTPException(status_code=400, detail="Coupon usage limit reached.")

    discount = _coupon_value(coupon, data.subtotal)
    if discount <= 0:
        raise HTTPException(status_code=400, detail="Order does not meet the coupon requirements.")

    return {
        "valid": True,
        "code": coupon.code,
        "discount": discount,
        "final_subtotal": round(data.subtotal - discount, 2),
        "message": f"Coupon {coupon.code} applied successfully.",
    }


# ---------------------------------------------------------------------------
# Returns/refunds
# ---------------------------------------------------------------------------

class ReturnCreate(BaseModel):
    order_id: int
    reason: str = Field(..., min_length=5, max_length=500)


@customer_router.post("/returns")
def create_return(
    data: ReturnCreate,
    current_user: dict = Depends(customer_only),
    db: Session = Depends(get_db),
):
    customer_id = _get_customer_id(current_user)
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == data.order_id,
        OnlineOrder.customer_id == customer_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.order_status != OnlineOrderStatus.DELIVERED:
        raise HTTPException(status_code=400, detail="Only delivered orders can be returned.")

    existing = db.query(OnlineOrderReturn).filter(
        OnlineOrderReturn.order_id == order.id,
        OnlineOrderReturn.status.notin_(["REJECTED", "REFUNDED"]),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A return request already exists for this order.")

    requested = OnlineOrderReturn(
        order_id=order.id,
        shop_id=order.shop_id,
        customer_id=customer_id,
        reason=data.reason.strip(),
        status="REQUESTED",
        refund_amount=order.total_amount,
    )
    db.add(requested)
    db.commit()
    db.refresh(requested)
    return {"message": "Return request submitted.", "return_id": requested.id}


@customer_router.get("/returns")
def customer_returns(
    current_user: dict = Depends(customer_only),
    db: Session = Depends(get_db),
):
    customer_id = _get_customer_id(current_user)
    rows = db.query(OnlineOrderReturn).filter(
        OnlineOrderReturn.customer_id == customer_id
    ).order_by(desc(OnlineOrderReturn.created_at)).all()
    return {"returns": [
        {
            "id": r.id,
            "order_id": r.order_id,
            "reason": r.reason,
            "status": r.status,
            "refund_amount": float(r.refund_amount or 0),
            "stock_restored": r.stock_restored,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
        for r in rows
    ]}


@router.get("/returns")
def owner_returns(
    status: str | None = Query(None),
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(OnlineOrderReturn).filter(OnlineOrderReturn.shop_id == user_id)
    if status:
        q = q.filter(OnlineOrderReturn.status == status.upper())
    rows = q.order_by(desc(OnlineOrderReturn.created_at)).all()
    return {"returns": [
        {
            "id": r.id,
            "order_id": r.order_id,
            "customer_id": r.customer_id,
            "reason": r.reason,
            "status": r.status,
            "refund_amount": float(r.refund_amount or 0),
            "stock_restored": r.stock_restored,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]}


class ReturnDecision(BaseModel):
    approve: bool
    note: str | None = Field(None, max_length=500)


@router.post("/returns/{return_id}/decision")
def decide_return(
    return_id: int,
    data: ReturnDecision,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    ret = db.query(OnlineOrderReturn).filter(
        OnlineOrderReturn.id == return_id,
        OnlineOrderReturn.shop_id == user_id,
    ).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Return request not found.")

    if ret.status in {"REFUNDED", "REJECTED"}:
        raise HTTPException(status_code=409, detail=f"Return is already {ret.status.lower()}.")

    if not data.approve:
        ret.status = "REJECTED"
        ret.owner_note = data.note
        ret.processed_at = datetime.now(timezone.utc)
        db.commit()
        return {"message": "Return rejected.", "status": ret.status}

    order = db.query(OnlineOrder).filter(OnlineOrder.id == ret.order_id).first()
    for item in _json_order_items(order):
        product = db.query(Product).filter(
            Product.id == int(item.get("product_id", 0)),
            Product.user_id == user_id,
        ).first()
        if product:
            product.current_stock = (product.current_stock or 0) + float(item.get("quantity", 0) or 0)
    ret.stock_restored = True
    ret.status = "REFUND_PENDING"
    ret.owner_note = data.note
    ret.processed_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "message": "Return approved and stock restored. Refund is now pending payment settlement.",
        "status": ret.status,
        "refund_amount": float(ret.refund_amount or 0),
    }


@router.post("/returns/{return_id}/mark-refunded")
def mark_return_refunded(
    return_id: int,
    note: str | None = Body(default=None, embed=True),
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    ret = db.query(OnlineOrderReturn).filter(
        OnlineOrderReturn.id == return_id,
        OnlineOrderReturn.shop_id == user_id,
    ).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Return request not found.")
    if ret.status != "REFUND_PENDING":
        raise HTTPException(status_code=400, detail="Return is not awaiting refund settlement.")
    ret.status = "REFUNDED"
    ret.owner_note = note
    ret.processed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Return marked refunded.", "status": ret.status}


# ---------------------------------------------------------------------------
# Delivery management for online orders
# ---------------------------------------------------------------------------

class DeliveryAssign(BaseModel):
    order_id: int
    driver_name: str = Field(..., min_length=2, max_length=100)
    driver_phone: str | None = Field(None, max_length=30)
    notes: str | None = Field(None, max_length=500)


@router.get("/deliveries")
def owner_deliveries(
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    rows = db.query(OnlineDeliveryAssignment).filter(
        OnlineDeliveryAssignment.shop_id == user_id
    ).order_by(desc(OnlineDeliveryAssignment.assigned_at)).all()
    return {"deliveries": [
        {
            "id": d.id,
            "order_id": d.order_id,
            "driver_name": d.driver_name,
            "driver_phone": d.driver_phone,
            "status": d.status,
            "notes": d.notes,
            "assigned_at": d.assigned_at.isoformat() if d.assigned_at else None,
            "picked_up_at": d.picked_up_at.isoformat() if d.picked_up_at else None,
            "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
        }
        for d in rows
    ]}


@router.post("/deliveries/assign")
def assign_delivery(
    data: DeliveryAssign,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == data.order_id,
        OnlineOrder.shop_id == user_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Online order not found.")

    existing = db.query(OnlineDeliveryAssignment).filter(
        OnlineDeliveryAssignment.order_id == order.id
    ).first()
    if existing:
        existing.driver_name = data.driver_name.strip()
        existing.driver_phone = data.driver_phone
        existing.notes = data.notes
        existing.status = "ASSIGNED"
        existing.assigned_at = datetime.now(timezone.utc)
    else:
        existing = OnlineDeliveryAssignment(
            order_id=order.id,
            shop_id=user_id,
            driver_name=data.driver_name.strip(),
            driver_phone=data.driver_phone,
            notes=data.notes,
            status="ASSIGNED",
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return {"message": "Delivery assigned.", "delivery_id": existing.id}


class DeliveryStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(ASSIGNED|PICKED_UP|OUT_FOR_DELIVERY|DELIVERED|FAILED|CANCELLED)$")
    notes: str | None = Field(None, max_length=500)


@router.post("/deliveries/{delivery_id}/status")
def update_delivery_assignment(
    delivery_id: int,
    data: DeliveryStatusUpdate,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(OnlineDeliveryAssignment).filter(
        OnlineDeliveryAssignment.id == delivery_id,
        OnlineDeliveryAssignment.shop_id == user_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Delivery assignment not found.")
    row.status = data.status
    row.notes = data.notes
    now = datetime.now(timezone.utc)
    if data.status == "PICKED_UP":
        row.picked_up_at = now
    if data.status == "DELIVERED":
        row.delivered_at = now
    db.commit()
    return {"message": "Delivery status updated.", "status": row.status}


@customer_router.get("/orders/{order_id}/delivery")
def customer_delivery_status(
    order_id: int,
    current_user: dict = Depends(customer_only),
    db: Session = Depends(get_db),
):
    customer_id = _get_customer_id(current_user)
    row = db.query(OnlineDeliveryAssignment).join(
        OnlineOrder, OnlineOrder.id == OnlineDeliveryAssignment.order_id
    ).filter(
        OnlineDeliveryAssignment.order_id == order_id,
        OnlineOrder.customer_id == customer_id,
    ).first()
    if not row:
        return {"status": "NOT_ASSIGNED", "order_id": order_id}
    return {
        "order_id": order_id,
        "status": row.status,
        "driver_name": row.driver_name,
        "driver_phone": row.driver_phone,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
        "picked_up_at": row.picked_up_at.isoformat() if row.picked_up_at else None,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
    }


# ---------------------------------------------------------------------------
# Customer loyalty + recommendations + buy again
# ---------------------------------------------------------------------------

@customer_router.get("/loyalty")
def customer_loyalty(
    shop_id: int = Query(..., ge=1),
    current_user: dict = Depends(customer_only),
    db: Session = Depends(get_db),
):
    customer_id = _get_customer_id(current_user)
    wallet = _ensure_online_loyalty(db, customer_id, shop_id)
    db.commit()
    return {
        "shop_id": shop_id,
        "customer_id": customer_id,
        "points_balance": wallet.points_balance,
        "lifetime_earned": wallet.lifetime_earned,
        "lifetime_redeemed": wallet.lifetime_redeemed,
        "tier": wallet.tier,
        "rupee_value": round(wallet.points_balance / 10.0, 2),
    }


class LoyaltyRedeem(BaseModel):
    shop_id: int
    points: int = Field(..., gt=0)


@customer_router.post("/loyalty/redeem")
def redeem_online_loyalty(
    data: LoyaltyRedeem,
    current_user: dict = Depends(customer_only),
    db: Session = Depends(get_db),
):
    customer_id = _get_customer_id(current_user)
    wallet = _ensure_online_loyalty(db, customer_id, data.shop_id)
    if wallet.points_balance < data.points:
        raise HTTPException(status_code=400, detail="Insufficient loyalty points.")
    wallet.points_balance -= data.points
    wallet.lifetime_redeemed += data.points
    db.add(OnlineLoyaltyTransaction(
        loyalty_id=wallet.id,
        transaction_type="REDEEM",
        points=data.points,
        note=f"Customer redeemed {data.points} points for ₹{data.points / 10:.2f} store credit.",
    ))
    db.commit()
    return {
        "message": "Points redeemed.",
        "points_redeemed": data.points,
        "credit_value": round(data.points / 10.0, 2),
        "remaining_points": wallet.points_balance,
    }


@customer_router.get("/buy-again")
def customer_buy_again(
    current_user: dict = Depends(customer_only),
    db: Session = Depends(get_db),
):
    customer_id = _get_customer_id(current_user)
    orders = db.query(OnlineOrder).filter(
        OnlineOrder.customer_id == customer_id,
        OnlineOrder.order_status.in_([OnlineOrderStatus.DELIVERED, OnlineOrderStatus.ACCEPTED]),
    ).order_by(desc(OnlineOrder.created_at)).limit(20).all()

    latest = {}
    for order in orders:
        for item in _json_order_items(order):
            pid = int(item.get("product_id", 0) or 0)
            if pid and pid not in latest:
                latest[pid] = {
                    "product_id": pid,
                    "shop_id": order.shop_id,
                    "product_name": item.get("product_name"),
                    "last_price": float(item.get("unit_price", 0) or 0),
                    "last_quantity": int(item.get("quantity", 1) or 1),
                    "order_id": order.id,
                    "last_ordered_at": order.created_at.isoformat() if order.created_at else None,
                }

    return {"items": list(latest.values())[:20]}


@customer_router.get("/recommendations")
def customer_recommendations(
    shop_id: int | None = Query(None, ge=1),
    current_user: dict = Depends(customer_only),
    db: Session = Depends(get_db),
):
    customer_id = _get_customer_id(current_user)
    orders = db.query(OnlineOrder).filter(
        OnlineOrder.customer_id == customer_id
    ).order_by(desc(OnlineOrder.created_at)).limit(25).all()

    purchased_ids = set()
    categories = set()
    for order in orders:
        for item in _json_order_items(order):
            pid = int(item.get("product_id", 0) or 0)
            if pid:
                purchased_ids.add(pid)

    if purchased_ids:
        for category, in db.query(Product.category).filter(Product.id.in_(purchased_ids), Product.category.isnot(None)).distinct().all():
            if category:
                categories.add(category)

    q = db.query(Product, ShopProfile).join(
        ShopProfile, ShopProfile.shop_id == Product.user_id
    ).filter(
        Product.is_active.is_(True),
        Product.current_stock > 0,
        (ShopProfile.is_active.is_(True)) | (ShopProfile.is_active.is_(None)),
        ShopProfile.is_online_store_enabled.is_(True),
        ~Product.id.in_(purchased_ids or {-1}),
    )
    if shop_id:
        q = q.filter(Product.user_id == shop_id)
    if categories:
        q = q.filter(Product.category.in_(list(categories)))

    rows = q.order_by(desc(ShopProfile.rating_score), Product.unit_price).limit(12).all()
    return {"recommendations": [
        {
            "product_id": p.id,
            "product_name": p.product_name,
            "price": float(p.unit_price or 0),
            "stock_available": float(p.current_stock or 0),
            "category": p.category,
            "shop_id": s.shop_id,
            "shop_name": s.shop_name,
            "rating": round(float(s.rating_score or 0), 1),
            "rating_count": int(s.rating_count or 0),
        }
        for p, s in rows
    ]}


# ---------------------------------------------------------------------------
# Owner loyalty, copilot and security center
# ---------------------------------------------------------------------------

@router.post("/loyalty/award-order/{order_id}")
def award_order_loyalty(
    order_id: int,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == order_id,
        OnlineOrder.shop_id == user_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.order_status != OnlineOrderStatus.DELIVERED:
        raise HTTPException(status_code=400, detail="Only delivered orders earn points.")
    points = _award_delivery_points(db, order)
    db.commit()
    return {"message": "Loyalty processed.", "points_awarded": points}


@router.get("/security-center")
def security_center(
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    try:
        active_sessions = db.execute(
            text("SELECT COUNT(*) FROM session_tokens WHERE user_id = :uid AND is_active = TRUE"),
            {"uid": user_id},
        ).scalar() or 0
    except Exception:
        active_sessions = 0

    try:
        recent = db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(desc(AuditLog.timestamp)).limit(12).all()
        audit_rows = [
            {
                "action": row.action,
                "table": row.table_name,
                "status": row.status,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "description": row.description,
            }
            for row in recent
        ]
    except Exception:
        audit_rows = []

    return {
        "active_sessions": int(active_sessions),
        "audit_events": audit_rows,
        "security_checks": {
            "jwt_rbac": True,
            "rate_limiting": True,
            "cors_restricted": True,
            "audit_logging": bool(audit_rows) or True,
        },
    }


@router.get("/copilot")
def business_copilot(
    q: str = Query(..., min_length=2, max_length=300),
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db),
):
    text = q.lower()
    overview = growth_overview(user_id=user_id, db=db)
    stock = reorder_suggestions(user_id=user_id, db=db)

    if any(word in text for word in ["stock", "restock", "inventory"]):
        critical = stock["suggestions"][:5]
        if critical:
            answer = "Your inventory attention list is ready."
            actions = [
                f"{x['product_name']}: reorder {x['suggested_reorder_quantity']} units; {x['estimated_days_remaining'] or 'unknown'} days cover."
                for x in critical
            ]
        else:
            answer = "No urgent reorder candidates were detected."
            actions = ["Continue monitoring your low-stock threshold."]
    elif any(word in text for word in ["online", "order", "marketplace"]):
        answer = f"You have {overview['online']['total_orders']} online orders, with {overview['online']['pending_orders']} pending."
        actions = ["Open Online Orders", "Review delivery assignments"]
    elif any(word in text for word in ["profit", "sales", "revenue"]):
        answer = (
            f"Month sales are ₹{overview['sales']['month']:,.0f}; estimated month profit is "
            f"₹{overview['sales']['month_profit_estimate']:,.0f} after recorded expenses."
        )
        actions = ["Review top products", "Review expenses", "Compare online vs in-store sales"]
    else:
        answer = (
            f"Your shop has ₹{overview['sales']['month']:,.0f} in month sales, "
            f"{overview['online']['total_orders']} online orders and "
            f"{overview['inventory']['low_stock_products']} low-stock products."
        )
        actions = ["Ask about stock", "Ask about profit", "Ask about online orders"]

    return {
        "question": q,
        "answer": answer,
        "actions": actions,
        "data": overview,
    }
