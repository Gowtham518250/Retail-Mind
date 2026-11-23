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

def test_asr_alias_returns_all_matching_pack_candidates_for_generic_disambiguation():
    boost_bottle = SimpleNamespace(product_name="Boost", sku="")
    boost_jar = SimpleNamespace(product_name="Boost 500g", sku="")

    candidates = _voice_billing_catalog_candidates(
        "300 bubt", [boost_bottle, boost_jar]
    )
    assert set(candidates) == {boost_bottle, boost_jar}



def test_translation_and_extraction_token_budgets_scale_for_long_bills():
    from inventory import (
        _voice_billing_translation_token_budget,
        _voice_billing_extraction_token_budget,
    )

    short_text = "2 kg rice 50"
    long_text = " ".join([f"item{i} quantity 2 price 50" for i in range(25)])

    assert _voice_billing_translation_token_budget(short_text) == 220
    assert _voice_billing_translation_token_budget(long_text) > 220
    assert _voice_billing_extraction_token_budget(short_text) == 1100
    assert _voice_billing_extraction_token_budget(long_text) > 1100


def test_long_translated_bill_is_not_truncated_to_a_short_search_snippet(monkeypatch):
    import asyncio
    import json
    import inventory as inventory_module

    translated = " ; ".join(
        f"product {index} quantity 2 unit kg line total 100"
        for index in range(1, 26)
    )
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({"english_search_text": translated})
                    }
                }]
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            captured["max_tokens"] = json["max_tokens"]
            return FakeResponse()

    monkeypatch.setattr(inventory_module.httpx, "AsyncClient", FakeAsyncClient)
    result = asyncio.run(
        inventory_module._voice_billing_translate_search_query(
            " ".join(["two kg rice one hundred rupees"] * 25),
            "te-IN",
            "unit-test-key",
            "test-model",
        )
    )

    assert len(result) > 320
    assert result == translated
    assert captured["max_tokens"] > 220
