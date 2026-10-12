import asyncio
from types import SimpleNamespace

from purchase_orders import (
    _make_reorder_suggestion,
    _search_online_supplier_prices,
    router,
)


def _product(**overrides):
    values = {
        "id": 17,
        "product_name": "Sona Masoori Rice 5kg",
        "sku": "RICE-5KG",
        "category": "Grocery",
        "current_stock": 3,
        "min_stock": 10,
        "reorder_level": 20,
        "max_stock": 100,
        "purchase_price": 250,
        "unit_price": 310,
        "is_active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_reorder_recommendation_route_is_registered():
    assert any(
        getattr(route, "path", "") == "/purchase-orders/reorder-recommendations"
        and "GET" in getattr(route, "methods", set())
        for route in router.routes
    )


def test_critical_stock_suggestion_uses_configured_threshold():
    suggestion = _make_reorder_suggestion(_product(current_stock=0))

    assert suggestion["product_id"] == 17
    assert suggestion["urgency"] == "CRITICAL"
    assert suggestion["suggested_reorder_qty"] == 40
    assert suggestion["recorded_purchase_price"] == 250.0
    assert suggestion["online_offers"] == []


def test_low_stock_suggestion_uses_shop_product_settings():
    suggestion = _make_reorder_suggestion(
        _product(current_stock=10, min_stock=8, reorder_level=20, max_stock=50)
    )

    assert suggestion["urgency"] == "REORDER"
    assert suggestion["target_stock"] == 40
    assert suggestion["suggested_reorder_qty"] == 30


def test_online_price_lookup_sorts_real_provider_offers(monkeypatch):
    import json

    monkeypatch.setenv("SERPAPI_API_KEY", "test-provider-key")
    monkeypatch.delenv("SERPAPI_KEY", raising=False)

    payload = {
        "shopping_results": [
            {
                "title": "Rice 5kg seller B",
                "source": "Seller B",
                "extracted_price": 265,
                "price": "₹265",
                "product_link": "https://example.com/b",
                "rating": 4.2,
                "reviews": 20,
            },
            {
                "title": "Rice 5kg seller A",
                "source": "Seller A",
                "extracted_price": 249.5,
                "price": "₹249.50",
                "product_link": "https://example.com/a",
            },
            {"title": "Unpriced listing", "source": "Seller C"},
        ]
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        async def get(self, url, *, params):
            assert url == "https://serpapi.com/search.json"
            assert params["engine"] == "google_shopping"
            assert params["gl"] == "in"
            assert params["api_key"] == "test-provider-key"
            return FakeResponse()

    result = asyncio.run(
        _search_online_supplier_prices(
            FakeClient(), "Rice 5kg contract-test", "Grocery"
        )
    )

    assert result["configured"] is True
    assert [offer["source"] for offer in result["offers"]] == ["Seller A", "Seller B"]
    assert result["offers"][0]["price"] == 249.5
    assert result["offers"][0]["currency"] == "INR"


def test_online_price_lookup_reports_missing_provider_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)

    class NeverCalledClient:
        async def get(self, *args, **kwargs):
            raise AssertionError("Provider should not be called without an API key")

    result = asyncio.run(
        _search_online_supplier_prices(
            NeverCalledClient(), "No API key contract-test", "Grocery"
        )
    )

    assert result["configured"] is False
    assert result["offers"] == []
    assert "SERPAPI_API_KEY" in result["message"]
