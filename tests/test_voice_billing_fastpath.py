"""Deterministic voice-billing fast path: accepts only unambiguous utterances."""
import asyncio
from types import SimpleNamespace

import pytest

import inventory as inv
from voice_billing_fastpath import try_fast_parse
from test_voice_billing_parse_contract import _run_voice_billing_endpoint


def _p(pid, name, unit="pcs", price=10, sku=""):
    return SimpleNamespace(
        id=pid, product_name=name, sku=sku, category="", unit=unit,
        unit_price=price, current_stock=100, user_id=7, is_active=True,
    )


CATALOG = [
    _p(1, "Rice", "kg", 50, "RICE"),
    _p(2, "Lux Soap", "pcs", 35, "LUXS"),
    _p(3, "Milk", "l", 60, "MILK"),
    _p(4, "Egg", "pcs", 6, "EGG"),
    _p(5, "Sunflower Oil", "l", 140, "OIL"),
]


def parse(text, catalog=CATALOG):
    cands = inv._voice_billing_catalog_candidates(text, catalog, limit=80)
    return try_fast_parse(
        text, cands,
        normalize=inv._voice_billing_normalize,
        expand_tokens=inv._voice_billing_expanded_tokens,
    )


def items(text, catalog=CATALOG):
    out = parse(text, catalog)
    return None if out is None else out["items"]


def test_qty_unit_name_and_trailing_unit_price():
    (it,) = items("2 kg rice 50")
    assert (it["product_id"], it["quantity"], it["spoken_unit"]) == (1, "2", "kg")
    assert (it["spoken_price_kind"], it["spoken_price_amount"]) == ("unit", 50.0)


def test_multi_line_with_english_number_words_and_separators():
    out = items("add three soap and one litre milk, twenty five eggs")
    assert [(i["product_id"], i["quantity"], i["spoken_unit"]) for i in out] == [
        (2, "3", ""), (3, "1", "litre"), (4, "25", ""),
    ]


def test_no_quantity_defaults_to_one_and_no_price_means_none():
    (it,) = items("rice")
    assert it["quantity"] == "1" and it["spoken_price_kind"] == "none"


def test_decimal_quantity_and_plural_name():
    (it,) = items("1.5 kg rice")
    assert it["quantity"] == "1.5"
    (it,) = items("2 soaps")
    assert it["product_id"] == 2 and it["quantity"] == "2"


def test_leading_unit_quantity_after_name():
    (it,) = items("rice 3 kg")
    assert it["quantity"] == "3" and it["spoken_unit"] == "kg"


@pytest.mark.parametrize("text", [
    "2 kg rice for 100",            # 'for' makes price semantics ambiguous
    "two and a half kg rice",       # fractions are left to the LLM
    "half kg rice",
    "2 kg rice total 100",
    "2 dragon fruit 30",            # not in catalog: custom line handled by the LLM path
    "rendu kilo rice",              # Indian-language cue words
    "2 కిలో rice",                  # non-ASCII
    "2 kg soap",                    # kg vs a piece-priced product: needs confirmation
    "2 kg basmati rice",            # 'basmati' not explained by the catalog product
    "hello how are you",            # noise
    "2 3 rice 50",                  # two bare quantities
    "2 kg rice 50 60",              # two prices
    "rice 2 kg milk",               # name split around a quantity
    "",
])
def test_ambiguous_or_unexplained_utterances_fall_back_to_llm(text):
    assert items(text) is None


def test_ambiguous_pack_sizes_never_guess():
    catalog = CATALOG + [_p(10, "Lux Soap 100g"), _p(11, "Lux Soap 150g")]
    assert items("2 lux soap", [c for c in catalog if c.id not in (2,)]) is None


def test_product_with_pack_size_in_its_name_falls_back():
    catalog = [_p(20, "Atta 5kg", "pcs", 250)]
    assert items("2 atta", catalog) is None
    assert items("atta 5 kg", catalog) is None


def test_ambiguous_generic_name_with_two_catalog_matches_falls_back():
    catalog = [_p(30, "Basmati Rice", "kg", 90), _p(31, "Sona Masoori Rice", "kg", 60)]
    assert items("2 kg rice", catalog) is None
    # ...while a product literally named "Rice" is the exact match, as in the core resolver.
    assert items("2 kg rice", CATALOG + [_p(32, "Basmati Rice", "kg", 90)])[0]["product_id"] == 1


