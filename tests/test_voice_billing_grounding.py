"""Units and prices reported by the extraction model must be grounded in what was said."""
from types import SimpleNamespace

import pytest

from test_voice_billing_parse_contract import _run_voice_billing_endpoint
from voice_billing_core import spoken_unit_is_grounded

RICE = SimpleNamespace(
    id=42, product_name="Sona Masoori Rice", sku="RICE-01", category="", unit="kg",
    unit_price=50, current_stock=20, user_id=7, is_active=True,
)


def _item(monkeypatch, model_item, transcript, language="en-IN"):
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch, [model_item], transcript=transcript, language_code=language,
        catalog_products=[RICE],
    )
    return result, (result["items"][0] if result["items"] else None)


def test_hallucinated_unit_does_not_scale_quantity(monkeypatch):
    result, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "g",
        "spoken_price_kind": "none", "confidence": 0.95}, "2 kg rice")
    # exactly one unit was said ("kg"), so the model's "g" is repaired, not trusted
    assert item["unit_converted"] is False and item["quantity"] == 2.0
    assert item["product_id"] == 42 and item["needs_confirmation"] is False


def test_unattributable_unit_keeps_quantity_unconverted_and_asks(monkeypatch):
    result, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "g",
        "spoken_price_kind": "none", "confidence": 0.95}, "2 rice")      # no unit spoken at all
    assert item["unit_converted"] is False and item["quantity"] == 2.0
    assert item["unit_grounded"] is False and item["needs_confirmation"] is True
    assert "unit not clearly heard" in result["clarification_question"]


@pytest.mark.parametrize("transcript,model_qty,model_unit,expected_qty", [
    ("500 g rice", 500, "g", 0.5),
    ("500g rice", 500, "g", 0.5),
    ("500 grams rice", 500, "gram", 0.5),
    ("2 kilos rice", 2, "kg", 2.0),
    ("2 kg rice", 2, "kg", 2.0),
])
def test_genuinely_spoken_units_still_convert(monkeypatch, transcript, model_qty, model_unit, expected_qty):
    _, item = _item(monkeypatch, {
        "product_id": 42, "quantity": model_qty, "spoken_unit": model_unit,
        "spoken_price_kind": "none", "confidence": 0.95}, transcript)
    assert item["quantity"] == expected_qty
    assert item["unit_grounded"] is True and item["needs_confirmation"] is False


def test_invented_price_falls_back_to_catalog_and_asks(monkeypatch):
    result, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "kg",
        "spoken_price_amount": 5000, "spoken_price_kind": "unit", "confidence": 0.95}, "2 kg rice 50")
    assert item["unit_price"] == 50.0 and item["price_source"] == "catalog"
    assert item["price_grounded"] is False and item["needs_confirmation"] is True
    assert "price not clearly heard" in result["clarification_question"]


def test_price_when_none_was_spoken_is_not_trusted(monkeypatch):
    _, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "kg",
        "spoken_price_amount": 75, "spoken_price_kind": "unit", "confidence": 0.95}, "2 kg rice")
    assert item["unit_price"] == 50.0 and item["price_grounded"] is False


@pytest.mark.parametrize("transcript,kind,amount,expected_unit_price", [
    ("2 kg rice 55", "unit", 55, 55.0),
    ("2 kg rice fifty five", "unit", 55, 55.0),
    ("2 kg rice for 110", "line_total", 110, 55.0),
    ("2 kg rice 52.5", "unit", 52.5, 52.5),
])
def test_spoken_prices_are_still_used(monkeypatch, transcript, kind, amount, expected_unit_price):
    _, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "kg",
        "spoken_price_amount": amount, "spoken_price_kind": kind, "confidence": 0.95}, transcript)
    assert item["unit_price"] == expected_unit_price
    assert item["price_grounded"] is True and item["needs_confirmation"] is False


