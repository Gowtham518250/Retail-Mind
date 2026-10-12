from types import SimpleNamespace

from inventory import (
    _voice_billing_catalog_candidates,
    _voice_billing_normalize,
    router,
)


def _product(product_id: int, name: str, sku: str = ""):
    return SimpleNamespace(id=product_id, product_name=name, sku=sku)


def test_voice_billing_parse_endpoint_is_registered():
    assert any(
        getattr(route, "path", "") == "/api/inventory/voice-billing/parse"
        and "POST" in getattr(route, "methods", set())
        for route in router.routes
    )


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
