"""Server-side, brandable SVG poster generation for Grow My Shop.

The returned SVG is a complete poster asset. It uses only verified shop/product
facts and never publishes to a social network.
"""
from __future__ import annotations

import base64
import html
import re
from urllib.parse import urlparse


_PALETTES = {
    "price_burst": ("#101014", "#7F1D1D", "#F97316", "#FDE68A", "#FFFFFF"),
    "market": ("#052E2B", "#047857", "#84CC16", "#ECFCCB", "#FFFFFF"),
    "editorial": ("#FFF7ED", "#FED7AA", "#9A3412", "#7C2D12", "#1C1917"),
    "festive": ("#450A0A", "#B91C1C", "#F97316", "#FDE68A", "#FFFFFF"),
    "bold": ("#111827", "#4338CA", "#7C3AED", "#FDE68A", "#FFFFFF"),
}


def _safe_text(value, limit=180):
    return html.escape(re.sub(r"\s+", " ", str(value or "")).strip()[:limit])


def _safe_image_url(value):
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme == "https" and parsed.netloc and not parsed.username and not parsed.password:
        return html.escape(raw, quote=True)
    return ""


def choose_poster_template(goal: str, discount_price=None, offer: str = "") -> str:
    if discount_price is not None or str(offer or "").strip():
        return "price_burst"
    if goal == "clear_stock":
        return "market"
    if goal == "regular_customers":
        return "editorial"
    return "bold"


