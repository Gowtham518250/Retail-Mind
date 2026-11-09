"""Deterministic, side-effect-free helpers for voice billing.

The LLM proposes draft lines; this module is the financial safety net applied
afterwards.  It never touches the database, the network or the LLM, so every
rule here can be unit-tested and benchmarked offline.

Responsibilities
* spoken-unit canonicalisation and exact Decimal unit conversion
* "was this quantity actually spoken?" grounding check
* per-item catalog resolution that
    - judges evidence from the item's own words (not the whole utterance), and
    - refuses to silently pick between equally plausible products
      (e.g. "Lux soap" when Lux 100g and Lux 150g are both stocked).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

# --------------------------------------------------------------------------- #
# Units
# --------------------------------------------------------------------------- #
# dimension -> {alias: factor to the dimension's base unit}
#   mass base = gram, volume base = millilitre, count base = piece
_UNIT_ALIASES: dict[str, dict[str, int]] = {
    "mass": {
        "g": 1, "gm": 1, "gms": 1, "gram": 1, "grams": 1, "gramme": 1,
        "గ్రాము": 1, "గ్రాములు": 1, "గ్రాం": 1, "గ్రా": 1, "ग्राम": 1,
        "kg": 1000, "kgs": 1000, "kilo": 1000, "kilos": 1000,
        "kilogram": 1000, "kilograms": 1000,
        "కిలో": 1000, "కిలోలు": 1000, "కిలోగ్రాము": 1000, "కేజీ": 1000,
        "కేజీలు": 1000, "కిలోల": 1000, "किलो": 1000, "किलोग्राम": 1000,
    },
    "volume": {
        "ml": 1, "mls": 1, "millilitre": 1, "milliliter": 1, "millilitres": 1,
        "milliliters": 1, "మిల్లీలీటర్": 1, "మి.లీ": 1, "मिलीलीटर": 1,
        "l": 1000, "lt": 1000, "ltr": 1000, "ltrs": 1000, "litre": 1000,
        "liter": 1000, "litres": 1000, "liters": 1000,
        "లీటర్": 1000, "లీటర్లు": 1000, "లీటరు": 1000, "లీటర్ల": 1000,
        "लीटर": 1000,
    },
    "count": {
        "pc": 1, "pcs": 1, "piece": 1, "pieces": 1, "unit": 1, "units": 1,
        "nos": 1, "no": 1, "number": 1, "numbers": 1, "item": 1, "items": 1,
        "dozen": 12, "dozens": 12, "doz": 12, "డజను": 12, "డజన్": 12,
        "డజన్లు": 12, "दर्जन": 12, "नग": 1,
    },
    "packet": {
        "packet": 1, "packets": 1, "pack": 1, "packs": 1, "pkt": 1,
        "ప్యాకెట్": 1, "ప్యాకెట్లు": 1, "ప్యాకెట్ల": 1, "पैकेट": 1,
    },
    "box": {"box": 1, "boxes": 1, "డబ్బా": 1, "డబ్బాలు": 1},
    "bottle": {"bottle": 1, "bottles": 1, "బాటిల్": 1, "బాటిళ్లు": 1, "बोतल": 1},
    "tin": {"tin": 1, "tins": 1},
    "can": {"can": 1, "cans": 1},
    "bag": {"bag": 1, "bags": 1},
    "sachet": {"sachet": 1, "sachets": 1},
}
_UNIT_LOOKUP: dict[str, tuple[str, int]] = {
    alias: (dimension, factor)
    for dimension, aliases in _UNIT_ALIASES.items()
    for alias, factor in aliases.items()
}
_QTY_Q = Decimal("0.001")


@dataclass(frozen=True)
class UnitInfo:
    dimension: str  # mass | volume | count
    factor: int  # to base unit
    name: str  # normalised alias used for lookup


def canonical_unit(value: Any) -> Optional[UnitInfo]:
    """Return unit metadata for a spoken or catalogue unit string, else None."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    text = text.strip(" .,:;()[]")
    if not text:
        return None
    found = _UNIT_LOOKUP.get(text)
    if found is None:
        found = _UNIT_LOOKUP.get(text.rstrip("."))
    if found is None:
        return None
    return UnitInfo(dimension=found[0], factor=found[1], name=text)


