from datetime import date
import inspect
from types import SimpleNamespace

import pytest
from fastapi.routing import iter_route_contexts
from pydantic import ValidationError

from growth_suite import (
    MarketingAutomationSettingsRequest,
    MarketingCampaignApprovalRequest,
    MarketingCampaignSaveRequest,
    MarketingCopyRequest,
    _calculate_marketing_discount,
    _marketing_shop_snapshot,
    approve_marketing_campaign,
    get_marketing_automation_settings,
    reject_marketing_campaign,
    router,
    update_marketing_automation_settings,
)
from growth_marketing_automation import (
    enqueue_product_created_trigger,
    process_pending_marketing_triggers,
)


def test_discount_percent_uses_product_original_price_and_owner_offer():
    original, discounted, percent = _calculate_marketing_discount(
        1000, 800, today=date(2026, 11, 6)
    )
    assert original == 1000
    assert discounted == 800
    assert percent == 20


@pytest.mark.parametrize(
    "original,discounted",
    [
        (0, 0),
        (100, 100),
        (100, 101),
        (100, -1),
        (None, 10),
    ],
)
def test_invalid_discount_prices_are_rejected(original, discounted):
    with pytest.raises(ValueError):
        _calculate_marketing_discount(
            original, discounted, today=date(2026, 11, 6)
        )


def test_offer_dates_must_be_valid_and_not_expired():
    with pytest.raises(ValueError):
        _calculate_marketing_discount(
            100, 80, offer_valid_from=date(2026, 11, 10),
            offer_valid_until=date(2026, 11, 9), today=date(2026, 11, 6)
        )
    with pytest.raises(ValueError):
        _calculate_marketing_discount(
            100, 80, offer_valid_until=date(2026, 11, 5),
            today=date(2026, 11, 6)
        )
    with pytest.raises(ValueError):
        _calculate_marketing_discount(
            100, None, offer_valid_until=date(2026, 11, 10),
            today=date(2026, 11, 6)
        )


def test_shop_snapshot_keeps_address_contact_and_coordinates():
    profile = SimpleNamespace(
        address_line1="12 Market Road",
        address_line2="First Floor",
        address="",
        location="Main Market",
        city="Kadapa",
        state="Andhra Pradesh",
        postal_code="516001",
        latitude=14.4673,
        longitude=78.8242,
        phone="9000000000",
        website="https://example.invalid",
        logo_url="https://example.invalid/logo.png",
    )
    snapshot = _marketing_shop_snapshot(profile)
    assert "12 Market Road" in snapshot["shop_address"]
    assert "Kadapa" in snapshot["shop_address"]
    assert snapshot["shop_phone"] == "9000000000"
    assert snapshot["shop_latitude"] == 14.4673
    assert snapshot["shop_logo_url"].endswith("logo.png")


def test_marketing_generation_accepts_discount_and_validity_fields():
    request = MarketingCopyRequest(
        product_id=12,
        discount_price="800.00",
        offer_valid_until=date(2026, 12, 31),
    )
    assert request.discount_price == 800
    assert request.offer_valid_until == date(2026, 12, 31)


def test_marketing_save_requires_approval_submission_flag_and_supported_trigger_types():
    request = MarketingCampaignSaveRequest(
        campaign_id="test-campaign",
        goal="new_product",
        headline="New product",
        caption="Visit our shop",
        product_id=12,
        discount_price="800",
        submit_for_approval=True,
        trigger_type="owner_offer",
    )
    assert request.submit_for_approval is True
    assert request.trigger_type == "owner_offer"
    with pytest.raises(ValidationError):
        MarketingCampaignSaveRequest(
            campaign_id="bad-campaign",
            goal="new_product",
            headline="New product",
            caption="Visit our shop",
            trigger_type="publish_automatically",
        )


def test_automation_settings_have_safe_off_by_default_defaults_and_limits():
    settings = MarketingAutomationSettingsRequest()
    assert settings.enabled is False
    assert settings.new_products_enabled is True
    assert settings.weekly_enabled is False
    with pytest.raises(ValidationError):
        MarketingAutomationSettingsRequest(max_campaigns_per_week=100)


def test_approval_request_requires_expected_version():
    request = MarketingCampaignApprovalRequest(expected_version=2)
    assert request.expected_version == 2
    with pytest.raises(ValidationError):
        MarketingCampaignApprovalRequest(expected_version=0)


def test_marketing_automation_and_approval_routes_are_registered_and_owner_scoped():
    paths = {context.path for context in iter_route_contexts(router.routes)}
    assert "/growth/marketing/automation/settings" in paths
    assert "/growth/marketing/campaigns/{campaign_id}/approve" in paths
    assert "/growth/marketing/campaigns/{campaign_id}/reject" in paths

    approve_source = inspect.getsource(approve_marketing_campaign)
    reject_source = inspect.getsource(reject_marketing_campaign)
    settings_source = inspect.getsource(update_marketing_automation_settings)
    assert "GrowthMarketingCampaign.shop_id == user_id" in approve_source
    assert "GrowthMarketingCampaign.shop_id == user_id" in reject_source
    assert "expected_version" in approve_source
    assert "expected_version" in reject_source
    assert "GrowthMarketingAutomationSettings.shop_id == user_id" in settings_source


def test_new_product_trigger_is_opt_in_and_deduplicated_by_shop_product():
    source = inspect.getsource(enqueue_product_created_trigger)
    assert "GrowthMarketingAutomationSettings.enabled.is_(True)" in source
    assert "GrowthMarketingAutomationSettings.new_products_enabled.is_(True)" in source
    assert 'trigger_key = f"new-product:{int(product_id)}"' in source
    assert "existing" in source and "GrowthMarketingTrigger.trigger_key == trigger_key" in source


def test_automation_worker_only_creates_pending_approval_drafts():
    source = inspect.getsource(process_pending_marketing_triggers)
    assert 'status="PENDING_APPROVAL"' in source
    assert "GrowthMarketingAutomationSettings.enabled.is_(True)" in source
    assert "GrowthMarketingCampaign.shop_id == trigger.shop_id" in source
    assert "db.commit()" in source


def test_owner_approval_is_not_social_publishing():
    approve_source = inspect.getsource(approve_marketing_campaign)
    assert 'campaign.status = "APPROVED"' in approve_source
    assert "publish" not in approve_source.lower()
