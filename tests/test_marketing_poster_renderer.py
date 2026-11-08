from xml.etree import ElementTree

from marketing_poster_renderer import choose_poster_template, render_retail_poster


def test_smart_template_selects_offer_style_for_discounted_product():
    assert choose_poster_template("nearby", discount_price=89, offer="Weekend deal") == "price_burst"


def test_poster_renderer_returns_valid_unique_svg_and_dimensions():
    result = render_retail_poster({
        "shop_name": "Gowtham Market",
        "shop_address": "Kadapa, Andhra Pradesh",
        "shop_phone": "9999999999",
        "product_name": "Basmati Rice",
        "original_price_inr": 120,
        "discount_price_inr": 99,
        "discount_percent": 17.5,
        "offer_provided_by_owner": "Weekend offer",
        "headline": "A better deal for your home",
        "goal": "nearby",
        "language": "en",
        "ad_format": "feed",
    })
    assert result["template"] == "price_burst"
    assert result["width"] == 1080
    assert result["height"] == 1350
    assert result["mime_type"] == "image/svg+xml"
    root = ElementTree.fromstring(result["poster_svg"])
    assert root.tag.endswith("svg")
    assert "Gowtham Market" in result["poster_svg"]
    assert "Basmati Rice" in result["poster_svg"]
    assert "₹99" in result["poster_svg"]
    assert result["poster_data_uri"].startswith("data:image/svg+xml;base64,")


def test_poster_escapes_untrusted_shop_and_product_text():
    result = render_retail_poster({
        "shop_name": '<script>alert("x")</script>',
        "product_name": "Rice & Wheat",
        "headline": "Fresh < offers > today",
        "goal": "nearby",
        "language": "en",
        "ad_format": "square",
    })
    assert "<script>" not in result["poster_svg"]
    assert "Rice &amp; Wheat" in result["poster_svg"]
    assert result["height"] == 1080