@dataclass(frozen=True)
class UnitConversion:
    quantity: Decimal
    status: str  # same | converted | no_spoken_unit | unknown_unit | incompatible
    detail: str = ""

    @property
    def converted(self) -> bool:
        return self.status == "converted"

    @property
    def incompatible(self) -> bool:
        return self.status == "incompatible"


def convert_quantity(
    quantity: Decimal,
    spoken_unit: Any,
    product_unit: Any,
) -> UnitConversion:
    """Convert a spoken quantity to the product's selling unit using Decimal.

    * 500 g of a kg-product  -> 0.5
    * 1.5 l of a ml-product  -> 1500
    * 2 dozen of a pcs-product -> 24
    * package units are separate dimensions; pack-size conversion requires explicit catalog configuration
    * kg spoken for a litre/pcs product -> ``incompatible`` (caller must confirm)
    """
    quantity = Decimal(quantity)
    spoken = canonical_unit(spoken_unit)
    if spoken is None:
        status = "no_spoken_unit" if not str(spoken_unit or "").strip() else "unknown_unit"
        return UnitConversion(quantity, status)
    target = canonical_unit(product_unit)
    if target is None:
        return UnitConversion(quantity, "unknown_unit", f"product unit {product_unit!r} unknown")
    if spoken.dimension != target.dimension:
        return UnitConversion(
            quantity,
            "incompatible",
            f"spoken {spoken.name} ({spoken.dimension}) vs selling unit {target.name} ({target.dimension})",
        )
    if spoken.factor == target.factor:
        return UnitConversion(quantity, "same")
    converted = (quantity * Decimal(spoken.factor) / Decimal(target.factor)).quantize(
        _QTY_Q, rounding=ROUND_HALF_UP
    )
    return UnitConversion(converted, "converted", f"{quantity} {spoken.name} -> {converted} {target.name}")


# --------------------------------------------------------------------------- #
# Spoken-number grounding
# --------------------------------------------------------------------------- #
_FRACTION_WORDS: dict[str, Decimal] = {
    "half": Decimal("0.5"), "aadha": Decimal("0.5"), "adha": Decimal("0.5"),
    "ara": Decimal("0.5"), "ardha": Decimal("0.5"), "అర": Decimal("0.5"),
    "అరకిలో": Decimal("0.5"), "आधा": Decimal("0.5"), "आधी": Decimal("0.5"),
    "quarter": Decimal("0.25"), "paav": Decimal("0.25"), "pav": Decimal("0.25"),
    "paavu": Decimal("0.25"), "పావు": Decimal("0.25"), "పావ్": Decimal("0.25"),
    "पाव": Decimal("0.25"),
    "dedh": Decimal("1.5"), "deadh": Decimal("1.5"), "डेढ़": Decimal("1.5"),
    "डेढ": Decimal("1.5"), "okatinnara": Decimal("1.5"), "ఒకటిన్నర": Decimal("1.5"),
    "ఒకటిన్నర్": Decimal("1.5"), "dhai": Decimal("2.5"), "adhai": Decimal("2.5"),
    "ढाई": Decimal("2.5"), "rendunnara": Decimal("2.5"), "రెండున్నర": Decimal("2.5"),
    "మూడున్నర": Decimal("3.5"), "moodunnara": Decimal("3.5"),
}
_EXTRA_NUMBER_WORDS: dict[str, int] = {
    "a": 1, "an": 1, "oka": 1, "ఒక": 1, "ఒకటి": 1, "single": 1,
    "couple": 2, "జంట": 2,
}
_DIGIT_RE = re.compile(r"\d+(?:,\d{2,3})*(?:\.\d+)?|\d+/\d+")


