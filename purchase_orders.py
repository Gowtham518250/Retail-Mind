"""
📦 PURCHASE ORDERS API — AI Shop Pro Enterprise Backend
Covers:
  - Create purchase orders to wholesalers
  - Mark order as delivered (auto-adds stock to inventory)
  - List all POs with status
  - Cancel PO
  - Auto-write to UniversalTransaction journal on delivery
"""

from typing import Optional, List
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db
from models import PurchaseOrder, Product, StockMovement, UniversalTransaction
from security import owner_only, sanitize_input, resolve_shop_id
import json

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])

# =====================
# SCHEMAS
# =====================
class POItem(BaseModel):
    product_id: Optional[int] = None
    product_name: Optional[str] = None       # make optional
    quantity: int = Field(..., gt=0)
    unit_cost: Optional[float] = Field(None, ge=0)   # keep original
    unit_price: Optional[float] = Field(None, ge=0)

class PurchaseOrderCreate(BaseModel):
    supplier_name: str = Field(..., min_length=2, max_length=100)
    expected_delivery: Optional[date] = None
    items: List[POItem] = Field(..., min_length=1)
    notes: Optional[str] = None

class PurchaseOrderResponse(BaseModel):
    id: int
    supplier_name: str
    status: str
    total_cost: float
    expected_delivery: Optional[date]
    items_json: str
    created_at: datetime

    class Config:
        from_attributes = True

# =====================
# ENDPOINTS
# =====================

@router.post("/", response_model=PurchaseOrderResponse)
def create_purchase_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Create a new purchase order to a supplier"""
    shop_id = resolve_shop_id(current_user)
    supplier_name = sanitize_input(data.supplier_name, "supplier_name")

    items_data = [item.model_dump() for item in data.items]
    total_cost = sum(item["quantity"] * (item.get("unit_cost") or item.get("unit_price") or 0) for item in items_data)

    po = PurchaseOrder(
        shop_id=shop_id,
        supplier_name=supplier_name,
        status="PENDING",
        total_cost=total_cost,
        items_json=json.dumps(items_data),
        expected_delivery=data.expected_delivery,
    )
    db.add(po)
    try:
        db.commit()
        db.refresh(po)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create purchase order: {str(e)}")
    return po


@router.get("/", response_model=List[PurchaseOrderResponse])
def list_purchase_orders(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """List all purchase orders for this shop"""
    shop_id = resolve_shop_id(current_user)
    q = db.query(PurchaseOrder).filter(PurchaseOrder.shop_id == shop_id)
    if status:
        q = q.filter(PurchaseOrder.status == status.upper())
    orders = q.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit).all()
    return orders


@router.post("/{po_id}/mark-delivered")
def mark_po_delivered(
    po_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """
    Mark a PO as delivered.
    This AUTOMATICALLY adds received stock quantities to inventory.
    """
    shop_id = resolve_shop_id(current_user)
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.shop_id == shop_id,
    ).first()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status == "DELIVERED":
        raise HTTPException(status_code=409, detail="This PO is already marked as delivered.")
    if po.status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Cannot deliver a cancelled PO.")

    items = json.loads(po.items_json)
    stock_updates = []

    for item in items:
        if item.get("product_id"):
            product = db.query(Product).filter(
                Product.id == item["product_id"],
                Product.user_id == shop_id,
            ).with_for_update().first()
            if product:
                product.current_stock = (product.current_stock or 0) + item["quantity"]
                # Log stock movement
                movement = StockMovement(
                    product_id=product.id,
                    movement_type="IN",
                    quantity=item["quantity"],
                    reason="Purchase Order Delivery",
                    reference_id=f"PO-{po.id}",
                )
                db.add(movement)
                stock_updates.append({
                    "product_name": product.product_name,
                    "qty_added": item["quantity"],
                    "new_stock": product.current_stock,
                })

    po.status = "DELIVERED"

    # Write to universal transaction journal
    tx = UniversalTransaction(
        shop_id=shop_id,
        tx_type="EXPENSE",
        category="PO_PAYMENT",
        amount=float(po.total_cost),
        reference_id=f"PO-{po.id}",
        description=f"Purchase Order from {po.supplier_name}",
    )
    db.add(tx)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update PO delivery: {str(e)}")

    return {
        "message": f"PO #{po.id} marked as delivered. Stock updated.",
        "stock_updates": stock_updates,
        "total_cost": float(po.total_cost),
    }


@router.post("/{po_id}/cancel")
def cancel_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Cancel a purchase order"""
    shop_id = resolve_shop_id(current_user)
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.shop_id == shop_id,
    ).first()

    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status == "DELIVERED":
        raise HTTPException(status_code=409, detail="Cannot cancel a delivered PO.")

    po.status = "CANCELLED"
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel purchase order: {str(e)}")
    return {"message": f"Purchase order #{po_id} has been cancelled."}
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


def _make_reorder_suggestion(product: Product) -> dict:
    """Build a conservative shop-scoped suggestion from persisted stock settings."""
    current_stock = max(0.0, _reorder_number(product.current_stock))
    minimum = max(0.0, _reorder_number(product.min_stock))
    reorder_level = max(0.0, _reorder_number(product.reorder_level))
    trigger_stock = max(minimum, reorder_level)

    # Return only products at or below their configured trigger.
    target_stock = max(1, math.ceil(trigger_stock * 2))
    configured_max = _reorder_number(product.max_stock)
    if configured_max > 0:
        target_stock = min(target_stock, math.ceil(configured_max))
    target_stock = max(target_stock, math.ceil(current_stock) + 1)
    suggested_qty = max(1, math.ceil(target_stock - current_stock))

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
    """Return low-stock items, suggested replenishment quantities and verified listing prices."""
    shop_id = resolve_shop_id(current_user)
    products = (
        db.query(Product)
        .filter(Product.user_id == shop_id, Product.is_active.is_(True))
        .order_by(Product.current_stock.asc(), Product.product_name.asc())
        .all()
    )

    items = [
        _make_reorder_suggestion(product)
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
