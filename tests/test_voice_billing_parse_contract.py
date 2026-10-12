from types import SimpleNamespace

from inventory import (
    _voice_billing_catalog_candidates,
    _voice_billing_normalize,
    router,
)


def _product(product_id: int, name: str, sku: str = ""):
    return SimpleNamespace(id=product_id, product_name=name, sku=sku)


def test_voice_billing_parse_endpoints_are_registered():
    paths = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in router.routes
    }
    assert ("/api/inventory/voice-billing/parse", frozenset({"POST"})) in paths
    assert ("/api/inventory/voice-billing/parse-audio", frozenset({"POST"})) in paths


def test_voice_billing_normalization_preserves_indian_script_and_numbers():
    assert _voice_billing_normalize("రెండు kg rice 50") == "రెండు kg rice 50"
    assert _voice_billing_normalize("  RICE,   50 ") == "rice 50"


def test_catalog_shortlisting_matches_transliterated_product_alias():
    products = [
        _product(index, f"Unrelated product {index}", f"SKU-{index}")
        for index in range(1, 110)
    ]
    expected = _product(999, "Sona Masoori Rice", "RICE-01")
    products.append(expected)

    candidates = _voice_billing_catalog_candidates(
        "రెండు kilo biyyam 50",
        products,
        limit=80,
    )

    assert len(candidates) <= 80
    assert any(product.id == expected.id for product in candidates)
    assert candidates[0].id == expected.id


def test_native_script_telugu_rice_shortlists_catalog_product():
    products = [
        _product(index, f"Unrelated household item {index}", f"SKU-{index}")
        for index in range(1, 110)
    ]
    expected = _product(999, "Sona Masoori Rice", "RICE-01")
    products.append(expected)

    candidates = _voice_billing_catalog_candidates(
        "రెండు కిలోల బియ్యం 50",
        products,
        limit=80,
    )

    assert candidates
    assert candidates[0].id == expected.id


def test_native_script_hindi_sugar_shortlists_catalog_product():
    products = [
        _product(index, f"Unrelated household item {index}", f"SKU-{index}")
        for index in range(1, 110)
    ]
    expected = _product(999, "White Sugar", "SUGAR-01")
    products.append(expected)

    candidates = _voice_billing_catalog_candidates(
        "दो किलो चीनी 60",
        products,
        limit=80,
    )

    assert candidates
    assert candidates[0].id == expected.id


def test_native_script_chicken_biryani_shortlists_english_catalog_item():
    products = [
        _product(index, f"Unrelated household item {index}", f"SKU-{index}")
        for index in range(1, 110)
    ]
    expected = _product(999, "Chicken Biryani", "FOOD-01")
    products.append(expected)

    candidates = _voice_billing_catalog_candidates(
        "చికెన్ బిర్యానీ 60 రూపాయలు",
        products,
        limit=80,
    )

    assert candidates
    assert candidates[0].id == expected.id


def test_small_catalog_is_not_artificially_trimmed():
    products = [
        _product(1, "Rice", "RICE"),
        _product(2, "Milk", "MILK"),
    ]
    candidates = _voice_billing_catalog_candidates("two rice", products, limit=80)
    assert [product.id for product in candidates] == [1, 2]


def test_large_catalog_does_not_return_random_candidates_for_unknown_product():
    products = [
        _product(index, f"Unrelated household item {index}", f"SKU-{index}")
        for index in range(1, 110)
    ]
    assert _voice_billing_catalog_candidates("dragonfruit 17", products, limit=80) == []