def _tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    cleaned = "".join(
        ch if ch.isspace() or unicodedata.category(ch)[0] in {"L", "M", "N"} or ch in ".,/" else " "
        for ch in text
    )
    return [tok.strip(".,") for tok in cleaned.split() if tok.strip(".,")]


def spoken_numbers(
    text: str,
    number_words: Mapping[str, int],
    scale_words: Mapping[str, int],
) -> set[Decimal]:
    """Every numeric value a listener could have heard in ``text``.

    The set is deliberately generous (it contains single tokens *and* common
    compositions such as "twenty five", "two hundred", "one and a half").  It is
    only used to reject quantities that appear nowhere in the speech.
    """
    values: set[Decimal] = set()
    for match in _DIGIT_RE.finditer(unicodedata.normalize("NFKC", text or "")):
        raw = match.group(0)
        try:
            if "/" in raw:
                top, bottom = raw.split("/", 1)
                if int(bottom):
                    values.add(Decimal(int(top)) / Decimal(int(bottom)))
            else:
                values.add(Decimal(raw.replace(",", "")))
        except (InvalidOperation, ValueError):
            continue

    toks = _tokens(text)
    word_values: list[Optional[Decimal]] = []
    for tok in toks:
        if tok in number_words:
            word_values.append(Decimal(number_words[tok]))
        elif tok in _FRACTION_WORDS:
            word_values.append(_FRACTION_WORDS[tok])
        elif tok in _EXTRA_NUMBER_WORDS:
            word_values.append(Decimal(_EXTRA_NUMBER_WORDS[tok]))
        else:
            word_values.append(None)
    values.update(v for v in word_values if v is not None)

    for i, tok in enumerate(toks):
        cur = word_values[i]
        nxt = word_values[i + 1] if i + 1 < len(toks) else None
        if cur is not None and nxt is not None:
            if cur >= 20 and cur % 10 == 0 and Decimal(1) <= nxt <= 9:  # twenty five
                values.add(cur + nxt)
            if Decimal(0) < cur < Decimal(10) and nxt in (Decimal("0.5"), Decimal("0.25")):
                values.add(cur + nxt)  # "two half" style from ASR
        scale = scale_words.get(toks[i + 1]) if i + 1 < len(toks) else None
        if cur is not None and scale:
            base = cur * Decimal(scale)
            values.add(base)
            if i + 2 < len(toks):
                rem = word_values[i + 2]
                if rem is None and toks[i + 2] in {"and", "aur", "మరియు", "mariyu"} and i + 3 < len(toks):
                    rem = word_values[i + 3]
                if rem is not None:
                    values.add(base + rem)
        # "one and a half", "two and half"
        if cur is not None and Decimal(0) < cur < 100 and i + 2 < len(toks) and toks[i + 1] in {"and", "aur", "మరియు"}:
            j = i + 2
            if toks[j] in {"a", "an"} and j + 1 < len(toks):
                j += 1
            if toks[j] in {"half", "aadha", "adha", "ardha", "అర", "आधा"}:
                values.add(cur + Decimal("0.5"))
            if toks[j] in {"quarter", "paav", "pav", "పావు", "पाव"}:
                values.add(cur + Decimal("0.25"))
    return values


