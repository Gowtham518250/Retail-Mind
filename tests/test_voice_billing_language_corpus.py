"""Per-language accuracy gate for deterministic voice-billing stages.

This corpus checks deterministic normalization and catalog alias evidence. It
does not measure the external transcription/translation model's real-world
accuracy; extend it with reviewed recordings and expected transcripts.
"""
from types import SimpleNamespace

import pytest

from inventory import (
    _voice_billing_catalog_candidates,
    _voice_billing_normalize,
    _voice_billing_normalize_spoken_scales,
    _voice_billing_repair_asr,
)

CORPUS = [
    ("te", "మూడు వందలు బియ్యం", "300 బియ్యం"),
    ("te", "ఇండు కిలో పంచేదారా ఆరవే రూపాయలు", "రెండు కిలో పంచదార అరవై రూపాయలు"),
    ("te", "ఒక బిరియాని ఆయ్దు ఉందలు", "ఒక బిరియాని 500"),
    ("te", "ఒక బిరియాని రేణు ఉందలు", "ఒక బిరియాని 200"),
    ("te", "రేణు కిలో", "రేణు కిలో"),
    ("hi", "दो सौ चावल", "200 चावल"),
    ("hi", "पाँच हज़ार चीनी", "5000 चीनी"),
    ("hi", "तीन सौ पचास रुपये", "350 रुपये"),
    ("ta", "இரண்டு நூறு அரிசி", "200 அரிசி"),
    ("ta", "ஐந்து ஆயிரம் எண்ணெய்", "5000 எண்ணெய்"),
    ("kn", "ಮೂರು ನೂರು ಅಕ್ಕಿ", "300 ಅಕ್ಕಿ"),
    ("kn", "ಎರಡು ಸಾವಿರ ಸಕ್ಕರೆ", "2000 ಸಕ್ಕರೆ"),
    ("ml", "ഏഴ് നൂറ് അരി", "700 അരി"),
    ("ml", "രണ്ട് ആയിരം പഞ്ചസാര", "2000 പഞ്ചസാര"),
    ("mr", "पाच शे तांदूळ", "500 तांदूळ"),
    ("mr", "दोन हजार साखर", "2000 साखर"),
    ("bn", "পাঁচ শো চাল", "500 চাল"),
    ("bn", "তিন হাজার চিনি", "3000 চিনি"),
    ("gu", "ત્રણ સો ચોખા", "300 ચોખા"),
    ("gu", "બે હજાર ખાંડ", "2000 ખાંડ"),
    ("pa", "ਦੋ ਸੌ ਚੌਲ", "200 ਚੌਲ"),
    ("pa", "ਤਿੰਨ ਹਜ਼ਾਰ ਖੰਡ", "3000 ਖੰਡ"),
    ("en", "three hundred soap", "300 soap"),
]


@pytest.mark.parametrize("language,utterance,expected", CORPUS)
def test_multilingual_number_and_asr_normalization(language, utterance, expected):
    assert _voice_billing_normalize_spoken_scales(utterance) == expected


def test_all_current_deterministic_corpus_cases_match_expected_output():
    # This is a regression corpus, not a statistical/live microphone accuracy claim.
    for language, utterance, expected in CORPUS:
        assert _voice_billing_normalize_spoken_scales(utterance) == expected, language


@pytest.mark.parametrize(
    "utterance,expected_name",
    [
        ("బిరియాని 500", "Chicken Biryani"),
        ("పంచేదారా అరవై", "Sugar"),
        ("मटन 300", "Mutton Curry"),
        ("முட்டை 6", "Egg"),
    ],
)
def test_regional_and_misheard_names_find_catalogue_items(utterance, expected_name):
    repaired = " ".join(_voice_billing_repair_asr(_voice_billing_normalize(utterance).split()))
    products = [
        SimpleNamespace(product_name=name, sku="")
        for name in ("Chicken Biryani", "Sugar", "Mutton Curry", "Egg", "Soap")
    ]
    candidates = _voice_billing_catalog_candidates(repaired, products)
    assert expected_name in [product.product_name for product in candidates]