def _run_voice_billing_endpoint(monkeypatch, model_items, *, transcript="2 kg rice 50"):
    import asyncio
    import json
    import inventory as inventory_module

    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    product = SimpleNamespace(
        id=42,
        product_name="Sona Masoori Rice",
        sku="RICE-01",
        category="Grains",
        unit_price=50,
        current_stock=20,
        user_id=7,
        is_active=True,
    )

    class FakeQuery:
        def __init__(self):
            self.filters = []

        def filter(self, *criteria):
            self.filters.extend(criteria)
            return self

        def order_by(self, *criteria):
            return self

        def all(self):
            return [product]

    class FakeDb:
        def __init__(self):
            self.query_obj = FakeQuery()

        def query(self, model):
            assert model is inventory_module.Product
            return self.query_obj

    api_capture = {}
    response_content = json.dumps({
        "items": model_items,
        "needs_clarification": False,
        "clarification_question": "",
    })

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": response_content}}]}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            api_capture["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            api_capture["url"] = url
            api_capture["headers"] = headers
            api_capture["request"] = json
            return FakeResponse()

    monkeypatch.setattr(inventory_module.httpx, "AsyncClient", FakeAsyncClient)
    db = FakeDb()
    result = asyncio.run(inventory_module.parse_voice_billing(
        inventory_module.VoiceBillingParseRequest(
            transcript=transcript,
            language_code="en-IN",
        ),
        user_id=7,
        db=db,
    ))
    return result, api_capture, db


def test_groq_response_is_validated_against_catalog_ids(monkeypatch):
    result, api_capture, db = _run_voice_billing_endpoint(
        monkeypatch,
        [{
            "product_id": 42,
            "quantity": 2,
            "spoken_price_amount": 50,
            "spoken_price_kind": "unit",
            "confidence": 0.98,
        }],
    )

    assert result["success"] is True
    assert len(result["items"]) == 1
    assert result["items"][0]["product_id"] == 42
    assert result["items"][0]["product_name"] == "Sona Masoori Rice"
    assert result["items"][0]["quantity"] == 2.0
    assert result["items"][0]["unit_price"] == 50.0
    assert result["items"][0]["price_source"] == "spoken_unit"
    assert api_capture["request"]["response_format"] == {"type": "json_object"}
    assert api_capture["headers"]["Authorization"] == "Bearer unit-test-key"
    # The endpoint's SQLAlchemy query must scope inventory to the authenticated account.
    assert db.query_obj.filters
    assert any("user_id" in str(clause) for clause in db.query_obj.filters)


def test_groq_cannot_inject_product_id_not_in_shop_catalog(monkeypatch):
    result, _, _ = _run_voice_billing_endpoint(
        monkeypatch,
        [{
            "product_id": 999999,
            "quantity": 2,
            "spoken_price_amount": 50,
            "spoken_price_kind": "unit",
            "confidence": 0.99,
        }],
    )

    assert result["items"] == []
    assert result["success"] is False
    assert result["needs_clarification"] is True
    assert "confidently identify" in result["clarification_question"].lower()


def test_audio_endpoint_uses_groq_whisper_then_passes_transcript_to_parser(monkeypatch):
    import asyncio
    import io
    import inventory as inventory_module
    from fastapi import UploadFile
    from starlette.datastructures import Headers

    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"text": "2 kg rice 50", "language": "english"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, data, files):
            captured["url"] = url
            captured["headers"] = headers
            captured["data"] = data
            captured["files"] = files
            return FakeResponse()

    async def fake_parse(request, *, user_id, db):
        captured["transcript"] = request.transcript
        captured["language_code"] = request.language_code
        captured["user_id"] = user_id
        return {"success": True, "items": [], "needs_clarification": False}

    monkeypatch.setattr(inventory_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(inventory_module, "parse_voice_billing", fake_parse)

    audio = UploadFile(
        filename="voice-billing.wav",
        file=io.BytesIO(b"RIFF-fake-test-audio"),
        headers=Headers({"content-type": "audio/wav"}),
    )
    result = asyncio.run(
        inventory_module.parse_voice_billing_audio(
            audio=audio,
            language_code="auto",
            user_id=7,
            db=object(),
        )
    )

    assert captured["url"].endswith("/audio/transcriptions")
    assert captured["data"]["model"] == "whisper-large-v3"
    assert captured["headers"]["Authorization"] == "Bearer unit-test-key"
    assert captured["transcript"] == "2 kg rice 50"
    assert captured["language_code"] == "auto"
    assert captured["user_id"] == 7
    assert result["transcription_provider"] == "Groq"
    assert result["transcription_model"] == "whisper-large-v3"
    assert result["detected_language"] == "english"