# ---- endpoint level -------------------------------------------------------

def test_endpoint_uses_no_llm_for_a_clear_utterance(monkeypatch):
    rice = _p(42, "Sona Masoori Rice", "kg", 50, "RICE-01")
    result, capture, _, _ = _run_voice_billing_endpoint(
        monkeypatch, [], transcript="2 kg rice 55", language_code="auto",
        catalog_products=[rice], fast_path=True,
    )
    assert capture["requests"] == []          # no translation, no extraction call
    assert result["provider"] == "deterministic"
    (item,) = result["items"]
    assert item["product_id"] == 42 and item["quantity"] == 2.0
    assert item["unit_price"] == 55.0 and item["price_source"] == "spoken_unit"
    assert item["quantity_grounded"] is True


def test_endpoint_converts_units_through_the_shared_pipeline(monkeypatch):
    rice = _p(42, "Sona Masoori Rice", "kg", 50, "RICE-01")
    result, capture, _, _ = _run_voice_billing_endpoint(
        monkeypatch, [], transcript="500 g rice", language_code="en-IN",
        catalog_products=[rice], fast_path=True,
    )
    assert capture["requests"] == []
    (item,) = result["items"]
    assert item["quantity"] == 0.5 and item["unit_converted"] is True
    assert item["unit_price"] == 50.0 and item["price_source"] == "catalog"


def test_endpoint_still_calls_llm_when_the_fast_path_declines(monkeypatch):
    rice = _p(42, "Sona Masoori Rice", "kg", 50, "RICE-01")
    result, capture, _, _ = _run_voice_billing_endpoint(
        monkeypatch,
        [{"product_id": None, "product_name_en": "Dragon Fruit", "quantity": 2,
          "spoken_price_amount": 30, "spoken_price_kind": "unit", "confidence": 0.98}],
        transcript="2 dragon fruit 30", language_code="auto",
        catalog_products=[rice], translated_text="2 dragon fruit 30", fast_path=True,
    )
    assert capture["requests"]                # fell back to the existing pipeline
    assert result["items"][0]["product_name"] == "Dragon Fruit"
    assert result["provider"] == "Groq"


def test_endpoint_skips_fast_path_for_explicit_indian_language(monkeypatch):
    rice = _p(42, "Sona Masoori Rice", "kg", 50, "RICE-01")
    _, capture, _, _ = _run_voice_billing_endpoint(
        monkeypatch,
        [{"product_id": 42, "quantity": 2, "spoken_unit": "kg",
          "spoken_price_kind": "none", "confidence": 0.98}],
        transcript="2 kg rice", language_code="te-IN",
        catalog_products=[rice], translated_text="2 kg rice", fast_path=True,
    )
    assert capture["requests"]


def test_kill_switch_disables_fast_path(monkeypatch):
    rice = _p(42, "Sona Masoori Rice", "kg", 50, "RICE-01")
    _, capture, _, _ = _run_voice_billing_endpoint(
        monkeypatch,
        [{"product_id": 42, "quantity": 2, "spoken_unit": "kg",
          "spoken_price_kind": "none", "confidence": 0.98}],
        transcript="2 kg rice", language_code="en-IN",
        catalog_products=[rice], fast_path=False,
    )
    assert capture["requests"]


@pytest.mark.parametrize("utterance", [
    "₹50 rice", "50 rupees rice", "rice ₹50", "rice 50 rupees", "2 kg rice ₹50",
])
def test_currency_markers_bind_to_the_amount_not_quantity(utterance):
    (item,) = items(utterance)
    assert item["quantity"] == ("2" if utterance.startswith("2 kg") else "1")
    assert item["spoken_price_kind"] == "unit"
    assert item["spoken_price_amount"] == 50.0


def test_quantity_and_trailing_price_follow_existing_pos_convention():
    (item,) = items("2 rice 50")
    assert item["quantity"] == "2"
    assert item["spoken_price_kind"] == "unit"
    assert item["spoken_price_amount"] == 50.0


def test_bare_number_after_product_without_grounded_quantity_is_ambiguous():
    assert items("rice 2") is None
    assert items("rice 50") is None
