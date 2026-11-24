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
    # These legacy quantity/price tests target numeric grounding rather than
    # extraction. Give their mocked AI response the name the new contract requires.
    model_item = dict(model_item)
    model_item.setdefault("product_name_en", "Sona Masoori Rice")
    model_item.setdefault("product_name_local", "rice")
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


def test_ungrounded_spoken_price_never_falls_back_to_catalog(monkeypatch):
    result, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "kg",
        "spoken_price_amount": 5000, "spoken_price_kind": "unit", "confidence": 0.95}, "2 kg rice 50")
    assert item["unit_price"] == 0.0 and item["price_source"] == "missing"
    assert item["price_grounded"] is False and item["needs_confirmation"] is True
    assert "price not clearly heard" in result["clarification_question"]


def test_price_when_none_was_spoken_is_not_trusted(monkeypatch):
    _, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "kg",
        "spoken_price_amount": 75, "spoken_price_kind": "unit", "confidence": 0.95}, "2 kg rice")
    assert item["unit_price"] == 0.0 and item["price_source"] == "missing"
    assert item["price_grounded"] is False


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


def test_ai_extractor_handles_decimals_without_catalog_fastpath(monkeypatch):
    result, capture, _, _ = _run_voice_billing_endpoint(
        monkeypatch,
        [{"product_name_en": "Rice", "product_name_local": "rice",
          "quantity": 1.5, "spoken_unit": "kg", "spoken_price_amount": 60,
          "spoken_price_kind": "unit", "confidence": 0.99}],
        transcript="1.5 kg rice 60 per kg", language_code="auto",
        catalog_products=[RICE], fast_path=True)
    assert len(capture["requests"]) == 2  # translation + structured extraction
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
    assert rice_line["unit_price"] == 0.0
    assert rice_line["price_source"] == "missing"
    assert rice_line["price_grounded"] is False
    assert rice_line["needs_confirmation"] is True
    assert oil_line["unit_price"] == 0.0
    assert oil_line["price_source"] == "missing"
    assert oil_line["price_grounded"] is False
    assert oil_line["needs_confirmation"] is True


def test_unit_from_another_product_line_does_not_scale_quantity(monkeypatch):
    from types import SimpleNamespace

    rice = SimpleNamespace(
        id=42, product_name="Rice", sku="RICE", category="", unit="kg",
        unit_price=45, current_stock=20, user_id=7, is_active=True,
    )
    spice = SimpleNamespace(
        id=43, product_name="Spice", sku="SPICE", category="", unit="pcs",
        unit_price=10, current_stock=20, user_id=7, is_active=True,
    )
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch,
        [
            {"product_id": 42, "product_name_en": "Rice", "quantity": 2,
             "spoken_unit": "g", "spoken_price_kind": "none", "confidence": 0.95},
            {"product_id": 43, "product_name_en": "Spice", "quantity": 1,
             "spoken_unit": "g", "spoken_price_kind": "none", "confidence": 0.95},
        ],
        transcript="2 kg rice and 1 g spice",
        catalog_products=[rice, spice],
    )
    rice_line = result["items"][0]
    assert rice_line["quantity"] == 2.0
    assert rice_line["unit_converted"] is False
    assert rice_line["unit_grounded"] is True
    assert rice_line["needs_confirmation"] is False


def test_quantity_number_alone_cannot_be_used_as_spoken_price(monkeypatch):
    _, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "kg",
        "spoken_price_amount": 2, "spoken_price_kind": "unit", "confidence": 0.95,
    }, "2 kg rice")
    assert item["unit_price"] == 50.0
    assert item["price_source"] == "catalog"
    assert item["price_grounded"] is False
    assert item["needs_confirmation"] is True


def test_quantity_after_product_name_alone_cannot_be_used_as_spoken_price(monkeypatch):
    _, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "kg",
        "spoken_price_amount": 2, "spoken_price_kind": "unit", "confidence": 0.95,
    }, "rice 2 kg")
    assert item["unit_price"] == 50.0
    assert item["price_source"] == "catalog"
    assert item["price_grounded"] is False
    assert item["needs_confirmation"] is True


@pytest.mark.parametrize("wrong_quantity", [1, 60, 203])
def test_ungrounded_quantity_is_not_returned_as_a_billable_line(monkeypatch, wrong_quantity):
    result, item = _item(monkeypatch, {
        "product_id": 42, "quantity": wrong_quantity, "spoken_unit": "kg",
        "spoken_price_amount": 60, "spoken_price_kind": "line_total",
        "confidence": 0.99,
    }, "2 kg rice 60")

    # An ungrounded model quantity must be rejected, not merely flagged. Older
    # clients may ignore needs_confirmation and otherwise save the wrong amount.
    assert item is None
    assert result["items"] == []
    assert result["needs_clarification"] is True
    assert "quantity" in result["clarification_question"].lower()


