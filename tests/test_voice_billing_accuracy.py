from types import SimpleNamespace

from inventory import (
    _voice_billing_catalog_candidates,
    _voice_billing_normalize_spoken_scales,
)


def test_normalize_roman_telugu_and_native_telugu_hundreds():
    assert _voice_billing_normalize_spoken_scales("3 vandalu biyyam") == "300 biyyam"
    assert _voice_billing_normalize_spoken_scales("moodu vandalu biyyam") == "300 biyyam"
    assert _voice_billing_normalize_spoken_scales("మూడు వందలు బియ్యం") == "300 బియ్యం"


def test_normalize_spoken_hundred_plus_remainder():
    assert _voice_billing_normalize_spoken_scales("3 vandalu yabhai rupees") == "350 rupees"


def test_do_not_treat_ordinary_homophone_as_a_number():
    assert _voice_billing_normalize_spoken_scales("tree vandalu soap") == "tree vandalu soap"


def test_small_catalog_is_still_filtered_by_transcript_evidence():
    rice = SimpleNamespace(product_name="Rice", sku="")
    sugar = SimpleNamespace(product_name="Sugar", sku="")

    candidates = _voice_billing_catalog_candidates("rice 300", [rice, sugar], limit=80)

    assert candidates == [rice]
