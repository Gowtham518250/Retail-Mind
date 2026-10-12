import asyncio
from fastapi import HTTPException

from query_retrival import (
    _clean_product_discovery_query,
    _product_discovery_distance_km,
    app,
    ask_query_product_discovery,
)


def test_product_discovery_endpoint_is_registered():
    assert any(
        getattr(route, "path", "") == "/askquery/product-discovery"
        and "POST" in getattr(route, "methods", set())
        for route in app.routes
    )


def test_product_prompt_cleaner_keeps_brand_and_pack_size():
    assert _clean_product_discovery_query("I need ghee around me") == "ghee"
    assert _clean_product_discovery_query("Looking for Amul cow ghee 1kg near me") == "Amul cow ghee 1kg"


def test_distance_helper_returns_zero_for_same_point():
    assert _product_discovery_distance_km(17.0, 78.0, 17.0, 78.0) == 0


def test_product_discovery_compares_online_prices_and_filters_local_distance(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-search-key")
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, *, params):
            assert url == "https://serpapi.com/search.json"
            calls.append(dict(params))
            if params["engine"] == "google_shopping":
                return FakeResponse({
                    "shopping_results": [
                        {
                            "title": "Cow Ghee 1L - Seller A",
                            "source": "Seller A",
                            "extracted_price": 620,
                            "price": "₹620",
                            "product_link": "https://example.com/a",
                            "rating": 4.5,
                            "reviews": 42,
                        },
                        {
                            "title": "Cow Ghee 1L - Seller B",
                            "source": "Seller B",
                            "extracted_price": 599.5,
                            "price": "₹599.50",
                            "product_link": "https://example.com/b",
                        },
                        {"title": "Unpriced listing"},
                    ]
                })
            assert params["engine"] == "google_maps"
            assert params["ll"] == "@17.0,78.0,14z"
            return FakeResponse({
                "local_results": [
                    {
                        "title": "Nearby Grocery",
                        "address": "Main Road",
                        "gps_coordinates": {"latitude": 17.001, "longitude": 78.001},
                        "rating": 4.2,
                        "phone": "+910000000000",
                    },
                    {
                        "title": "Far Grocery",
                        "address": "Outside radius",
                        "gps_coordinates": {"latitude": 17.6, "longitude": 78.6},
                    },
                    {
                        "title": "No coordinates",
                        "address": "Unknown distance",
                    },
                ]
            })

    monkeypatch.setattr("query_retrival.httpx.AsyncClient", lambda **kwargs: FakeClient())
    result = asyncio.run(
        ask_query_product_discovery(
            query="I need ghee",
            language_code="en",
            latitude=17.0,
            longitude=78.0,
            radius_km=10,
            user_id=7,
        )
    )

    assert len(calls) == 2
    assert result["product_discovery"]["product_query"] == "ghee"
    offers = result["product_discovery"]["online_offers"]
    assert [offer["source"] for offer in offers] == ["Seller B", "Seller A"]
    assert offers[0]["price"] == 599.5
    shops = result["product_discovery"]["nearby_shops"]
    assert [shop["name"] for shop in shops] == ["Nearby Grocery"]
    assert shops[0]["price"] is None
    assert "call" in shops[0]["price_note"].lower()
    assert "do not confirm" in result["answer"].lower()


def test_product_discovery_without_location_only_searches_online(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-search-key")
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"shopping_results": []}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, *, params):
            calls.append(params["engine"])
            return FakeResponse()

    monkeypatch.setattr("query_retrival.httpx.AsyncClient", lambda **kwargs: FakeClient())
    result = asyncio.run(
        ask_query_product_discovery(
            query="I need ghee",
            language_code="en",
            latitude=None,
            longitude=None,
            radius_km=10,
            user_id=7,
        )
    )

    assert calls == ["google_shopping"]
    assert result["product_discovery"]["location_available"] is False
    assert result["product_discovery"]["nearby_shops"] == []
    assert "allow location access" in result["answer"].lower()


def test_product_discovery_requires_provider_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)

    with __import__("pytest").raises(HTTPException) as err:
        asyncio.run(
            ask_query_product_discovery(
                query="I need ghee",
                language_code="en",
                latitude=None,
                longitude=None,
                radius_km=10,
                user_id=7,
            )
        )

    assert err.value.status_code == 503
    assert "SERPAPI_API_KEY" in err.value.detail