def test_line_total_is_divided_by_the_verified_quantity_only(monkeypatch):
    _, item = _item(monkeypatch, {
        "product_id": 42, "quantity": 2, "spoken_unit": "kg",
        "spoken_price_amount": 120, "spoken_price_kind": "line_total",
        "confidence": 0.99,
    }, "2 kg rice 120")

    assert item["quantity_grounded"] is True
    assert item["price_grounded"] is True
    assert item["price_source"] == "spoken_line_total"
    assert item["unit_price"] == 60.0


def test_rupee_symbol_before_product_is_preserved_and_price_is_grounded(monkeypatch):
    _, item = _item(monkeypatch, {
        "product_id": 42,
        "product_name_en": "Rice",
        "quantity": 1,
        "spoken_price_amount": 50,
        "spoken_price_kind": "unit",
        "confidence": 0.95,
    }, "₹50 rice")

    assert item is not None
    assert item["unit_price"] == 50.0
    assert item["price_source"] == "spoken_unit"
    assert item["price_grounded"] is True
    assert item["needs_confirmation"] is False


def test_ambiguous_spoken_price_requires_confirmation_even_with_catalog_price(monkeypatch):
    result, item = _item(monkeypatch, {
        "product_id": 42,
        "product_name_en": "Rice",
        "quantity": 2,
        "spoken_unit": "kg",
        "spoken_price_amount": 50,
        "spoken_price_kind": "ambiguous",
        "confidence": 0.95,
    }, "2 kg rice 50")

    assert item is not None
    assert item["unit_price"] == 0.0
    assert item["price_source"] == "missing"
    assert item["price_needs_confirmation"] is True
    assert item["needs_confirmation"] is True
    assert result["needs_clarification"] is True
    assert "spoken price needs confirmation" in result["clarification_question"].lower()


def test_line_total_rounding_that_changes_total_requires_confirmation(monkeypatch):
    result, item = _item(monkeypatch, {
        "product_id": 42,
        "product_name_en": "Rice",
        "quantity": 3,
        "spoken_unit": "kg",
        "spoken_price_amount": 100,
        "spoken_price_kind": "line_total",
        "confidence": 0.95,
    }, "3 kg rice 100")

    assert item is not None
    assert item["price_source"] == "spoken_line_total"
    assert item["unit_price"] == 33.33
    assert item["price_needs_confirmation"] is True
    assert item["needs_confirmation"] is True
    assert "rounding" in item["price_warning"].lower()
    assert result["needs_clarification"] is True


def test_line_total_with_exact_per_unit_value_does_not_need_rounding_confirmation(monkeypatch):
    _, item = _item(monkeypatch, {
        "product_id": 42,
        "product_name_en": "Rice",
        "quantity": 2,
        "spoken_unit": "kg",
        "spoken_price_amount": 110,
        "spoken_price_kind": "line_total",
        "confidence": 0.95,
    }, "2 kg rice 110")

    assert item is not None
    assert item["unit_price"] == 55.0
    assert item["price_needs_confirmation"] is False
    assert item["needs_confirmation"] is False


def test_telugu_inflected_units_keep_quantities_on_their_own_product_lines(monkeypatch):
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch,
        [
            {
                "product_id": None,
                "product_name_en": "Chicken",
                "product_name_local": "చికెన్",
                "quantity": 2,
                "spoken_unit": "kg",
                "spoken_price_amount": 300,
                "spoken_price_kind": "line_total",
                "confidence": 0.96,
            },
            {
                "product_id": None,
                "product_name_en": "Mutton",
                "product_name_local": "మటన్",
                "quantity": 5,
                "spoken_unit": "kg",
                "spoken_price_amount": 600,
                "spoken_price_kind": "line_total",
                "confidence": 0.96,
            },
        ],
        transcript="2 కేజీల చికెన్ 300, 5 కేజీల మటన్ 600",
        language_code="te-IN",
        catalog_products=[],
        translated_text="2 kg chicken 300; 5 kg mutton 600",
    )

    assert result["needs_clarification"] is False
    assert [item["product_name"] for item in result["items"]] == ["Chicken", "Mutton"]
    assert [item["quantity"] for item in result["items"]] == [2.0, 5.0]
    assert [item["quantity_grounded"] for item in result["items"]] == [True, True]
    assert [item["price_grounded"] for item in result["items"]] == [True, True]
    assert [item["unit_price"] for item in result["items"]] == [150.0, 120.0]
    assert [item["price_source"] for item in result["items"]] == [
        "spoken_line_total",
        "spoken_line_total",
    ]
    assert all(item["needs_confirmation"] is False for item in result["items"])