def quantity_is_grounded(
    quantity: Decimal,
    transcripts: Iterable[str],
    number_words: Mapping[str, int],
    scale_words: Mapping[str, int],
) -> bool:
    """True when ``quantity`` was spoken in any transcript form.

    A quantity of exactly 1 is always grounded: "one" is the documented
    default when no count is spoken ("add rice").  A spoken dozen counts as 12.
    """
    quantity = Decimal(quantity)
    transcript_values = [str(text or "") for text in transcripts]
    heard: set[Decimal] = set()
    for transcript in transcript_values:
        heard |= spoken_numbers(transcript, number_words, scale_words)
    if quantity == 1:
        # One is the default only when no quantity was spoken before the product.
        # If the cashier clearly said "2 kg rice", an extractor's fallback quantity
        # of 1 must not pass merely because 1 is the default.
        return not heard or quantity in heard
    if quantity in heard:
        return True
    # A multiple of twelve is accepted only when "dozen" was actually spoken.
    for transcript in transcript_values:
        if re.search(r"(?i)\b(?:dozen|dozens|doz|డజను|డజన్|డజన్లు|दर्जन)\b", transcript):
            if any(h > 0 and quantity == h * 12 for h in heard if h == h.to_integral_value()):
                return True
    return False


def spoken_unit_is_grounded(spoken_unit: Any, transcripts: Iterable[str]) -> bool:
    """True when a unit of the same dimension and size was actually said.

    The extraction model reports the unit it believes was spoken.  A hallucinated "g" for
    "2 kg rice" would otherwise scale the quantity by 1000 with no warning.  Units the
    catalogue does not know are left to ``convert_quantity`` (returns True here).
    """
    wanted = canonical_unit(spoken_unit)
    if wanted is None:
        return True
    for transcript in transcripts:
        text = unicodedata.normalize("NFKC", transcript or "")
        text = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", text)  # "500g" -> "500 g"
        for token in _tokens(text):
            info = canonical_unit(token)
            if info and info.dimension == wanted.dimension and info.factor == wanted.factor:
                return True
    return False


def repair_spoken_unit(
    transcripts: Iterable[str],
    number_words: Optional[Mapping[str, int]] = None,
) -> Optional[str]:
    """Return the single unit spoken immediately after a numeric or number-word quantity.

    Supports native-script speech such as Telugu "మూడు కేజీలు" as well as "3 kg".
    If an utterance contains different units, return None rather than borrowing one
    item's unit for another line.
    """
    found: dict[tuple, str] = {}
    recognized_number_words = set(number_words or {}) | set(_EXTRA_NUMBER_WORDS) | set(_FRACTION_WORDS)
    for transcript in transcripts:
        text = unicodedata.normalize("NFKC", transcript or "")
        text = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", text)
        words = [w.strip(".,;:!?()[]\"'").casefold() for w in text.split()]
        for current, following in zip(words, words[1:]):
            is_number = bool(re.fullmatch(r"\d+(?:\.\d+)?", current)) or current in recognized_number_words
            if not is_number:
                continue
            info = canonical_unit(following)
            if info:
                found[(info.dimension, info.factor)] = following
    return next(iter(found.values())) if len(found) == 1 else None


# --------------------------------------------------------------------------- #
# Catalog resolution
# --------------------------------------------------------------------------- #
_SIZE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|kgs|kilo|kilos|kilogram|kilograms|g|gm|gms|gram|grams|ml|ltr|ltrs|litre|litres|liter|liters|l)\b",
    re.IGNORECASE,
)

_STOP = {
    "a", "an", "the", "please", "add", "want", "need", "give", "me", "for", "at",
    "price", "cost", "rupee", "rupees", "rs", "inr", "only", "total", "each", "per",
    "unit", "of", "to", "is", "and", "then", "product", "pack", "packet", "packets",
    "piece", "pieces", "pcs", "bottle", "bottles", "box", "boxes",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
}


def size_tokens(text: str) -> frozenset[str]:
    """Canonical pack-size tokens: "100 g" -> "100g", "1 kg" -> "1000g", "1.5 l" -> "1500ml"."""
    out: set[str] = set()
    for value, unit in _SIZE_RE.findall(unicodedata.normalize("NFKC", text or "")):
        info = canonical_unit(unit)
        if info is None:
            continue
        try:
            base = (Decimal(value) * Decimal(info.factor)).normalize()
        except InvalidOperation:
            continue
        suffix = "g" if info.dimension == "mass" else "ml"
        out.add(f"{base:f}{suffix}")
    return frozenset(out)