def render_retail_poster(context: dict, template: str | None = None) -> dict:
    """Return complete SVG poster, data URI, selected style and pixel dimensions."""
    fmt = str(context.get("ad_format") or "feed")
    width, height = {
        "square": (1080, 1080),
        "story": (1080, 1920),
        "feed": (1080, 1350),
    }.get(fmt, (1080, 1350))
    style = template if template in _PALETTES else choose_poster_template(
        str(context.get("goal") or "nearby"),
        context.get("discount_price_inr"),
        context.get("offer_provided_by_owner"),
    )
    bg, mid, accent, highlight, fg = _PALETTES[style]
    shop = _safe_text(context.get("shop_name") or "Your Local Store", 70)
    headline = _safe_text(context.get("headline") or "Discover something special", 110)
    product = _safe_text(context.get("product_name"), 90)
    offer = _safe_text(context.get("offer_provided_by_owner"), 100)
    address = _safe_text(context.get("shop_address"), 130)
    phone = _safe_text(context.get("shop_phone"), 40)
    logo_url = _safe_image_url(context.get("shop_logo_url"))
    product_image = _safe_image_url(context.get("product_image_url"))
    price = context.get("discount_price_inr")
    if price is None:
        price = context.get("original_price_inr")
    price_text = ("₹" + format(float(price), ",.2f").rstrip("0").rstrip(".")) if price is not None else ""
    original = context.get("original_price_inr")
    original_text = ("₹" + format(float(original), ",.2f").rstrip("0").rstrip(".")) if original is not None and price is not None and float(original) > float(price) else ""
    discount = context.get("discount_percent")
    discount_text = (str(round(float(discount))) + "% OFF") if discount is not None else ""
    lang = str(context.get("language") or "en")
    cta = {"te": "ఈరోజే సందర్శించండి", "hi": "आज ही आएँ"}.get(lang, "VISIT US TODAY")
    canvas_radius = 44
    top = 90 if fmt != "story" else 145
    footer_y = height - (145 if fmt != "story" else 190)
    # Each style has its own composition, not just a different background colour.
    if style == "editorial":
        artwork = f"""
        <rect x="64" y="64" width="{width-128}" height="{height-128}" rx="10" fill="none" stroke="{mid}" stroke-width="3"/>
        <path d="M64 {top+70} H{width-64}" stroke="{mid}" stroke-width="2"/>
        <text x="92" y="{top+35}" fill="{mid}" font-size="25" font-family="Noto Sans,sans-serif" letter-spacing="8">THE LOCAL EDIT</text>
        <text x="92" y="{top+190}" fill="{fg}" font-size="76" font-weight="800" font-family="Noto Sans,sans-serif">{headline}</text>
        <path d="M92 {top+235} H330" stroke="{accent}" stroke-width="12"/>
        <rect x="92" y="{top+300}" width="{width-184}" height="430" rx="8" fill="#FFEDD5"/>
        """
        product_y = top + 520
    elif style == "market":
        artwork = f"""
        <path d="M0 0 H{width} V{height} H0 Z" fill="{bg}"/>
        <circle cx="{width-80}" cy="{top+100}" r="230" fill="{mid}" opacity=".8"/>
        <circle cx="70" cy="{height-300}" r="250" fill="{accent}" opacity=".18"/>
        <path d="M0 {top+260} Q{width//2} {top+80} {width} {top+260} V{height} H0 Z" fill="{mid}" opacity=".38"/>
        <text x="78" y="{top+90}" fill="{highlight}" font-size="26" font-weight="700" letter-spacing="5" font-family="Noto Sans,sans-serif">FRESH • LOCAL • EVERYDAY</text>
        <text x="78" y="{top+205}" fill="{fg}" font-size="76" font-weight="900" font-family="Noto Sans,sans-serif">{headline}</text>
        <rect x="78" y="{top+275}" width="{width-156}" height="430" rx="42" fill="#FFFFFF" opacity=".12"/>
        """
        product_y = top + 520
    elif style == "festive":
        artwork = f"""
        <circle cx="{width-70}" cy="{top+100}" r="250" fill="{accent}" opacity=".25"/>
        <circle cx="40" cy="{height-250}" r="280" fill="{highlight}" opacity=".12"/>
        <path d="M0 {top+300} L{width} {top+180} V{height} H0 Z" fill="{mid}" opacity=".65"/>
        <text x="{width//2}" y="{top+85}" text-anchor="middle" fill="{highlight}" font-size="27" font-weight="800" letter-spacing="6" font-family="Noto Sans,sans-serif">A LITTLE CELEBRATION</text>
        <text x="{width//2}" y="{top+210}" text-anchor="middle" fill="{fg}" font-size="78" font-weight="900" font-family="Noto Sans,sans-serif">{headline}</text>
        <path d="M130 {top+275} H{width-130}" stroke="{highlight}" stroke-width="4" stroke-dasharray="12 16"/>
        """
        product_y = top + 520
    elif style == "price_burst":
        artwork = f"""
        <circle cx="{width-160}" cy="{top+330}" r="300" fill="{accent}" opacity=".20"/>
        <circle cx="{width-160}" cy="{top+330}" r="225" fill="none" stroke="{highlight}" stroke-width="8" stroke-dasharray="18 18"/>
        <path d="M0 {top+700} L{width} {top+570} V{height} H0 Z" fill="{mid}" opacity=".75"/>
        <text x="78" y="{top+90}" fill="{highlight}" font-size="27" font-weight="900" letter-spacing="5" font-family="Noto Sans,sans-serif">SHOP SPECIAL</text>
        <text x="78" y="{top+220}" fill="{fg}" font-size="82" font-weight="900" font-family="Noto Sans,sans-serif">{headline}</text>
        """
        product_y = top + 520
    else:
        artwork = f"""
        <circle cx="{width-80}" cy="{top+70}" r="260" fill="{accent}" opacity=".18"/>
        <circle cx="50" cy="{height-260}" r="240" fill="{mid}" opacity=".8"/>
        <rect x="62" y="62" width="{width-124}" height="{height-124}" rx="48" fill="none" stroke="{highlight}" stroke-opacity=".45" stroke-width="3"/>
        <text x="92" y="{top+100}" fill="{highlight}" font-size="25" font-weight="800" letter-spacing="5" font-family="Noto Sans,sans-serif">MADE FOR YOUR NEIGHBOURHOOD</text>
        <text x="92" y="{top+235}" fill="{fg}" font-size="80" font-weight="900" font-family="Noto Sans,sans-serif">{headline}</text>
        """
        product_y = top + 520

    logo = (f'<image href="{logo_url}" x="78" y="{top-55}" width="88" height="88" preserveAspectRatio="xMidYMid meet"/>'
            if logo_url else f'<circle cx="120" cy="{top-10}" r="42" fill="{highlight}"/><text x="120" y="{top+2}" text-anchor="middle" fill="{bg}" font-size="30" font-weight="900" font-family="Noto Sans,sans-serif">{_safe_text((context.get("shop_name") or "S")[:1]).upper()}</text>')
    image = (f'<image href="{product_image}" x="{width-420}" y="{top+320}" width="300" height="300" preserveAspectRatio="xMidYMid meet"/>'
             if product_image else f'<circle cx="{width-270}" cy="{top+470}" r="115" fill="{highlight}" opacity=".14"/><path d="M{width-340} {top+500} l70 -125 70 125 z" fill="{highlight}" opacity=".75"/>')
    product_block = ""
    if product:
        product_block = f"""
        <rect x="78" y="{product_y}" width="{width-156}" height="300" rx="{canvas_radius}" fill="{fg}" opacity=".12" stroke="{fg}" stroke-opacity=".32" stroke-width="2"/>
        <text x="118" y="{product_y+80}" fill="{fg}" font-size="42" font-weight="800" font-family="Noto Sans,sans-serif">{product}</text>
        <text x="118" y="{product_y+190}" fill="{highlight}" font-size="88" font-weight="900" font-family="Noto Sans,sans-serif">{_safe_text(price_text,30)}</text>
        <text x="118" y="{product_y+245}" fill="{fg}" font-size="30" font-family="Noto Sans,sans-serif">{_safe_text(original_text + ('   ' + discount_text if discount_text else ''),70)}</text>
        {image}
        """
    offer_line = f'<text x="80" y="{product_y+360}" fill="{highlight}" font-size="32" font-weight="800" font-family="Noto Sans,sans-serif">{offer}</text>' if offer else ""
    details = " • ".join(x for x in (address, phone) if x)
    footer = f"""
      <rect x="70" y="{footer_y}" width="{width-140}" height="100" rx="28" fill="{highlight}"/>
      <text x="{width//2}" y="{footer_y+63}" text-anchor="middle" fill="{bg}" font-size="34" font-weight="900" font-family="Noto Sans,sans-serif">{_safe_text(cta,60)}</text>
      <text x="{width//2}" y="{height-65}" text-anchor="middle" fill="{fg}" opacity=".88" font-size="23" font-family="Noto Sans,sans-serif">{_safe_text(details,160)}</text>
    """
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
    <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{bg}"/><stop offset="1" stop-color="{mid}"/></linearGradient></defs>
    <rect width="{width}" height="{height}" fill="url(#bg)"/>
    {artwork}{logo}
    <text x="78" y="{top+25}" fill="{fg}" font-size="36" font-weight="900" font-family="Noto Sans,sans-serif">{shop}</text>
    {product_block}{offer_line}{footer}
    </svg>'''
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {
        "template": style,
        "format": fmt,
        "width": width,
        "height": height,
        "mime_type": "image/svg+xml",
        "poster_svg": svg,
        "poster_data_uri": "data:image/svg+xml;base64," + encoded,
    }
