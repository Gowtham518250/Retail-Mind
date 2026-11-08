"""Event-driven Grow My Shop campaign drafting.

This worker creates private drafts only. It never publishes to social networks.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

from sqlalchemy import func

from models import (
    GrowthMarketingAutomationSettings,
    GrowthMarketingCampaign,
    GrowthMarketingTrigger,
    Product,
    ShopProfile,
)


_RESTRICTED_MARKETING_PATTERN = re.compile(
    r"\b(?:alcohol|beer|wine|liquor|vodka|whisky|whiskey|rum|tequila|gin|champagne|cider|"
    r"tobacco|cigarette|cigar|vape|vaping|e-cigarette|nicotine|"
    r"marijuana|cannabis|weed|thc|cbd|prescription|controlled-substance|steroid|"
    r"gambling|betting|casino|sports-betting|lottery|firearm|gun|ammunition|weapon|"
    r"switchblade|taser|pepper-spray|pornography|adult-toy|sex-toy|diet-pill|laxative)\b",
    re.IGNORECASE,
)


def _is_restricted_marketing_product(product: Product | None) -> bool:
    if product is None:
        return False
    return any(
        _RESTRICTED_MARKETING_PATTERN.search(str(value or ""))
        for value in (product.product_name, getattr(product, "category", None))
    )


def enqueue_product_created_trigger(db, shop_id: int, product_id: int) -> bool:
    """Queue a new-product trigger only when the shop explicitly enabled it."""
    settings = db.query(GrowthMarketingAutomationSettings).filter(
        GrowthMarketingAutomationSettings.shop_id == int(shop_id),
        GrowthMarketingAutomationSettings.enabled.is_(True),
        GrowthMarketingAutomationSettings.new_products_enabled.is_(True),
    ).first()
    if settings is None:
        return False

    trigger_key = f"new-product:{int(product_id)}"
    existing = db.query(GrowthMarketingTrigger.id).filter(
        GrowthMarketingTrigger.shop_id == int(shop_id),
        GrowthMarketingTrigger.trigger_key == trigger_key,
    ).first()
    if existing:
        return False

    db.add(GrowthMarketingTrigger(
        shop_id=int(shop_id),
        trigger_key=trigger_key,
        trigger_type="new_product",
        product_id=int(product_id),
        status="PENDING",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    return True


def _shop_address(profile: ShopProfile) -> str:
    parts = [
        profile.address_line1,
        profile.address_line2,
        profile.address,
        profile.location,
        profile.city,
        profile.state,
        profile.postal_code,
    ]
    result = []
    for item in parts:
        value = str(item or "").strip()
        if value and value not in result:
            result.append(value)
    return ", ".join(result)[:1000]


def _shop_snapshot(profile: ShopProfile) -> dict:
    return {
        "shop_address": _shop_address(profile),
        "shop_location": profile.location,
        "shop_city": profile.city,
        "shop_state": profile.state,
        "shop_postal_code": profile.postal_code,
        "shop_latitude": profile.latitude,
        "shop_longitude": profile.longitude,
        "shop_phone": profile.phone,
        "shop_website": profile.website,
        "shop_logo_url": profile.logo_url,
    }


def _weekly_limit_reached(db, shop_id: int, settings, now: datetime) -> bool:
    count = db.query(func.count(GrowthMarketingCampaign.id)).filter(
        GrowthMarketingCampaign.shop_id == int(shop_id),
        GrowthMarketingCampaign.trigger_type.in_(("new_product", "weekly")),
        GrowthMarketingCampaign.created_at >= now - timedelta(days=7),
    ).scalar() or 0
    return int(count) >= int(settings.max_campaigns_per_week or 3)


def _queue_due_weekly_triggers(db, now: datetime) -> int:
    """Create at most one weekly trigger per shop and ISO week."""
    created = 0
    india_timezone = timezone(timedelta(hours=5, minutes=30))
    local_now = datetime.now(timezone.utc).astimezone(india_timezone)
    settings_rows = db.query(GrowthMarketingAutomationSettings).filter(
        GrowthMarketingAutomationSettings.enabled.is_(True),
        GrowthMarketingAutomationSettings.weekly_enabled.is_(True),
        GrowthMarketingAutomationSettings.weekly_day == local_now.weekday(),
    ).all()
    iso = local_now.isocalendar()
    trigger_key = f"weekly:{iso.year}:{iso.week:02d}"
    for settings in settings_rows:
        existing = db.query(GrowthMarketingTrigger.id).filter(
            GrowthMarketingTrigger.shop_id == settings.shop_id,
            GrowthMarketingTrigger.trigger_key == trigger_key,
        ).first()
        if existing or _weekly_limit_reached(db, settings.shop_id, settings, now):
            continue
        db.add(GrowthMarketingTrigger(
            shop_id=settings.shop_id,
            trigger_key=trigger_key,
            trigger_type="weekly",
            product_id=None,
            status="PENDING",
            created_at=now,
        ))
        created += 1
    return created


def _build_auto_copy(profile: ShopProfile, product: Product | None, language: str, trigger_type: str) -> tuple[str, str]:
    shop_name = str(profile.shop_name or 'Our shop').strip()
    if trigger_type == 'weekly':
        headline = {
            'te': 'ఈ వారం మా దుకాణంలో అందుబాటులో ఉన్నవి',
            'hi': 'इस सप्ताह हमारी दुकान में उपलब्ध उत्पाद',
        }.get(language, "This week's shop highlights")
    else:
        headline = {
            'te': 'మా కొత్త ఉత్పత్తిని చూడండి',
            'hi': 'हमारा नया उत्पाद देखें',
        }.get(language, 'Discover our new product')

    address = _shop_address(profile)
    context = {
        'shop_name': shop_name,
        'shop_address': address,
        'shop_city': profile.city,
        'shop_state': profile.state,
        'shop_phone': profile.phone,
        'product_name': product.product_name if product is not None else None,
        'product_price_inr': float(product.unit_price) if product is not None and product.unit_price is not None else None,
        'goal': 'new_product' if trigger_type == 'new_product' else 'nearby',
        'offer_provided_by_owner': '',
    }
    # Use Groq when it is configured; deterministic templates remain the fallback.
    try:
        from growth_suite import _generate_growth_copy_with_groq

        generated = _generate_growth_copy_with_groq(context, language)
        if generated and generated.get('headline') and generated.get('caption'):
            return str(generated['headline'])[:120], str(generated['caption'])[:1200]
    except Exception:
        pass

    lines = [shop_name, headline]
    if product is not None:
        lines.append(f'{product.product_name} — ₹{Decimal(str(product.unit_price or 0)):,.2f}')
    if address:
        lines.append(f'Visit us: {address}')
    if profile.phone:
        lines.append(f'Contact: {str(profile.phone).strip()}')
    lines.append('Review this draft and confirm the details before sharing.')
    return headline[:120], '\n'.join(lines)[:1200]

def process_pending_marketing_triggers(db, limit: int = 50) -> dict:
    """Create owner-review drafts from queued triggers with per-shop limits."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    weekly_queued = _queue_due_weekly_triggers(db, now)
    if weekly_queued:
        db.flush()

    processed = 0
    skipped = 0
    triggers = db.query(GrowthMarketingTrigger).filter(
        GrowthMarketingTrigger.status == "PENDING",
    ).order_by(
        GrowthMarketingTrigger.created_at.asc(),
        GrowthMarketingTrigger.id.asc(),
    ).limit(max(1, min(int(limit), 200))).all()

    for trigger in triggers:
        settings = db.query(GrowthMarketingAutomationSettings).filter(
            GrowthMarketingAutomationSettings.shop_id == trigger.shop_id,
            GrowthMarketingAutomationSettings.enabled.is_(True),
        ).first()
        if settings is None:
            trigger.status = "SKIPPED"
            trigger.error = "Marketing automation was disabled before this trigger was processed."
            trigger.processed_at = now
            skipped += 1
            continue
        if trigger.trigger_type == "new_product" and not settings.new_products_enabled:
            trigger.status = "SKIPPED"
            trigger.processed_at = now
            skipped += 1
            continue
        if trigger.trigger_type == "weekly" and not settings.weekly_enabled:
            trigger.status = "SKIPPED"
            trigger.processed_at = now
            skipped += 1
            continue
        if _weekly_limit_reached(db, trigger.shop_id, settings, now):
            trigger.status = "SKIPPED"
            trigger.error = "Shop weekly campaign limit reached."
            trigger.processed_at = now
            skipped += 1
            continue

        profile = db.query(ShopProfile).filter(
            ShopProfile.shop_id == trigger.shop_id,
        ).first()
        if profile is None:
            trigger.status = "SKIPPED"
            trigger.error = "Shop profile is missing."
            trigger.processed_at = now
            skipped += 1
            continue

        product = None
        if trigger.product_id is not None:
            product = db.query(Product).filter(
                Product.id == trigger.product_id,
                Product.user_id == trigger.shop_id,
                Product.is_active.is_(True),
                Product.current_stock > 0,
            ).first()
        elif trigger.trigger_type == "weekly":
            product = db.query(Product).filter(
                Product.user_id == trigger.shop_id,
                Product.is_active.is_(True),
                Product.current_stock > 0,
            ).order_by(Product.id.desc()).first()

        if trigger.trigger_type in {"new_product", "weekly"} and product is None:
            trigger.status = "SKIPPED"
            trigger.error = "No eligible in-stock product was found."
            trigger.processed_at = now
            skipped += 1
            continue
        if _is_restricted_marketing_product(product):
            trigger.status = "SKIPPED"
            trigger.error = "This product category is not eligible for promotional drafts."
            trigger.processed_at = now
            skipped += 1
            continue

        campaign_key = (
            f"auto-new-{trigger.product_id}"
            if trigger.trigger_type == "new_product"
            else f"auto-weekly-{trigger.trigger_key.rsplit(':', 2)[-2]}-{trigger.trigger_key.rsplit(':', 1)[-1]}"
        )[:64]
        existing = db.query(GrowthMarketingCampaign).filter(
            GrowthMarketingCampaign.shop_id == trigger.shop_id,
            GrowthMarketingCampaign.campaign_key == campaign_key,
        ).first()
        if existing is None:
            headline, caption = _build_auto_copy(
                profile, product, settings.language or "en", trigger.trigger_type
            )
            snapshot = _shop_snapshot(profile)
            product_price = Decimal(str(product.unit_price)) if product is not None and product.unit_price is not None else None
            from marketing_poster_renderer import render_retail_poster
            poster_asset = render_retail_poster({
                "shop_name": str(profile.shop_name or "My Shop"),
                "shop_address": snapshot.get("shop_address"),
                "shop_phone": snapshot.get("shop_phone"),
                "shop_logo_url": snapshot.get("shop_logo_url"),
                "product_name": product.product_name if product is not None else "",
                "product_image_url": getattr(product, "image_url", None) if product is not None else None,
                "original_price_inr": float(product_price) if product_price is not None else None,
                "headline": headline,
                "caption": caption,
                "goal": "new_product" if trigger.trigger_type == "new_product" else "nearby",
                "language": settings.language or "en",
                "ad_format": "feed",
            })
            db.add(GrowthMarketingCampaign(
                shop_id=trigger.shop_id,
                campaign_key=campaign_key,
                product_id=product.id if product is not None else None,
                product_name=product.product_name if product is not None else None,
                product_price=product_price,
                original_price=product_price,
                goal="new_product" if trigger.trigger_type == "new_product" else "nearby",
                language=settings.language or "en",
                ad_format="feed",
                template=poster_asset["template"],
                shop_name=str(profile.shop_name or "My Shop")[:200],
                headline=headline,
                caption=caption,
                offer="",
                offer_code="",
                generation_source="automation",
                trigger_type=trigger.trigger_type,
                status="PENDING_APPROVAL",
                content_version=1,
                poster_svg=poster_asset["poster_svg"],
                **snapshot,
                created_at=now,
                updated_at=now,
            ))
        trigger.status = "PROCESSED"
        trigger.attempts = int(trigger.attempts or 0) + 1
        trigger.processed_at = now
        trigger.error = None
        processed += 1

    db.commit()
    return {"processed": processed, "skipped": skipped, "weekly_triggers_queued": weekly_queued}
