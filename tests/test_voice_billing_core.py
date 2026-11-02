"""Endpoint-level regression tests for ambiguity, unit conversion and quantity grounding."""
from decimal import Decimal
from types import SimpleNamespace

from test_voice_billing_parse_contract import _run_voice_billing_endpoint
from voice_billing_core import convert_quantity, quantity_is_grounded
from inventory import _VOICE_BILLING_NUMBER_WORDS, _VOICE_BILLING_SCALE_WORDS


def _p(pid, name, unit="pcs", price=40, stock=50):
    return SimpleNamespace(id=pid, product_name=name, sku="", category="", unit=unit,
                           unit_price=price, current_stock=stock, user_id=7, is_active=True)


def _item(name, qty, unit="", pid=None, **extra):
    base = {"product_id": pid, "product_name_en": name, "product_name_local": "", "quantity": qty,
            "spoken_unit": unit, "spoken_price_kind": "none", "confidence": 0.95}
    base.update(extra)
    return base


def test_ambiguous_pack_sizes_are_not_silently_picked(monkeypatch):
    catalog = [_p(1, "Lux Soap 100g"), _p(2, "Lux Soap 150g")]
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch, [_item("Lux Soap", 2, pid=1)], transcript="2 lux soap", catalog_products=catalog)
    item = result["items"][0]
    assert item["catalog_matched"] is False and item["product_id"] is None
    assert {c["product_id"] for c in item["ambiguous_candidates"]} == {1, 2}
    assert item["needs_confirmation"] and result["needs_clarification"]


def test_spoken_pack_size_disambiguates(monkeypatch):
    catalog = [_p(1, "Lux Soap 100g"), _p(2, "Lux Soap 150g")]
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch, [_item("Lux Soap 150g", 2, pid=2)], transcript="2 lux soap 150g", catalog_products=catalog)
    assert result["items"][0]["product_id"] == 2


def test_grams_are_converted_to_the_catalog_unit(monkeypatch):
    catalog = [_p(5, "Sugar", unit="kg", price=44)]
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch, [_item("Sugar", 500, "g", pid=5)], transcript="500 grams sugar", catalog_products=catalog)
    item = result["items"][0]
    assert item["quantity"] == 0.5 and item["unit_converted"] is True and item["spoken_quantity"] == 500
    assert item["unit_price"] == 44.0


def test_incompatible_unit_is_flagged_not_guessed(monkeypatch):
    catalog = [_p(6, "Fortune Oil", unit="l", price=150)]
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch, [_item("Fortune Oil", 2, "kg", pid=6)], transcript="2 kg fortune oil", catalog_products=catalog)
    item = result["items"][0]
    assert item["unit_mismatch"] is True and item["needs_confirmation"] is True
    assert item["product_id"] is None  # old clients must not deduct stock on unit mismatch


def test_quantity_the_speaker_never_said_is_flagged(monkeypatch):
    catalog = [_p(7, "Dettol Soap")]
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch, [_item("Dettol Soap", 8, pid=7)], transcript="3 dettol soap", catalog_products=catalog)
    item = result["items"][0]
    assert item["quantity_grounded"] is False and item["needs_confirmation"] is True


def test_multi_item_bill_matches_each_line_to_its_own_product(monkeypatch):
    catalog = [_p(1, "Sona Masoori Rice", "kg", 50), _p(2, "Sunflower Oil", "l", 140)]
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch,
        [_item("Rice", 2, "kg", pid=1), _item("Sunflower Oil", 1, "l", pid=2)],
        transcript="2 kg rice and 1 litre sunflower oil", catalog_products=catalog)
    assert [i["product_id"] for i in result["items"]] == [1, 2]


def test_local_product_name_newlines_are_cleaned(monkeypatch):
    catalog = [_p(1, "Sona Masoori Rice", "kg", 50)]
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch, [_item("Rice", 2, "kg", pid=1, product_name_local="బియ్యం\nరైస్")],
        transcript="2 kg rice", catalog_products=catalog)
    assert "\n" not in result["items"][0]["product_name_local"]


def test_unit_conversion_is_decimal_exact():
    r = convert_quantity(Decimal("750"), "g", "kg")
    assert r.converted and r.quantity == Decimal("0.750")
    assert convert_quantity(Decimal("1"), "dozen", "pcs").quantity == Decimal("12")
    assert convert_quantity(Decimal("2"), "kg", "l").incompatible
    assert convert_quantity(Decimal("2"), "box", "pcs").incompatible




def test_quantity_does_not_infer_dozen_from_an_unrelated_number():
    assert not quantity_is_grounded(
        Decimal("24"), ["2 kg rice"], _VOICE_BILLING_NUMBER_WORDS, _VOICE_BILLING_SCALE_WORDS
    )
    assert quantity_is_grounded(
        Decimal("24"), ["2 dozen eggs"], _VOICE_BILLING_NUMBER_WORDS, _VOICE_BILLING_SCALE_WORDS
    )
