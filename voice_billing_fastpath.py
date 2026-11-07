"""Deterministic fast path for clear voice-billing utterances.

Most counter utterances are short and unambiguous ("2 kg rice 50", "add 3 soap
and 1 litre milk").  For those, two Groq round trips (translate + extract) add
seconds of latency and a small chance of model error without adding value.

This module parses such utterances without any network call.  It is
*conservative by construction*: it returns ``None`` (meaning "use the existing
LLM pipeline") unless EVERY one of these holds:

* the text is plain ASCII English with no Indian-language cue words,
* every segment has exactly one product name span, at most one unit-bound
  quantity and at most one price, in an unambiguous position,
* every product word was explained by ONE catalog product (no ties, no custom
  items, no pack-size names, no incompatible/unknown units),
* every line resolves to the same product when judged against the whole
  utterance (the exact check the downstream pipeline performs).

On success it returns the same ``{"items": [...]}`` shape the LLM produces, so
the unchanged downstream safety net (catalog re-resolution, unit conversion,
quantity grounding, price rules) still validates every line.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional

from voice_billing_core import canonical_unit, convert_quantity, resolve_catalog_product, size_tokens, stem_token

MAX_TRANSCRIPT_CHARS = 400
MAX_SEGMENTS = 8

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SEPARATORS = {",", "and", "then", "plus", "also", "next"}
_FILLERS = {"add", "please", "give", "me", "i", "want", "need", "a", "an", "the", "of", "bill", "to"}
_PRICE_MARKERS = {"rs", "rupee", "rupees", "inr", "₹", "at", "@", "each", "per"}
# Words that make price/quantity semantics ambiguous: leave them to the LLM.
_BAIL_WORDS = {
    "total", "for", "half", "quarter", "dozen", "dozens", "doz", "hundred",
    "thousand", "minus", "less", "discount", "remove", "cancel", "delete",
    "return", "credit", "udhar", "khata", "paid", "pay",
}
# "no" is the English word far more often than the "no." count unit.
_NOT_UNITS = {"no", "number", "numbers", "item", "items", "unit", "units"}

_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|[a-z]+|[,@₹]")


def _is_unit(token: str) -> bool:
    return token not in _NOT_UNITS and canonical_unit(token) is not None


def _tokenize(text: str) -> Optional[list[str]]:
    text = unicodedata.normalize("NFKC", text or "").casefold().strip()
    if not text or len(text) > MAX_TRANSCRIPT_CHARS:
        return None
    if any(ord(ch) > 127 and ch != "₹" for ch in text):
        return None
    if re.search(r"\d,\d", text):  # "1,000" would be torn apart by the comma separator
        return None
    return _TOKEN_RE.findall(text)


def _merge_number_words(tokens: list[str]) -> list[str]:
    """Turn English number words into digit tokens ("twenty five" -> "25")."""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _TENS:
            value = _TENS[tok]
            if i + 1 < len(tokens) and tokens[i + 1] in _ONES and 1 <= _ONES[tokens[i + 1]] <= 9:
                value += _ONES[tokens[i + 1]]
                i += 1
            out.append(str(value))
        elif tok in _ONES:
            out.append(str(_ONES[tok]))
        else:
            out.append(tok)
        i += 1
    return out


def _split_segments(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for tok in tokens:
        if tok in _SEPARATORS:
            if segments[-1]:
                segments.append([])
        else:
            segments[-1].append(tok)
    return [seg for seg in segments if seg]


def _is_number(token: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", token))


def _parse_segment(segment: list[str]) -> Optional[dict]:
    """Split one segment into name, quantity and price only when their roles are clear."""
    if any(tok in _BAIL_WORDS for tok in segment) or "per" in segment:
        return None

    # A currency/price marker must be attached to exactly one adjacent amount.
    # This prevents "₹50 rice" and "50 rupees rice" from becoming quantity=50.
    price_indices: set[int] = set()
    marker_indices: set[int] = set()
    currency_markers = {"rs", "rupee", "rupees", "inr", "₹"}
    positional_markers = {"at", "@", "each"}
    for idx, tok in enumerate(segment):
        if tok in currency_markers or tok in positional_markers:
            left_is_number = idx > 0 and _is_number(segment[idx - 1])
            right_is_number = idx + 1 < len(segment) and _is_number(segment[idx + 1])
            if left_is_number == right_is_number:
                return None
            price_indices.add(idx - 1 if left_is_number else idx + 1)
            marker_indices.add(idx)
    if len(price_indices) > 1:
        return None

    quantity: Optional[str] = None
    spoken_unit = ""
    price: Optional[str] = None
    name: list[str] = []
    name_started = False
    name_ended = False
    pending_bare: list[tuple[str, bool]] = []

    i = 0
    while i < len(segment):
        tok = segment[i]
        nxt = segment[i + 1] if i + 1 < len(segment) else None
        if i in marker_indices:
            i += 1
            continue
        if i in price_indices:
            if price is not None:
                return None
            price = tok
            if name_started:
                name_ended = True
            i += 1
            continue
        if _is_number(tok):
            if nxt is not None and _is_unit(nxt):
                if quantity is not None:
                    return None
                quantity, spoken_unit = tok, nxt
                if name_started:
                    name_ended = True
                i += 2
                continue
            pending_bare.append((tok, name_started))
            if name_started:
                name_ended = True
            i += 1
            continue
        if tok in _FILLERS:
            i += 1
            continue
        if tok in _PRICE_MARKERS or _is_unit(tok):
            return None
        if name_ended:
            return None
        name_started = True
        name.append(tok)
        i += 1

    if not name:
        return None
    before = [num for num, after_name in pending_bare if not after_name]
    after = [num for num, after_name in pending_bare if after_name]
    if len(after) > 1 or len(before) > 1:
        return None
    if before:
        if quantity is not None:
            return None
        quantity = before[0]
    if after:
        if quantity is None:
            # "rice 2" could mean quantity or price. Require a marker to decide.
            if price is None:
                return None
            quantity = after[0]
        else:
            # Established POS convention: "2 rice 50" means quantity 2 and unit price 50.
            if price is not None:
                return None
            price = after[0]
    return {"name": name, "quantity": quantity or "1", "unit": spoken_unit, "price": price}


def try_fast_parse(
    transcript: str,
    candidates: list[Any],
    *,
    normalize: Callable[[str], str],
    expand_tokens: Callable[[str], set],
    name_of: Callable[[Any], str] = lambda p: str(getattr(p, "product_name", "") or ""),
) -> Optional[dict]:
    """Return an LLM-shaped payload for a clear utterance, else ``None``."""
    if not candidates:
        return None
    tokens = _tokenize(transcript)
    if not tokens:
        return None
    segments = _split_segments(_merge_number_words(tokens))
    if not segments or len(segments) > MAX_SEGMENTS:
        return None

    items: list[dict] = []
    for segment in segments:
        parsed = _parse_segment(segment)
        if parsed is None:
            return None
        try:
            quantity = Decimal(parsed["quantity"])
        except InvalidOperation:
            return None
        if not quantity.is_finite() or quantity <= 0 or quantity > Decimal("10000"):
            return None

        # Fold spoken plurals ("eggs" -> "egg") so they resolve like the singular catalog name.
        name_text = " ".join(stem_token(word) for word in parsed["name"])
        resolution = resolve_catalog_product(
            [name_text],
            transcript,
            candidates,
            normalize=normalize,
            expand_tokens=expand_tokens,
        )
        if resolution.status != "matched" or resolution.product is None:
            return None
        product = resolution.product
        product_name = name_of(product)
        # Pack-size names ("Lux Soap 150g", "Atta 5kg") make "150 g" ambiguous
        # between a pack and a quantity: leave those to the LLM pipeline.
        if size_tokens(product_name):
            return None
        # Every spoken name word must be explained by this one product.
        product_words = expand_tokens(product_name)
        if not all(word in product_words or stem_token(word) in product_words for word in parsed["name"]):
            return None

        # A spoken unit must be convertible to the product's selling unit; "2 kg" of a
        # piece-priced product, or an unknown unit, needs the cashier's confirmation.
        if parsed["unit"]:
            conversion = convert_quantity(quantity, parsed["unit"], getattr(product, "unit", "pcs") or "pcs")
            if conversion.status not in {"same", "converted"}:
                return None

        kind, amount = "none", None
        if parsed["price"] is not None:
            try:
                price = Decimal(parsed["price"])
            except InvalidOperation:
                return None
            if not price.is_finite() or price <= 0 or price > Decimal("1000000"):
                return None
            kind, amount = "unit", float(price)
        items.append({
            "product_id": int(product.id),
            "product_name_en": product_name,
            "product_name_local": "",
            "quantity": str(int(quantity)) if quantity == quantity.to_integral_value() else format(quantity, "f"),
            "spoken_unit": parsed["unit"],
            "spoken_price_amount": amount,
            "spoken_price_kind": kind,
            "confidence": 0.99,
        })

    return {
        "interpreted_text_en": normalize(transcript)[:320],
        "items": items,
        "needs_clarification": False,
        "clarification_question": "",
        "fast_path": True,
    }
