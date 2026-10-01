import re
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from models import Product, ShopProfile


router = APIRouter(prefix="/store", tags=["Customer AI Shopping"])


def _parse_money(text: str) -> float | None:
    match = re.search(
        r"(?:under|below|less\s+than|upto|up\s+to|within|max(?:imum)?\s+of)\s*[₹rs.]*\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _extract_shop_hint(text: str) -> str | None:
    patterns = [
        r"(?:at|from|in|with)\s+(?:the\s+)?(?:shop|store)\s+(.+?)(?:\s+(?:for|with|under|below|less|upto)\b|$)",
        r"(?:shop|store)\s*[:=-]\s*(.+?)(?:\s+(?:for|with|under|below|less|upto)\b|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            hint = match.group(1).strip(" .,?!")
            if hint:
                return hint
    return None


def _extract_product_terms(text: str) -> str:
    cleaned = text
    cleaned = re.sub(
        r"\b(?:find|show|search|give|recommend|suggest|want|need|buy|where\s+can\s+i\s+find)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:cheap(?:est)?|low\s*price|lowest\s*price|best\s*price|budget|best\s*value|best\s*rated|highest\s*rated|top\s*rated|good\s*rating|compare|options?|deals?)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:under|below|less\s+than|upto|up\s+to|within|max(?:imum)?\s+of)\s*[₹rs.]*\s*[0-9][0-9,]*(?:\.[0-9]+)?",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    shop_hint = _extract_shop_hint(text)
    if shop_hint:
        cleaned = cleaned.replace(shop_hint, " ")
    cleaned = re.sub(r"\b(?:at|from|in|with)\s+(?:the\s+)?(?:shop|store)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,?!")
    return cleaned


def _intent(text: str) -> tuple[str, str]:
    normalized = text.lower()
    if re.search(r"best\s*rated|highest\s*rated|top\s*rated|good\s*rating", normalized):
        return "rating", "highest rated"
    if re.search(r"cheap|cheapest|low\s*price|lowest\s*price|budget|best\s*price", normalized):
        return "price", "lowest price"
    if re.search(r"under|below|less\s+than|upto|up\s+to|within", normalized):
        return "budget", "within your budget"
    return "match", "best matching"


@router.get("/customer-ai")
def customer_ai_shopping(
    q: str = Query(..., min_length=2, max_length=300),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Database-grounded customer shopping assistant.

    Rules:
    - Only active online-enabled shops are eligible.
    - Only active/in-stock products are eligible.
    - Natural-language intent changes ranking, not the underlying truth.
    - No product is invented when the database has no match.
    """
    raw_query = q.strip()
    intent, intent_label = _intent(raw_query)
    budget = _parse_money(raw_query)
    shop_hint = _extract_shop_hint(raw_query)
    product_terms = _extract_product_terms(raw_query)

    base = (
        db.query(Product, ShopProfile)
        .join(ShopProfile, ShopProfile.shop_id == Product.user_id)
        .filter(
            Product.is_active.is_(True),
            Product.current_stock > 0,
            (ShopProfile.is_active.is_(True)) | (ShopProfile.is_active.is_(None)),
            ShopProfile.is_online_store_enabled.is_(True),
        )
    )

    if budget is not None:
        base = base.filter(Product.unit_price <= budget)

    if shop_hint:
        base = base.filter(ShopProfile.shop_name.ilike(f"%{shop_hint}%"))

    rows = base.all()

    # Prefer the complete product phrase first, then fall back to token matching.
    searchable = product_terms or raw_query
    tokens = [
        token
        for token in re.split(r"[^a-zA-Z0-9]+", searchable.lower())
        if len(token) >= 2
    ]

    def text_match(product_name: str) -> bool:
        name = product_name.lower()
        if searchable and searchable.lower() in name:
            return True
        return bool(tokens) and all(token in name for token in tokens)

    matched = [(product, shop) for product, shop in rows if text_match(product.product_name)]

    # If the parser removed too much or the customer used a phrase such as
    # "rice with low price", search individual meaningful tokens.
    if not matched and tokens:
        matched = [
            (product, shop)
            for product, shop in rows
            if any(token in product.product_name.lower() for token in tokens)
        ]

    if intent == "price":
        matched.sort(key=lambda pair: (float(pair[0].price or 0), -float(pair[1].rating_score or 0)))
    elif intent == "rating":
        matched.sort(key=lambda pair: (-float(pair[1].rating_score or 0), -int(pair[1].rating_count or 0), float(pair[0].price or 0)))
    elif intent == "budget":
        matched.sort(key=lambda pair: (float(pair[0].price or 0), -float(pair[1].rating_score or 0)))
    else:
        matched.sort(
            key=lambda pair: (
                -float(pair[1].rating_score or 0),
                float(pair[0].price or 0),
            )
        )

    matched = matched[:limit]

    if not matched:
        target = product_terms or raw_query
        scope = f" at {shop_hint}" if shop_hint else ""
        budget_text = f" under ₹{budget:,.2f}" if budget is not None else ""
        message = (
            f"Product unavailable: I couldn't find “{target}”{scope}{budget_text} "
            "in any online-enabled shop with stock right now."
        )
        return {
            "available": False,
            "query": raw_query,
            "intent": intent,
            "intent_label": intent_label,
            "product_query": target,
            "shop_hint": shop_hint,
            "budget": budget,
            "message": message,
            "recommendations": [],
        }

    recommendations = []
    for product, shop in matched:
        recommendations.append(
            {
                "product_id": product.id,
                "product_name": product.product_name,
                "description": getattr(product, "description", None),
                "category": getattr(product, "category", None),
                "price": float(product.unit_price or 0),
                "stock_available": float(product.current_stock or 0),
                "shop_id": shop.shop_id,
                "shop_name": shop.shop_name,
                "shop_tagline": getattr(shop, "shop_tagline", None),
                "shop_address": getattr(shop, "address", None),
                "rating": round(float(shop.rating_score or 0), 1),
                "rating_count": int(shop.rating_count or 0),
                "online_setup_fee": float(getattr(shop, "online_setup_fee", 0) or 0),
                "reason": (
                    f"Lowest price ₹{float(product.unit_price or 0):,.2f}"
                    if intent == "price"
                    else f"Rated {float(shop.rating_score or 0):.1f}/5"
                    if intent == "rating"
                    else intent_label
                ),
            }
        )

    best = recommendations[0]
    message = (
        f"I found {len(recommendations)} matching option"
        f"{'' if len(recommendations) == 1 else 's'} across online-enabled shops. "
        f"The top match is {best['product_name']} at {best['shop_name']} for "
        f"₹{best['price']:,.2f}."
    )
    if intent == "rating":
        message += f" It has a {best['rating']:.1f}/5 shop rating."
    elif intent in {"price", "budget"}:
        message += " Prices are compared using currently available stock."

    return {
        "available": True,
        "query": raw_query,
        "intent": intent,
        "intent_label": intent_label,
        "product_query": product_terms,
        "shop_hint": shop_hint,
        "budget": budget,
        "message": message,
        "recommendations": recommendations,
    }
