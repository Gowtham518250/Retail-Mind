import inspect

import inventory
import growth_suite


def test_product_create_idempotency_never_returns_archived_product():
    source = inspect.getsource(inventory.create_product)
    assert "Product.is_active.is_(True)" in source
    assert "deleted/archived product must never be returned" in source


def test_bulk_import_does_not_reactivate_archived_sku_and_queues_marketing():
    source = inspect.getsource(inventory.bulk_import_products)
    assert "Product.is_active.is_(True)" in source
    assert "existing.is_active = True" not in source
    assert "enqueue_product_created_trigger(db, user_id, product.id)" in source


def test_generated_poster_has_owner_scoped_image_endpoint():
    paths = {route.path for route in growth_suite.router.routes}
    assert "/growth/marketing/campaigns/{campaign_id}/poster.svg" in paths
    source = inspect.getsource(growth_suite.get_marketing_campaign_poster)
    assert "GrowthMarketingCampaign.shop_id == user_id" in source
    assert 'media_type="image/svg+xml"' in source
