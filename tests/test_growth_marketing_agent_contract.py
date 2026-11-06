import inspect

import pytest
from pydantic import ValidationError

from growth_suite import (
    MarketingCopyRequest,
    generate_marketing_copy,
    router,
    _growth_copy_fallback,
)


def test_marketing_copy_request_only_accepts_supported_campaign_options():
    request = MarketingCopyRequest(
        goal="new_product",
        language="te",
        ad_format="story",
        product_id=12,
        offer="Owner-approved offer",
    )
    assert request.product_id == 12
    assert request.language == "te"
    with pytest.raises(ValidationError):
        MarketingCopyRequest(goal="invent_a_goal")


def test_marketing_endpoint_is_authenticated_and_tenant_scoped():
    source = inspect.getsource(generate_marketing_copy)
    assert "Depends(check_current_user)" in source
    assert "ShopProfile.shop_id == user_id" in source
    assert "Product.user_id == user_id" in source
    assert "Product.id == data.product_id" in source
    assert "Product.current_stock" not in source or "stock_quantity <= 0" in source
    assert '"/marketing/generate"' in {
        getattr(route, "path", "") for route in router.routes
    }


def test_fallback_copy_does_not_invent_an_offer():
    result = _growth_copy_fallback(
        shop_name="Green Basket",
        goal="nearby",
        language="en",
        product_name="Rice",
        product_price=55.0,
        offer="",
        offer_code="",
    )
    assert "Green Basket" in result["caption"]
    assert "Rice" in result["caption"]
    assert "₹55.00" in result["caption"]
    assert "Offer:" not in result["caption"]
    assert "discount" not in result["caption"].lower()
