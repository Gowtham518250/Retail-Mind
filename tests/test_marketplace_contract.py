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


def test_shop_product_page_batches_flash_sale_lookups_by_category():
    import inspect

    from online_store import browse_shop_products

    source = inspect.getsource(browse_shop_products)
    assert "get_active_discounts(" in source
    assert "discounts_by_category.get(product.category, 0.0)" in source
    assert "get_active_discount(db, shop_id_int, p.category)" not in source


def test_product_image_column_has_an_idempotent_production_repair():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app_source = (root / "app.py").read_text(encoding="utf-8")
    migration_source = (root / "alembic" / "versions" / "026_product_image_url.py").read_text(encoding="utf-8")

    assert 'ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT' in app_source
    assert 'ADD COLUMN IF NOT EXISTS image_url TEXT' in migration_source
    assert 'DROP COLUMN IF EXISTS image_url' in migration_source


def test_customer_create_accepts_slash_and_non_slash_paths_without_redirect():
    from customers import router as customer_router

    create_paths = {
        route.path
        for route in customer_router.routes
        if "POST" in (getattr(route, "methods", None) or set())
    }
    assert "/api/customers" in create_paths
    assert "/api/customers/" in create_paths


def test_token_lifetimes_keep_short_access_and_seven_day_refresh():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    render_source = (root / "render.yaml").read_text(encoding="utf-8")
    security_source = (root / "security.py").read_text(encoding="utf-8")
    assert "key: ACCESS_TOKEN_EXPIRE_MINUTES\n        value: 30" in render_source
    assert "key: REFRESH_TOKEN_EXPIRE_DAYS\n        value: 7" in render_source
    assert "ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv(\"ACCESS_TOKEN_EXPIRE_MINUTES\", 30))" in security_source