@dataclass
class Candidate:
    product: Any
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class Resolution:
    status: str  # matched | ambiguous | none
    product: Any = None
    candidates: list[Candidate] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def stem_token(token: str) -> str:
    """Cheap plural folding ("soaps"->"soap", "eggs"->"egg"); Indic tokens are left alone."""
    if len(token) > 3 and token.isascii() and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _meaningful(tokens: Iterable[str]) -> set[str]:
    base = {t for t in tokens if t and t not in _STOP and not t.isdigit() and not _SIZE_RE.fullmatch(t)}
    return base | {stem_token(t) for t in base}


def resolve_catalog_product(
    item_texts: Sequence[str],
    transcript: str,
    products: Sequence[Any],
    *,
    normalize: Callable[[str], str],
    expand_tokens: Callable[[str], set[str]],
    name_of: Callable[[Any], str] = lambda p: str(getattr(p, "product_name", "") or ""),
    sku_of: Callable[[Any], str] = lambda p: str(getattr(p, "sku", "") or ""),
    max_candidates: int = 5,
    hint_product: Any = None,
) -> Resolution:
    """Resolve one extracted line to a catalog product, or say it is ambiguous.

    ``item_texts`` are the model's names for the line (English and local).  Only
    words that were *actually spoken* (present in ``transcript`` after alias
    expansion) are used as evidence, so a model cannot upgrade "rice" to a
    specific brand it saw in the catalogue.
    """
    spoken_tokens = expand_tokens(transcript)
    spoken_plain = set(normalize(transcript).split())
    transcript_norm = normalize(transcript)

    # Use the first name variant (English, then local, then proposed) that has words the
    # speaker really said.  An unfamiliar romanised local word must never veto a match
    # that the English name already supports.
    expanded_item: set[str] = set()
    for text in item_texts:
        group = {
            t for t in _meaningful(normalize(text).split())
            if t in spoken_tokens or t in spoken_plain
        }
        if group:
            expanded_item = _meaningful(expand_tokens(" ".join(sorted(group))))
            break
    if not expanded_item and hint_product is not None:
        # The model gave an ID but no usable name: fall back to the spoken words
        # that overlap the product it chose (still requires real spoken evidence).
        expanded_item = _meaningful(spoken_tokens) & _meaningful(expand_tokens(name_of(hint_product)))
    if not expanded_item:
        return Resolution("none", reasons=["no spoken product words"])

    item_norm = " ".join(normalize(text) for text in item_texts if text)
    pool: list[Candidate] = []
    spoken_sizes = size_tokens(transcript)
    for product in products:
        name = name_of(product)
        name_norm = normalize(name)
        name_tokens = _meaningful(expand_tokens(name))
        reasons: list[str] = []
        sku_norm = normalize(sku_of(product))
        exact_name = bool(name_norm and name_norm in transcript_norm)
        # A SKU only identifies THIS line when its words belong to this line's own spoken
        # words. Another line's SKU appearing elsewhere in the utterance (SKU "MILK" in
        # "3 soap and 1 litre milk") must not pull that product into the "soap" line.
        sku_tokens = set(sku_norm.split())
        exact_sku = bool(
            sku_norm
            and sku_norm in transcript_norm
            and (sku_norm in item_norm or sku_tokens & expanded_item)
        )
        if exact_name:
            reasons.append("full product name spoken")
        if exact_sku:
            reasons.append("SKU spoken")
        # Membership always requires the line's own spoken words to fit the product.
        # Another line's full product name appearing in the utterance is NOT evidence
        # for this line (it used to pull "Sunflower Oil" into the "rice" line).
        if not (name_tokens and expanded_item.issubset(name_tokens)) and not exact_sku:
            continue
        overlap = len(expanded_item & name_tokens) / max(1, len(name_tokens))
        reasons.append(f"spoken words cover {overlap:.0%} of product name")
        score = 100.0 * overlap + (50.0 if exact_name else 0.0) + (60.0 if exact_sku else 0.0)
        pool.append(Candidate(product, score, reasons))

    if not pool:
        return Resolution("none", reasons=["no catalog product contains every spoken word"])
    pool.sort(key=lambda c: c.score, reverse=True)
    if len(pool) == 1:
        pool[0].reasons.append("only catalog product matching the spoken words")
        return Resolution("matched", pool[0].product, pool, pool[0].reasons)

    # More than one plausible product: look for distinguishing evidence.
    # 1) the pack size this very line named ("Lux Soap 150g"), if it was really spoken
    item_sizes: set[str] = set()
    for text in item_texts:
        item_sizes |= set(size_tokens(text))
    item_sizes &= set(spoken_sizes)
    if item_sizes:
        by_item_size = [c for c in pool if size_tokens(name_of(c.product)) and size_tokens(name_of(c.product)) <= item_sizes]
        if len(by_item_size) == 1:
            by_item_size[0].reasons.append("pack size named for this line matches")
            return Resolution("matched", by_item_size[0].product, pool, by_item_size[0].reasons)
    # 2) a product whose full name was spoken
    exact = [c for c in pool if "full product name spoken" in c.reasons or "SKU spoken" in c.reasons]
    if exact:
        best = max(c.score for c in exact)
        top = [c for c in exact if c.score == best]
        # the longest exact-name hit wins only if nothing else exact ties
        top.sort(key=lambda c: len(normalize(name_of(c.product))), reverse=True)
        if len(top) == 1 or len(normalize(name_of(top[0].product))) > len(normalize(name_of(top[1].product))):
            top[0].reasons.append("only candidate whose full name was spoken")
            return Resolution("matched", top[0].product, pool, top[0].reasons)

    sized = [c for c in pool if size_tokens(name_of(c.product)) and size_tokens(name_of(c.product)) <= spoken_sizes]
    if len(sized) == 1:
        sized[0].reasons.append("spoken pack size matches")
        return Resolution("matched", sized[0].product, pool, sized[0].reasons)

    distinguished = []
    for c in pool:
        extras = _meaningful(expand_tokens(name_of(c.product))) - expanded_item
        if extras and extras <= spoken_tokens:
            distinguished.append(c)
    if len(distinguished) == 1:
        distinguished[0].reasons.append("distinguishing words spoken")
        return Resolution("matched", distinguished[0].product, pool, distinguished[0].reasons)

    return Resolution(
        "ambiguous",
        None,
        pool[:max_candidates],
        [f"{len(pool)} catalog products fit the spoken words equally"],
    )


# --------------------------------------------------------------------------- #
# Idempotency for repeated submissions
# --------------------------------------------------------------------------- #
def custom_name_is_grounded(
    names: Iterable[str],
    transcripts: Iterable[str],
    *,
    normalize,
) -> bool:
    """True when a non-catalog product name is literally present in what was said.

    Guards against an extraction model inventing a line that the speaker never
    uttered.  Matches on any meaningful stemmed word or on the compacted name
    ("tooth brush" == "toothbrush").  A name with no testable word is not blocked.
    """
    haystacks = [normalize(t) for t in transcripts if t]
    hay_tokens = {stem_token(tok) for h in haystacks for tok in h.split()}
    hay_compact = " ".join(h.replace(" ", "") for h in haystacks)
    testable = False
    for name in names:
        norm = normalize(name or "")
        tokens = [stem_token(t) for t in norm.split() if len(t) >= 3 and not t.isdigit()]
        if not tokens:
            continue
        testable = True
        if all(t in hay_tokens for t in tokens):
            return True
        compact = norm.replace(" ", "")
        if len(compact) >= 4 and compact in hay_compact:
            return True
    return not testable