def test_unit_grounding_helper_matches_dimension_and_size():
    assert spoken_unit_is_grounded("kg", ["2 kg rice"])
    assert spoken_unit_is_grounded("kg", ["2 kilos rice"])
    assert spoken_unit_is_grounded("g", ["500g rice"])
    assert not spoken_unit_is_grounded("g", ["2 kg rice"])      # same dimension, wrong size
    assert not spoken_unit_is_grounded("l", ["2 kg rice"])
    assert spoken_unit_is_grounded("mystery-unit", ["2 rice"])  # unknown units: convert_quantity decides


@pytest.mark.parametrize("transcript,qty,price", [
    ("1.5 kg rice 60", 1.5, 60),
    ("0.5 kg rice 60", 0.5, 60),
    ("2 kg rice 1,200", 2, 1200),
    ("2 kg rice 1,00,000", 2, 100000),
])
def test_decimal_quantities_and_comma_prices_are_grounded(monkeypatch, transcript, qty, price):
    _, item = _item(monkeypatch, {
        "product_id": 42, "quantity": qty, "spoken_unit": "kg",
        "spoken_price_amount": price, "spoken_price_kind": "unit", "confidence": 0.95}, transcript)
    assert item is not None, "a decimal quantity must not drop the line"
    assert item["quantity"] == qty and item["quantity_grounded"] is True
    assert item["unit_price"] == price and item["needs_confirmation"] is False


def test_normalizer_keeps_numbers_whole():
    import inventory as inv
    assert inv._voice_billing_normalize("2.5 kg rice. Then 1,200 rs!") == "2.5 kg rice then 1200 rs"
    assert inv._voice_billing_normalize("end.") == "end"


def test_fast_path_handles_decimals(monkeypatch):
    result, capture, _, _ = _run_voice_billing_endpoint(
        monkeypatch, [], transcript="1.5 kg rice 60", language_code="auto",
        catalog_products=[RICE], fast_path=True)
    assert capture["requests"] == []
    (item,) = result["items"]
    assert item["quantity"] == 1.5 and item["unit_price"] == 60.0

def test_price_from_another_product_line_is_not_accepted(monkeypatch):
    from types import SimpleNamespace

    rice = SimpleNamespace(
        id=42, product_name="Rice", sku="RICE", category="", unit="kg",
        unit_price=45, current_stock=20, user_id=7, is_active=True,
    )
    oil = SimpleNamespace(
        id=43, product_name="Oil", sku="OIL", category="", unit="l",
        unit_price=110, current_stock=20, user_id=7, is_active=True,
    )
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch,
        [
            {"product_id": 42, "product_name_en": "Rice", "quantity": 2,
             "spoken_unit": "kg", "spoken_price_amount": 120,
             "spoken_price_kind": "unit", "confidence": 0.95},
            {"product_id": 43, "product_name_en": "Oil", "quantity": 1,
             "spoken_unit": "litre", "spoken_price_amount": 50,
             "spoken_price_kind": "unit", "confidence": 0.95},
        ],
        transcript="2 kg rice 50 and 1 litre oil 120",
        catalog_products=[rice, oil],
    )
    rice_line, oil_line = result["items"]
    assert rice_line["unit_price"] == 45.0
    assert rice_line["price_source"] == "catalog"
    assert rice_line["price_grounded"] is False
    assert rice_line["needs_confirmation"] is True
    assert oil_line["unit_price"] == 110.0
    assert oil_line["price_source"] == "catalog"
    assert oil_line["price_grounded"] is False
    assert oil_line["needs_confirmation"] is True


def test_unit_from_another_product_line_does_not_scale_quantity(monkeypatch):
    from types import SimpleNamespace

    rice = SimpleNamespace(
        id=42, product_name="Rice", sku="RICE", category="", unit="kg",
        unit_price=45, current_stock=20, user_id=7, is_active=True,
    )
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch,
        [{
            "product_id": 42, "product_name_en": "Rice", "quantity": 2,
            "spoken_unit": "g", "spoken_price_kind": "none", "confidence": 0.95,
        }],
        transcript="2 kg rice and 1 g spice",
        catalog_products=[rice],
    )
    (item,) = result["items"]
    assert item["quantity"] == 2.0
    assert item["unit_converted"] is False
    assert item["unit_grounded"] is True
    assert item["needs_confirmation"] is False
