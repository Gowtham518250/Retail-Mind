from types import SimpleNamespace

from inventory import (
    _voice_billing_catalog_candidates,
    _voice_billing_normalize_spoken_scales,
    _voice_billing_product_has_evidence,
    _voice_billing_should_translate,
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


def test_roman_telugu_scale_word_triggers_translation_when_asr_says_english():
    # Whisper can report English for Romanized speech; "vandalu" must not be
    # mistaken for an English word and sent directly to product matching.
    assert _voice_billing_should_translate("3 vandalu bubt", "en") is True
    assert _voice_billing_should_translate("moodu vandalu biyyam", "english") is True


def test_plain_english_scale_phrase_does_not_force_translation():
    assert _voice_billing_should_translate("three hundred soap", "en") is False


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

def test_bubt_asr_variant_matches_boost_only_when_boost_is_in_catalog():
    boost = SimpleNamespace(product_name="Boost", sku="")
    butter = SimpleNamespace(product_name="Butter", sku="")

    assert _voice_billing_catalog_candidates("300 bubt", [boost]) == [boost]
    assert _voice_billing_product_has_evidence("300 bubt", boost) is True
    assert _voice_billing_product_has_evidence("300 bubt", butter) is False


def test_boost_asr_alias_does_not_turn_unrelated_words_into_catalog_matches():
    boost = SimpleNamespace(product_name="Boost", sku="")
    soap = SimpleNamespace(product_name="Soap", sku="")

    assert _voice_billing_catalog_candidates("300 soap", [boost]) == []
    assert _voice_billing_product_has_evidence("300 soap", boost) is False
    assert _voice_billing_product_has_evidence("300 bubt", soap) is False

def test_bubt_alias_is_withheld_when_multiple_boost_pack_sizes_exist():
    boost_bottle = SimpleNamespace(product_name="Boost", sku="")
    boost_jar = SimpleNamespace(product_name="Boost 500g", sku="")

    assert _voice_billing_catalog_candidates(
        "300 bubt", [boost_bottle, boost_jar]
    ) == []

