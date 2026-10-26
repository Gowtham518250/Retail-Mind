"""
Purchase orders API.

Purchase receipts update inventory only for quantities actually received.
Order creation and receipt retries are idempotent, and stock movements commit
atomically with the purchase-order lifecycle state.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List
from datetime import date, datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import get_db
from models import PurchaseOrder, PurchaseOrderStatus, Product, StockMovement, StockMovementType, Invoice, InvoiceLineItem
from sales_recognition import recognized_invoice_filters
from security import owner_only, sanitize_input, resolve_shop_id
from durable_sync import append_sync_event

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


class POItem(BaseModel):
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Optional[Decimal] = Field(None, ge=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_name: str = Field(..., min_length=2, max_length=100)
    expected_delivery: Optional[date] = None
    items: List[POItem] = Field(..., min_length=1)
    notes: Optional[str] = None
    status: str = Field(default="ORDERED", max_length=32)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=128)


class PurchaseOrderResponse(BaseModel):
    id: int
    supplier_name: str
    status: str
    total_cost: float
    expected_delivery: Optional[date]
    items_json: str
    idempotency_key: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class POReceiptItem(BaseModel):
    item_index: int = Field(..., ge=0)
    quantity: Decimal = Field(..., gt=0)


class POReceiptRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=128)
    items: List[POReceiptItem] = Field(..., min_length=1)


def _status_value(status) -> str:
    return str(getattr(status, "value", status) or "").strip().upper()


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalized_po_items(items: List[POItem], db: Session, shop_id: int) -> list[dict]:
    normalized: list[dict] = []
    for item in items:
        product = None
        if item.product_id is not None:
            product = db.query(Product).filter(
                Product.id == item.product_id,
                Product.user_id == shop_id,
                Product.is_active.is_(True),
            ).first()
            if product is None:
                raise HTTPException(status_code=422, detail=f"Product {item.product_id} does not belong to this shop or is inactive.")
        name = str(item.product_name or (product.product_name if product else "")).strip()
        if not name:
            raise HTTPException(status_code=422, detail="Every purchase-order item needs a product name or a shop-owned product_id.")
        unit_cost = item.unit_cost if item.unit_cost is not None else (item.unit_price or Decimal("0"))
        normalized.append({
            "product_id": product.id if product else None,
            "product_name": sanitize_input(name, "product_name"),
            "quantity": float(item.quantity),
            "unit_cost": float(unit_cost),
            "received_quantity": 0.0,
        })
    return normalized


def _po_content_matches(existing: PurchaseOrder, supplier_name: str, expected_delivery, items: list[dict]) -> bool:
    try:
        if (existing.supplier_name or "").strip().casefold() != supplier_name.strip().casefold():
            return False
        if existing.expected_delivery != expected_delivery:
            return False
        existing_items = json.loads(existing.items_json or "[]")
        def signature(rows):
            return sorted((
                int(row.get("product_id") or 0),
                " ".join(str(row.get("product_name") or "").split()).casefold(),
                Decimal(str(row.get("quantity") or 0)).quantize(Decimal("0.001")),
                _money(row.get("unit_cost", row.get("unit_price", 0))),
            ) for row in rows)
        return signature(existing_items) == signature(items)
    except (TypeError, ValueError, ArithmeticError, json.JSONDecodeError):
        return False


def _po_response(po: PurchaseOrder, *, duplicate: bool = False) -> dict:
    return {
        "id": po.id,
        "supplier_name": po.supplier_name,
        "status": _status_value(po.status),
        "total_cost": float(po.total_cost or 0),
        "expected_delivery": po.expected_delivery.isoformat() if po.expected_delivery else None,
        "items_json": po.items_json,
        "idempotency_key": po.idempotency_key,
        "created_at": po.created_at.isoformat() if po.created_at else datetime.now(timezone.utc).isoformat(),
        "duplicate": duplicate,
    }


@router.post("/", response_model=PurchaseOrderResponse)
def create_purchase_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    shop_id = resolve_shop_id(current_user)
    supplier_name = sanitize_input(data.supplier_name, "supplier_name").strip()
    idempotency_key = (data.idempotency_key or "").strip() or None
    requested_status = (data.status or "ORDERED").strip().upper()
    if requested_status in {"PENDING", "SENT"}:
        requested_status = "ORDERED"
    if requested_status not in {"DRAFT", "ORDERED"}:
        raise HTTPException(status_code=422, detail="New purchase orders must start as DRAFT or ORDERED.")

    items_data = _normalized_po_items(data.items, db, shop_id)
    total_cost = _money(sum(
        Decimal(str(item["quantity"])) * Decimal(str(item["unit_cost"]))
        for item in items_data
    ))

    if idempotency_key:
        existing = db.query(PurchaseOrder).filter(
            PurchaseOrder.shop_id == shop_id,
            PurchaseOrder.idempotency_key == idempotency_key,
        ).first()
        if existing:
            if _po_content_matches(existing, supplier_name, data.expected_delivery, items_data):
                return _po_response(existing, duplicate=True)
            raise HTTPException(status_code=409, detail="Purchase-order idempotency key was reused with different content.")

    po = PurchaseOrder(
        shop_id=shop_id,
        supplier_name=supplier_name,
        status=PurchaseOrderStatus.DRAFT if requested_status == "DRAFT" else PurchaseOrderStatus.ORDERED,
        total_cost=total_cost,
        items_json=json.dumps(items_data, separators=(",", ":")),
        expected_delivery=data.expected_delivery,
        idempotency_key=idempotency_key,
    )
    db.add(po)
    try:
        db.commit()
        db.refresh(po)
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(PurchaseOrder).filter(
                PurchaseOrder.shop_id == shop_id,
                PurchaseOrder.idempotency_key == idempotency_key,
            ).first()
            if existing and _po_content_matches(existing, supplier_name, data.expected_delivery, items_data):
                return _po_response(existing, duplicate=True)
        raise HTTPException(status_code=409, detail="Purchase-order idempotency conflict.")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create purchase order.") from exc
    return _po_response(po)


@router.get("/", response_model=List[PurchaseOrderResponse])
def list_purchase_orders(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    shop_id = resolve_shop_id(current_user)
    query = db.query(PurchaseOrder).filter(PurchaseOrder.shop_id == shop_id)
    if status:
        wanted = status.strip().upper()
        aliases = {"PENDING": "ORDERED", "SENT": "ORDERED", "DELIVERED": "RECEIVED"}
        wanted = aliases.get(wanted, wanted)
        if wanted == "ORDERED":
            query = query.filter(PurchaseOrder.status.in_([
                PurchaseOrderStatus.ORDERED, PurchaseOrderStatus.SENT, PurchaseOrderStatus.PENDING,
            ]))
        elif wanted == "RECEIVED":
            query = query.filter(PurchaseOrder.status.in_([
                PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.DELIVERED,
            ]))
        else:
            query = query.filter(PurchaseOrder.status == wanted)
    return query.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit).all()


@router.post("/{po_id}/mark-ordered")
def mark_po_ordered(po_id: int, db: Session = Depends(get_db), current_user: dict = Depends(owner_only)):
    shop_id = resolve_shop_id(current_user)
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.shop_id == shop_id
    ).with_for_update().first()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    status = _status_value(po.status)
    if status in {"ORDERED", "SENT", "PENDING", "PARTIALLY_RECEIVED"}:
        return {"success": True, "status": status, "duplicate": True, "purchase_order_id": po.id}
    if status != "DRAFT":
        raise HTTPException(status_code=409, detail=f"Cannot mark a {status.lower()} purchase order as ordered.")
    po.status = PurchaseOrderStatus.ORDERED
    try:
        append_sync_event(db, {"shop_id": shop_id, "type": "purchase_order.changed", "payload": {"purchase_order_id": po.id, "status": "ORDERED"}})
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update purchase-order status.") from exc
    return {"success": True, "status": "ORDERED", "purchase_order_id": po.id}


def _receive_po_items(db: Session, shop_id: int, po_id: int, idempotency_key: str, requested_items: list[dict]) -> dict:
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.shop_id == shop_id
    ).with_for_update().first()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")

    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:28]
    reference_prefix = f"PO-{po.id}-R-{digest}"
    duplicate_movement = db.query(StockMovement.id).filter(
        StockMovement.reference_id.like(reference_prefix + "-%")
    ).first()
    if duplicate_movement:
        return {
            "success": True, "duplicate": True, "purchase_order_id": po.id,
            "status": _status_value(po.status), "items_json": po.items_json,
            "stock_updates": [], "message": "This receipt was already applied; no additional stock was added.",
        }

    status = _status_value(po.status)
    if status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Cannot receive a cancelled purchase order.")
    if status == "DRAFT":
        raise HTTPException(status_code=409, detail="Mark the purchase order as ordered before receiving stock.")
    if status in {"RECEIVED", "DELIVERED"}:
        raise HTTPException(status_code=409, detail="All ordered quantities have already been received.")

    try:
        items_data = json.loads(po.items_json or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=409, detail="Purchase-order item data is invalid; manual review is required.") from exc
    if not isinstance(items_data, list) or not items_data:
        raise HTTPException(status_code=409, detail="Purchase order has no item lines to receive.")

    indexes = [int(entry["item_index"]) for entry in requested_items]
    if len(indexes) != len(set(indexes)):
        raise HTTPException(status_code=422, detail="A receipt cannot contain the same purchase-order line more than once.")

    stock_updates = []
    try:
        for entry in requested_items:
            item_index = int(entry["item_index"])
            if item_index < 0 or item_index >= len(items_data):
                raise HTTPException(status_code=422, detail=f"Invalid purchase-order item index: {item_index}.")
            item = items_data[item_index]
            ordered_qty = Decimal(str(item.get("quantity") or 0))
            received_qty = Decimal(str(item.get("received_quantity") or 0))
            receipt_qty = Decimal(str(entry["quantity"]))
            if ordered_qty <= 0 or received_qty < 0:
                raise HTTPException(status_code=409, detail="Purchase order contains an invalid quantity.")
            remaining_qty = ordered_qty - received_qty
            if receipt_qty <= 0 or receipt_qty > remaining_qty:
                raise HTTPException(status_code=422, detail=f"Received quantity for line {item_index + 1} must be greater than 0 and no more than {remaining_qty}.")

            product_id = item.get("product_id")
            product = None
            if product_id is not None:
                product = db.query(Product).filter(
                    Product.id == int(product_id), Product.user_id == shop_id,
                    Product.is_active.is_(True),
                ).with_for_update().first()
            else:
                product_name = str(item.get("product_name") or "").strip()
                candidates = db.query(Product).filter(
                    Product.user_id == shop_id,
                    Product.product_name.ilike(product_name),
                    Product.is_active.is_(True),
                ).limit(2).all() if product_name else []
                if len(candidates) == 1:
                    product = candidates[0]
                    item["product_id"] = product.id
                elif len(candidates) > 1:
                    raise HTTPException(status_code=409, detail=f"More than one inventory product matches '{product_name}'. Select the exact product before receiving.")
            if product is None:
                raise HTTPException(status_code=422, detail=f"Link purchase-order line {item_index + 1} to an active inventory product before receiving stock.")

            old_stock = Decimal(str(product.current_stock or 0))
            product.current_stock = old_stock + receipt_qty
            item["received_quantity"] = float(received_qty + receipt_qty)
            movement_ref = f"{reference_prefix}-{item_index}"
            db.add(StockMovement(
                product_id=product.id,
                movement_type=StockMovementType.IN,
                quantity=receipt_qty,
                reason="Purchase Order Receipt",
                reference_id=movement_ref,
            ))
            stock_updates.append({
                "item_index": item_index,
                "product_id": product.id,
                "product_name": product.product_name,
                "quantity_added": float(receipt_qty),
                "new_stock": float(product.current_stock),
                "remaining_quantity": float(ordered_qty - received_qty - receipt_qty),
            })

        all_received = all(
            Decimal(str(item.get("received_quantity") or 0)) >= Decimal(str(item.get("quantity") or 0))
            for item in items_data
        )
        any_received = any(Decimal(str(item.get("received_quantity") or 0)) > 0 for item in items_data)
        if all_received:
            po.status = PurchaseOrderStatus.RECEIVED
        elif any_received:
            po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
        else:
            po.status = PurchaseOrderStatus.ORDERED
        po.items_json = json.dumps(items_data, separators=(",", ":"))

        for update in stock_updates:
            append_sync_event(db, {
                "shop_id": shop_id,
                "type": "inventory.changed",
                "payload": {"product_id": update["product_id"], "current_stock": update["new_stock"], "reason": "PURCHASE_ORDER_RECEIPT", "purchase_order_id": po.id},
            })
        append_sync_event(db, {
            "shop_id": shop_id,
            "type": "purchase_order.changed",
            "payload": {"purchase_order_id": po.id, "status": _status_value(po.status)},
        })
        # Receipt of goods is not proof of payment; a real supplier payment must be recorded separately.
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to record purchase receipt; stock changes were rolled back.") from exc

    return {
        "success": True, "duplicate": False, "purchase_order_id": po.id,
        "status": _status_value(po.status), "items_json": po.items_json,
        "stock_updates": stock_updates,
        "message": "Received quantities were recorded atomically with inventory stock movements.",
    }


@router.post("/{po_id}/receive")
def receive_purchase_order_items(
    po_id: int,
    data: POReceiptRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    return _receive_po_items(
        db, resolve_shop_id(current_user), po_id, data.idempotency_key.strip(),
        [item.model_dump() for item in data.items],
    )


@router.post("/{po_id}/mark-delivered")
def mark_po_delivered(po_id: int, db: Session = Depends(get_db), current_user: dict = Depends(owner_only)):
    """Backward-compatible full receipt alias. Safe to retry after a timeout."""
    shop_id = resolve_shop_id(current_user)
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.shop_id == shop_id
    ).with_for_update().first()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    status = _status_value(po.status)
    if status in {"RECEIVED", "DELIVERED"}:
        return {"success": True, "duplicate": True, "purchase_order_id": po.id, "status": "RECEIVED", "stock_updates": []}
    if status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Cannot receive a cancelled purchase order.")
    if status == "DRAFT":
        raise HTTPException(status_code=409, detail="Mark the purchase order as ordered before receiving stock.")
    items_data = json.loads(po.items_json or "[]")
    remaining = []
    for index, item in enumerate(items_data):
        ordered_qty = Decimal(str(item.get("quantity") or 0))
        received_qty = Decimal(str(item.get("received_quantity") or 0))
        if ordered_qty > received_qty:
            remaining.append({"item_index": index, "quantity": str(ordered_qty - received_qty)})
    if not remaining:
        po.status = PurchaseOrderStatus.RECEIVED
        db.commit()
        return {"success": True, "duplicate": True, "purchase_order_id": po.id, "status": "RECEIVED", "stock_updates": []}
    return _receive_po_items(db, shop_id, po_id, f"legacy-full-receipt-{po_id}", remaining)


@router.post("/{po_id}/cancel")
def cancel_purchase_order(po_id: int, db: Session = Depends(get_db), current_user: dict = Depends(owner_only)):
    """Cancel the unreceived balance. Stock already received remains on hand."""
    shop_id = resolve_shop_id(current_user)
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id, PurchaseOrder.shop_id == shop_id
    ).with_for_update().first()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    status = _status_value(po.status)
    if status in {"RECEIVED", "DELIVERED"}:
        raise HTTPException(status_code=409, detail="Cannot cancel a fully received purchase order.")
    if status == "CANCELLED":
        return {"success": True, "duplicate": True, "purchase_order_id": po.id, "status": "CANCELLED"}
    po.status = PurchaseOrderStatus.CANCELLED
    try:
        append_sync_event(db, {"shop_id": shop_id, "type": "purchase_order.changed", "payload": {"purchase_order_id": po.id, "status": "CANCELLED"}})
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to cancel purchase order.") from exc
    return {"success": True, "purchase_order_id": po.id, "status": "CANCELLED"}


# =====================
# SMART ONLINE REORDER RECOMMENDATIONS
# =====================
# Real listing prices come from Google Shopping via SerpApi. The LLM is not
# used to invent prices; reorder quantities and comparisons stay deterministic.
import asyncio
import math
import os
import time
import httpx

_REORDER_PRICE_CACHE: dict[str, tuple[float, dict]] = {}
_REORDER_PRICE_CACHE_TTL_SECONDS = 20 * 60
_REORDER_PRICE_CACHE_MAX_ITEMS = 250


def _reorder_number(value, default: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def _make_reorder_suggestion(
    product: Product,
    *,
    daily_velocity: Optional[float] = None,
    observed_lead_time_days: Optional[int] = None,
    sales_history_days: int = 30,
) -> dict:
    """Build a conservative reorder suggestion from recorded sales and receipts.

    When history is available, target coverage uses realized invoice quantities
    and observed purchase-order receipt lead time. With no usable history, fall
    back to configured stock limits and label the fallback explicitly.
    """
    current_stock = max(0.0, _reorder_number(product.current_stock))
    minimum = max(0.0, _reorder_number(product.min_stock))
    reorder_level = max(0.0, _reorder_number(product.reorder_level))
    trigger_stock = max(minimum, reorder_level)
    configured_max = _reorder_number(product.max_stock)

    has_sales_history = daily_velocity is not None and math.isfinite(daily_velocity) and daily_velocity > 0
    velocity = max(0.0, _reorder_number(daily_velocity))
    lead_time_days = max(0, int(observed_lead_time_days)) if observed_lead_time_days is not None else 7
    lead_time_basis = (
        "observed_purchase_receipts"
        if observed_lead_time_days is not None
        else "seven_day_fallback_no_receipt_history"
    )

    if has_sales_history:
        safety_days = max(3, math.ceil(lead_time_days * 0.20))
        demand_target = math.ceil(velocity * (lead_time_days + safety_days))
        target_stock = max(math.ceil(trigger_stock), demand_target)
        if configured_max > 0:
            target_stock = min(target_stock, math.ceil(configured_max))
        target_stock = max(math.ceil(current_stock), target_stock)
        suggested_qty = max(0, math.ceil(target_stock - current_stock))
        basis = (
            "30_day_realized_sales_and_observed_receipt_lead_time"
            if observed_lead_time_days is not None
            else "30_day_realized_sales_and_fallback_7_day_lead_time"
        )
    else:
        target_stock = max(1, math.ceil(trigger_stock * 2))
        if configured_max > 0:
            target_stock = min(target_stock, math.ceil(configured_max))
        target_stock = max(target_stock, math.ceil(current_stock) + 1)
        suggested_qty = max(1, math.ceil(target_stock - current_stock))
        basis = "configured_minimum_and_reorder_level_no_sales_history"

    if current_stock <= 0:
        urgency = "CRITICAL"
    elif trigger_stock > 0 and current_stock <= trigger_stock / 2:
        urgency = "HIGH"
    else:
        urgency = "REORDER"

    return {
        "product_id": int(product.id),
        "product_name": str(product.product_name or ""),
        "sku": str(product.sku or ""),
        "category": str(product.category or ""),
        "current_stock": round(current_stock, 3),
        "min_stock": round(minimum, 3),
        "reorder_level": round(reorder_level, 3),
        "target_stock": int(target_stock),
        "suggested_reorder_qty": int(suggested_qty),
        "urgency": urgency,
        "recorded_purchase_price": round(_reorder_number(product.purchase_price), 2),
        "catalog_selling_price": round(_reorder_number(product.unit_price), 2),
        "daily_sales_velocity": round(velocity, 4),
        "sales_history_days": sales_history_days if has_sales_history else 0,
        "lead_time_days": lead_time_days,
        "lead_time_basis": lead_time_basis,
        "recommendation_basis": basis,
        "currency": "INR",
        "online_offers": [],
        "best_offer": None,
        "best_online_price": None,
        "price_difference_vs_recorded_cost": None,
        "price_difference_percent": None,
        "price_comparison_status": "NOT_CHECKED",
        "online_lookup_message": None,
    }

async def _search_online_supplier_prices(
    client: httpx.AsyncClient,
    product_name: str,
    category: str,
) -> dict:
    api_key = (os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY") or "").strip()
    if not api_key:
        return {
            "offers": [],
            "message": "Live online prices are not configured. Set SERPAPI_API_KEY on the backend to enable Google Shopping lookups.",
            "configured": False,
        }

    query = " ".join(part for part in (product_name.strip(), category.strip()) if part).strip()
    if not query:
        return {"offers": [], "message": "Product name is missing, so no price search was made.", "configured": True}

    cache_key = query.casefold()
    now = time.monotonic()
    cached = _REORDER_PRICE_CACHE.get(cache_key)
    if cached and now - cached[0] < _REORDER_PRICE_CACHE_TTL_SECONDS:
        return {**cached[1], "cached": True}

    try:
        response = await client.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_shopping",
                "q": query,
                "gl": "in",
                "hl": "en",
                "num": 6,
                "api_key": api_key,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            return {
                "offers": [],
                "message": "Online price provider returned an error. Check the search API key or quota.",
                "configured": True,
            }

        offers = []
        for result in (payload.get("shopping_results") or [])[:10]:
            title = str(result.get("title") or "").strip()
            source = str(result.get("source") or "").strip()
            link = str(result.get("product_link") or "").strip()
            price = _reorder_number(result.get("extracted_price"), -1)
            if not title or price <= 0:
                continue
            if not link.startswith("https://"):
                link = ""
            offers.append({
                "title": title[:240],
                "source": source[:120] or "Online seller",
                "price": round(price, 2),
                "price_text": str(result.get("price") or f"₹{price:.2f}")[:60],
                "currency": "INR",
                "url": link,
                "rating": _reorder_number(result.get("rating"), 0) or None,
                "reviews": int(_reorder_number(result.get("reviews"), 0)),
                "delivery": str(result.get("delivery") or "")[:180],
            })

        offers.sort(key=lambda offer: offer["price"])
        found = {
            "offers": offers[:6],
            "message": None if offers else "No priced Google Shopping listings were returned for this product.",
            "configured": True,
        }
        if len(_REORDER_PRICE_CACHE) >= _REORDER_PRICE_CACHE_MAX_ITEMS:
            oldest_key = min(_REORDER_PRICE_CACHE, key=lambda key: _REORDER_PRICE_CACHE[key][0])
            _REORDER_PRICE_CACHE.pop(oldest_key, None)
        _REORDER_PRICE_CACHE[cache_key] = (now, found)
        return found
    except (httpx.HTTPError, ValueError, TypeError):
        return {
            "offers": [],
            "message": "Online price lookup failed temporarily. Inventory and reorder suggestions are still available.",
            "configured": True,
        }


@router.get("/reorder-recommendations")
async def get_reorder_recommendations(
    lookup_online: bool = Query(True),
    limit: int = Query(12, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Return demand-based low-stock suggestions from recorded sales and receipts.

    When history is unavailable, suggestions explicitly identify their fallback
    basis instead of claiming a data-driven forecast.
    """
    shop_id = resolve_shop_id(current_user)
    products = (
        db.query(Product)
        .filter(Product.user_id == shop_id, Product.is_active.is_(True))
        .order_by(Product.current_stock.asc(), Product.product_name.asc())
        .all()
    )

    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    since = today - timedelta(days=29)
    sales_rows = (
        db.query(
            InvoiceLineItem.product_id,
            func.coalesce(func.sum(InvoiceLineItem.quantity), 0).label("qty_sold"),
        )
        .join(Invoice, Invoice.id == InvoiceLineItem.invoice_id)
        .filter(
            Invoice.user_id == shop_id,
            Invoice.invoice_date >= since,
            Invoice.invoice_date <= today,
            InvoiceLineItem.product_id.isnot(None),
            *recognized_invoice_filters(),
        )
        .group_by(InvoiceLineItem.product_id)
        .all()
    )
    daily_velocity_by_product = {
        int(product_id): max(0.0, _reorder_number(qty_sold)) / 30.0
        for product_id, qty_sold in sales_rows
        if product_id is not None
    }

    # Estimate supplier lead times from observed PO receipt movements; expected
    # delivery dates are plans, not proof that goods arrived.
    receipt_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=365)
    completed_pos = (
        db.query(PurchaseOrder)
        .filter(
            PurchaseOrder.shop_id == shop_id,
            PurchaseOrder.status.in_([
                PurchaseOrderStatus.RECEIVED,
                PurchaseOrderStatus.PARTIALLY_RECEIVED,
                PurchaseOrderStatus.DELIVERED,
            ]),
            PurchaseOrder.created_at >= receipt_cutoff,
        )
        .order_by(PurchaseOrder.created_at.desc())
        .limit(500)
        .all()
    )
    po_by_id = {int(po.id): po for po in completed_pos}
    lead_days_by_product: dict[int, list[int]] = {}
    if po_by_id:
        receipt_movements = (
            db.query(StockMovement)
            .filter(
                StockMovement.created_at >= receipt_cutoff,
                StockMovement.reference_id.like("PO-%-R-%"),
            )
            .order_by(StockMovement.created_at.asc())
            .limit(5000)
            .all()
        )
        first_receipt_by_po: dict[int, date] = {}
        po_product_ids: dict[int, set[int]] = {}
        for po in completed_pos:
            try:
                po_items = json.loads(po.items_json or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(po_items, list):
                po_product_ids[int(po.id)] = {
                    int(item["product_id"])
                    for item in po_items
                    if isinstance(item, dict) and item.get("product_id") is not None
                }
        for movement in receipt_movements:
            match = re.match(r"^PO-(\d+)-R-", str(movement.reference_id or ""))
            if not match:
                continue
            po_id = int(match.group(1))
            po_record = po_by_id.get(po_id)
            if po_record is None or movement.created_at is None:
                continue
            receipt_date = movement.created_at.date()
            previous = first_receipt_by_po.get(po_id)
            if previous is None or receipt_date < previous:
                first_receipt_by_po[po_id] = receipt_date
        for po_id, receipt_date in first_receipt_by_po.items():
            po_record = po_by_id.get(po_id)
            if po_record is None or po_record.created_at is None:
                continue
            lead_days = max(0, (receipt_date - po_record.created_at.date()).days)
            for product_id in po_product_ids.get(po_id, set()):
                lead_days_by_product.setdefault(product_id, []).append(lead_days)

    observed_lead_time_by_product = {
        product_id: sorted(days)[(len(days) - 1) // 2]
        for product_id, days in lead_days_by_product.items()
        if days
    }
    items = [
        _make_reorder_suggestion(
            product,
            daily_velocity=daily_velocity_by_product.get(int(product.id)),
            observed_lead_time_days=observed_lead_time_by_product.get(int(product.id)),
            sales_history_days=30,
        )
        for product in products
        if _reorder_number(product.current_stock) <= max(
            _reorder_number(product.min_stock),
            _reorder_number(product.reorder_level),
        )
    ]
    total_low_stock = len(items)
    items = items[:limit]
    api_key_configured = bool(
        (os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY") or "").strip()
    )

    if lookup_online and api_key_configured and items:
        semaphore = asyncio.Semaphore(4)
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
            async def enrich(item: dict) -> None:
                async with semaphore:
                    result = await _search_online_supplier_prices(
                        client, item["product_name"], item["category"]
                    )
                offers = result.get("offers") or []
                item["online_offers"] = offers
                item["best_offer"] = offers[0] if offers else None
                item["best_online_price"] = offers[0]["price"] if offers else None
                item["online_lookup_message"] = result.get("message")
                item["price_comparison_status"] = "LIVE_LISTINGS" if offers else "NO_LISTINGS"

                recorded_cost = item["recorded_purchase_price"]
                if offers and recorded_cost > 0:
                    difference = round(recorded_cost - offers[0]["price"], 2)
                    item["price_difference_vs_recorded_cost"] = difference
                    item["price_difference_percent"] = round(
                        (difference / recorded_cost) * 100, 2
                    )
                    item["price_comparison_status"] = (
                        "ONLINE_LOWER" if difference > 0
                        else "ONLINE_HIGHER" if difference < 0
                        else "PRICE_MATCH"
                    )

            await asyncio.gather(*(enrich(item) for item in items))
    elif lookup_online and not api_key_configured:
        for item in items:
            item["price_comparison_status"] = "PROVIDER_NOT_CONFIGURED"
            item["online_lookup_message"] = (
                "Set SERPAPI_API_KEY on the backend to fetch live online listings. "
                "The stock-based reorder suggestion remains available."
            )
    else:
        for item in items:
            item["price_comparison_status"] = "NOT_REQUESTED"

    notice = (
        "Online listing prices can vary by pack size, brand, delivery charges and location. "
        "Verify the item/pack and seller before ordering. Creating a Retail Mind PO does not "
        "place an order with the external website."
    )
    if lookup_online and not api_key_configured:
        notice = (
            "Online price search needs SERPAPI_API_KEY in the backend environment. "
            + notice
        )

    return {
        "shop_id": shop_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "low_stock_count": total_low_stock,
        "returned_count": len(items),
        "truncated": total_low_stock > len(items),
        "online_lookup_requested": lookup_online,
        "online_lookup_configured": api_key_configured,
        "provider": "Google Shopping via SerpApi" if api_key_configured else None,
        "notice": notice,
        "items": items,
    }