def test_telugu_multi_item_extraction_ignores_wrong_catalog_prices(monkeypatch):
    from types import SimpleNamespace

    catalog = [
        SimpleNamespace(id=11, product_name="Coffee", sku="COFFEE", category="",
                        unit="pcs", unit_price=15, current_stock=20, user_id=7, is_active=True),
        SimpleNamespace(id=12, product_name="Idli", sku="IDLI", category="",
                        unit="pcs", unit_price=0, current_stock=20, user_id=7, is_active=True),
        SimpleNamespace(id=13, product_name="Chutney", sku="CHUTNEY", category="",
                        unit="pcs", unit_price=0, current_stock=20, user_id=7, is_active=True),
        SimpleNamespace(id=14, product_name="Potato", sku="POTATO", category="",
                        unit="pcs", unit_price=11, current_stock=20, user_id=7, is_active=True),
    ]
    transcript = (
        "5 కేజీల మటన్ 60, ఒకటి 20, ఒక కాఫీ 30, ఒక ఇడ్లీ 5, "
        "ఒక చట్నీ 10 మరియు ఒక బంగాళదుంప 70"
    )
    result, capture, _, _ = _run_voice_billing_endpoint(
        monkeypatch,
        [
            {"product_name_en": "Mutton", "product_name_local": "మటన్",
             "quantity": 5, "spoken_unit": "kg", "spoken_price_amount": 60,
             "spoken_price_kind": "line_total", "confidence": 0.99},
            {"product_name_en": "Coffee", "product_name_local": "కాఫీ",
             "quantity": 1, "spoken_unit": "", "spoken_price_amount": 30,
             "spoken_price_kind": "unit", "confidence": 0.99},
            {"product_name_en": "Idli", "product_name_local": "ఇడ్లీ",
             "quantity": 1, "spoken_unit": "", "spoken_price_amount": 5,
             "spoken_price_kind": "unit", "confidence": 0.99},
            {"product_name_en": "Chutney", "product_name_local": "చట్నీ",
             "quantity": 1, "spoken_unit": "", "spoken_price_amount": 10,
             "spoken_price_kind": "unit", "confidence": 0.99},
            {"product_name_en": "Potato", "product_name_local": "బంగాళదుంప",
             "quantity": 1, "spoken_unit": "", "spoken_price_amount": 70,
             "spoken_price_kind": "unit", "confidence": 0.99},
        ],
        transcript=transcript,
        language_code="te-IN",
        catalog_products=catalog,
        translated_text="5 kg mutton 60; 1 item 20; 1 coffee 30; 1 idli 5; 1 chutney 10; 1 potato 70",
        needs_clarification=True,
        clarification_question="One amount had no product name. Please identify that item.",
    )
    prompt = capture["request"]["messages"][1]["content"]
    assert '"product_id"' not in prompt
    assert "Authenticated shop catalog candidates" not in prompt
    assert '"product_id":11' not in prompt
    assert result["needs_clarification"] is True  # unnamed 'one 20' is never invented
    assert [item["product_name"] for item in result["items"]] == [
        "Mutton", "Coffee", "Idli", "Chutney", "Potato"
    ], result
    assert [item["quantity"] for item in result["items"]] == [5.0, 1.0, 1.0, 1.0, 1.0]
    assert [item["unit_price"] for item in result["items"]] == [12.0, 30.0, 5.0, 10.0, 70.0]
    assert [item["price_source"] for item in result["items"]] == [
        "spoken_line_total", "spoken_unit", "spoken_unit", "spoken_unit", "spoken_unit"
    ]
    assert result["items"][0]["product_id"] is None
    assert all(item["price_grounded"] is True for item in result["items"])

def test_delimited_count_based_products_keep_quantities_separate_without_units(monkeypatch):
    result, *_ = _run_voice_billing_endpoint(
        monkeypatch,
        [
            {
                "product_id": None,
                "product_name_en": "Soap",
                "product_name_local": "సబ్బు",
                "quantity": 3,
                "spoken_unit": "",
                "spoken_price_amount": 30,
                "spoken_price_kind": "unit",
                "confidence": 0.96,
            },
            {
                "product_id": None,
                "product_name_en": "Tea",
                "product_name_local": "టీ",
                "quantity": 5,
                "spoken_unit": "",
                "spoken_price_amount": 20,
                "spoken_price_kind": "unit",
                "confidence": 0.96,
            },
        ],
        transcript="3 సబ్బు 30, 5 టీ 20",
        language_code="te-IN",
        catalog_products=[],
        translated_text="3 soap 30; 5 tea 20",
    )

    assert result["needs_clarification"] is False, result
    assert [item["product_name"] for item in result["items"]] == ["Soap", "Tea"]
    assert [item["quantity"] for item in result["items"]] == [3.0, 5.0]
    assert [item["quantity_grounded"] for item in result["items"]] == [True, True]
    assert [item["unit_price"] for item in result["items"]] == [30.0, 20.0]
    assert all(item["needs_confirmation"] is False for item in result["items"])
