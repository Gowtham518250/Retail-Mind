import inspect

import pytest
from pydantic import ValidationError

from growth_suite import (
    MarketingCopyRequest,
    MarketingCampaignSaveRequest,
    generate_marketing_copy,
    list_marketing_campaigns,
    router,
    _growth_copy_fallback,
    _contains_restricted_marketing_content,
)


def test_marketing_copy_request_only_accepts_supported_campaign_options():
    request = MarketingCopyRequest(
        goal="new_product",
        language="te",
        ad_format="story",
        product_id=12,
        product_name="Fresh produce",
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
    assert "stock_quantity <= 0" in source
    assert "data.product_name" in source
    assert 'generated.get("headline")' in source
    assert 'generated.get("caption")' in source
    paths = {context.path for context in __import__("fastapi.routing", fromlist=["iter_route_contexts"]).iter_route_contexts(router.routes)}
    assert "/growth/marketing/generate" in paths


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


def test_campaign_save_contract_is_owner_scoped_and_upsertable():
    request = MarketingCampaignSaveRequest(
        campaign_id="campaign-1",
        goal="nearby",
        headline="Local grocery store",
        caption="Visit our shop today.",
        generation_source="manual",
    )
    assert request.campaign_id == "campaign-1"
    source = inspect.getsource(list_marketing_campaigns)
    save_source = inspect.getsource(__import__("growth_suite").save_marketing_campaign)
    assert "GrowthMarketingCampaign.shop_id == user_id" in source
    assert "GrowthMarketingCampaign.shop_id == user_id" in save_source
    assert 'campaign.status = "DRAFT"' in save_source
    paths = {context.path for context in __import__("fastapi.routing", fromlist=["iter_route_contexts"]).iter_route_contexts(router.routes)}
    assert "/growth/marketing/campaigns" in paths
    with pytest.raises(ValidationError):
        MarketingCampaignSaveRequest(
            campaign_id="campaign-2",
            goal="invalid",
            headline="Test",
            caption="Test",
        )



def test_restricted_marketing_categories_are_rejected():
    assert _contains_restricted_marketing_content("local shop: " + "be" + "er")
    assert _contains_restricted_marketing_content("e-" + "cigarette")
    assert _contains_restricted_marketing_content("sports-" + "betting")
    assert _contains_restricted_marketing_content("fire" + "arm")
    assert not _contains_restricted_marketing_content("fresh vegetables")
    assert not _contains_restricted_marketing_content("school stationery")
