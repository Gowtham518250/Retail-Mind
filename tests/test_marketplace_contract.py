import inspect

from online_store import OwnerOrderAction, ai_shopping_recommendations, marketplace_search, router


def test_customer_marketplace_contract_is_online_only_and_stock_aware():
    source = inspect.getsource(marketplace_search)
    assert "ShopProfile.is_online_store_enabled == True" in source
    assert "Product.current_stock > 0" in source


def test_customer_ai_recommendation_searches_enabled_shops_and_in_stock_items():
    source = inspect.getsource(ai_shopping_recommendations)
    assert "ShopProfile.is_online_store_enabled == True" in source
    assert "Product.current_stock > 0" in source


def test_delivery_otp_contract_requires_customer_otp_for_delivery_action():
    assert "customer_otp" in OwnerOrderAction.model_fields

    routes = {getattr(route, "path", "") for route in router.routes}
    assert "/store/owner/orders/{order_id}/delivery-otp" in routes
    assert "/store/owner/orders/{order_id}/action" in routes


def test_customer_marketplace_can_find_shops_by_category_metadata():
    import inspect

    source = inspect.getsource(marketplace_search)
    assert "ShopProfile.shop_type.ilike(like)" in source
    assert "ShopProfile.shop_categories.ilike(like)" in source


def test_product_image_column_has_an_idempotent_production_repair():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app_source = (root / "app.py").read_text(encoding="utf-8")
    migration_source = (root / "alembic" / "versions" / "026_product_image_url.py").read_text(encoding="utf-8")

    assert 'ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT' in app_source
    assert 'ADD COLUMN IF NOT EXISTS image_url TEXT' in migration_source
    assert 'DROP COLUMN IF EXISTS image_url' in migration_source
