from types import SimpleNamespace

from inventory import (
    _voice_billing_catalog_candidates,
    _voice_billing_normalize_spoken_scales,
    _voice_billing_whisper_language_hint,
    _voice_billing_whisper_prompt,
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



def test_whisper_language_hint_uses_selected_locale():
    assert _voice_billing_whisper_language_hint("te-IN") == "te"
    assert _voice_billing_whisper_language_hint("hi-IN") == "hi"
    assert _voice_billing_whisper_language_hint("en-IN") == "en"
    assert _voice_billing_whisper_language_hint("auto") is None
    assert _voice_billing_whisper_language_hint("unknown-LANG") is None


def test_whisper_prompt_uses_shop_catalog_vocabulary_without_duplicates():
    prompt = _voice_billing_whisper_prompt(
        "te-IN",
        ["Sona Masoori Rice", "Tata Salt", "Sona Masoori Rice", "", "Turmeric Powder"],
    )
    assert "రిటైల్ బిల్లింగ్" in prompt
    assert "Sona Masoori Rice" in prompt
    assert "Tata Salt" in prompt
    assert "Turmeric Powder" in prompt
    assert prompt.count("Sona Masoori Rice") == 1
