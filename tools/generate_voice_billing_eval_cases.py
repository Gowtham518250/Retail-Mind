"""Generate the synthetic voice-billing evaluation set (deterministic, no randomness).

Each case models what the LLM extraction stage returns for an utterance (gold
names / quantities / units, plus a few deliberate LLM mistakes).  The evaluator
then scores the *deterministic* post-processing that decides catalog match,
ambiguity, unit conversion and quantity grounding.  This is NOT an ASR test:
real ASR accuracy needs labelled audio (see docs/VOICE_AI_EVALUATION.md).

Usage: python tools/generate_voice_billing_eval_cases.py
"""
from __future__ import annotations

import json
from pathlib import Path

CATALOGS = {
    "main": [
        {"id": 1, "name": "Sona Masoori Rice", "unit": "kg", "price": "62.00", "stock": "50"},
        {"id": 3, "name": "Lux Soap 100g", "unit": "pcs", "price": "30.00", "stock": "40"},
        {"id": 4, "name": "Lux Soap 150g", "unit": "pcs", "price": "42.00", "stock": "40"},
        {"id": 5, "name": "Lifebuoy Soap 100g", "unit": "pcs", "price": "28.00", "stock": "40"},
        {"id": 6, "name": "Tata Salt 1kg", "unit": "pcs", "price": "28.00", "stock": "40"},
        {"id": 7, "name": "Tata Salt 2kg", "unit": "pcs", "price": "54.00", "stock": "40"},
        {"id": 8, "name": "Sunflower Oil", "unit": "l", "price": "140.00", "stock": "30"},
        {"id": 9, "name": "Sugar", "unit": "kg", "price": "44.00", "stock": "60"},
        {"id": 10, "name": "Parle G Biscuits", "unit": "pcs", "price": "10.00", "stock": "90"},
        {"id": 11, "name": "Boost", "unit": "pcs", "price": "260.00", "stock": "12"},
        {"id": 12, "name": "Milk", "unit": "l", "price": "56.00", "stock": "20"},
        {"id": 13, "name": "Toor Dal", "unit": "kg", "price": "120.00", "stock": "35"},
        {"id": 14, "name": "Colgate Toothpaste", "unit": "pcs", "price": "95.00", "stock": "25"},
        {"id": 15, "name": "Eggs", "unit": "pcs", "price": "7.00", "stock": "300"},
    ],
}
CATALOGS["rice2"] = CATALOGS["main"] + [
    {"id": 2, "name": "Basmati Rice", "unit": "kg", "price": "110.00", "stock": "30"},
]

AMB = "AMBIGUOUS"
cases: list[dict] = []


def item(name_en, name_local, qty, unit, pid, exp_qty=None, grounded=True, mismatch=False):
    return {
        "name_en": name_en, "name_local": name_local, "qty": str(qty), "spoken_unit": unit,
        "expect": {
            "product": pid,  # int | "AMBIGUOUS" | None (custom line)
            "qty": str(exp_qty if exp_qty is not None else qty),
            "grounded": grounded, "unit_mismatch": mismatch,
        },
    }


def add(cat, lang, spoken, english, items, catalog="main", replay=False):
    cases.append({
        "id": f"{cat}-{sum(1 for c in cases if c['category'] == cat) + 1:03d}",
        "category": cat, "language": lang, "spoken": spoken, "english": english,
        "catalog": catalog, "items": items, "replay_same_request": replay,
    })


# 1. single item, English ---------------------------------------------------
for q, text, name, pid, unit in [
    (2, "2 kg sona masoori rice", "Sona Masoori Rice", 1, "kg"),
    (3, "3 lifebuoy soap", "Lifebuoy Soap", 5, ""),
    (1, "1 litre sunflower oil", "Sunflower Oil", 8, "litre"),
    (4, "4 kg sugar", "Sugar", 9, "kg"),
    (6, "6 parle g biscuits", "Parle G Biscuits", 10, ""),
    (2, "2 boost", "Boost", 11, ""),
    (2, "2 litres milk", "Milk", 12, "litres"),
    (1, "1 kg toor dal", "Toor Dal", 13, "kg"),
    (3, "3 colgate toothpaste", "Colgate Toothpaste", 14, ""),
    (12, "12 eggs", "Eggs", 15, ""),
    (5, "5 sugar", "Sugar", 9, ""),
    (7, "7 milk", "Milk", 12, ""),
    (2, "please add 2 kg sugar", "Sugar", 9, "kg"),
    (8, "give me 8 eggs", "Eggs", 15, ""),
    (3, "3 packets parle g biscuits", "Parle G Biscuits", 10, "packets"),
    # label correction: a "bottle" of a per-litre product is not a litre, so the safe
    # behaviour is to flag a unit mismatch for confirmation (handled below).
    (10, "10 colgate toothpaste", "Colgate Toothpaste", 14, ""),
    (2, "2 toor dal", "Toor Dal", 13, ""),
    (9, "9 lifebuoy soap", "Lifebuoy Soap", 5, ""),
    (1, "1 sona masoori rice", "Sona Masoori Rice", 1, ""),
]:
    add("single_item_english", "en", text, text, [item(name, "", q, unit, pid)])

# 2. multi item (the whole-utterance evidence regression) --------------------
multi = [
    ("2 kg rice and 3 lifebuoy soap", [("Sona Masoori Rice", 2, "kg", 1), ("Lifebuoy Soap", 3, "", 5)]),
    ("2 kg rice, 3 lifebuoy soap, 1 litre sunflower oil, 5 parle g biscuits",
     [("Sona Masoori Rice", 2, "kg", 1), ("Lifebuoy Soap", 3, "", 5), ("Sunflower Oil", 1, "litre", 8), ("Parle G Biscuits", 5, "", 10)]),
    ("3 colgate toothpaste and 2 boost", [("Colgate Toothpaste", 3, "", 14), ("Boost", 2, "", 11)]),
    ("1 kg sugar and 1 kg toor dal and 2 litres milk", [("Sugar", 1, "kg", 9), ("Toor Dal", 1, "kg", 13), ("Milk", 2, "litres", 12)]),
    ("12 eggs and 2 parle g biscuits", [("Eggs", 12, "", 15), ("Parle G Biscuits", 2, "", 10)]),
    ("2 kg rice, 3 sugar", [("Sona Masoori Rice", 2, "kg", 1), ("Sugar", 3, "", 9)]),
    ("4 lifebuoy soap and 1 colgate toothpaste", [("Lifebuoy Soap", 4, "", 5), ("Colgate Toothpaste", 1, "", 14)]),
    ("2 litres sunflower oil and 5 eggs and 1 boost", [("Sunflower Oil", 2, "litres", 8), ("Eggs", 5, "", 15), ("Boost", 1, "", 11)]),
    ("3 kg sona masoori rice and 2 kg toor dal", [("Sona Masoori Rice", 3, "kg", 1), ("Toor Dal", 2, "kg", 13)]),
    ("6 milk and 4 sugar and 2 colgate toothpaste", [("Milk", 6, "", 12), ("Sugar", 4, "", 9), ("Colgate Toothpaste", 2, "", 14)]),
    ("5 parle g biscuits and 3 lifebuoy soap and 2 kg rice", [("Parle G Biscuits", 5, "", 10), ("Lifebuoy Soap", 3, "", 5), ("Sona Masoori Rice", 2, "kg", 1)]),
    ("1 litre milk and 12 eggs", [("Milk", 1, "litre", 12), ("Eggs", 12, "", 15)]),
    ("2 boost and 2 colgate toothpaste and 2 sugar", [("Boost", 2, "", 11), ("Colgate Toothpaste", 2, "", 14), ("Sugar", 2, "", 9)]),
    ("1 kg rice and 1 litre sunflower oil", [("Sona Masoori Rice", 1, "kg", 1), ("Sunflower Oil", 1, "litre", 8)]),
    ("3 toor dal and 3 sugar and 3 milk", [("Toor Dal", 3, "", 13), ("Sugar", 3, "", 9), ("Milk", 3, "", 12)]),
    ("8 eggs and 1 lifebuoy soap and 2 parle g biscuits", [("Eggs", 8, "", 15), ("Lifebuoy Soap", 1, "", 5), ("Parle G Biscuits", 2, "", 10)]),
    ("2 kg sugar and 2 kg toor dal and 2 kg rice", [("Sugar", 2, "kg", 9), ("Toor Dal", 2, "kg", 13), ("Sona Masoori Rice", 2, "kg", 1)]),
    ("4 boost and 1 milk", [("Boost", 4, "", 11), ("Milk", 1, "", 12)]),
    ("5 colgate toothpaste and 5 lifebuoy soap", [("Colgate Toothpaste", 5, "", 14), ("Lifebuoy Soap", 5, "", 5)]),
    ("3 litres sunflower oil and 1 kg sugar and 2 boost", [("Sunflower Oil", 3, "litres", 8), ("Sugar", 1, "kg", 9), ("Boost", 2, "", 11)]),
]
for text, rows in multi:
    add("multi_item", "en", text, text, [item(n, "", q, u, p) for n, q, u, p in rows])

# 3. ambiguous product variants ---------------------------------------------
for text, name, q, pid, unit in [
    ("5 lux soap", "Lux Soap", 5, AMB, ""),
    ("2 lux soap", "Lux Soap", 2, AMB, ""),
    ("1 lux soap", "Lux Soap", 1, AMB, ""),
    ("3 lux soap", "Lux Soap", 3, AMB, ""),
    ("2 tata salt", "Tata Salt", 2, AMB, ""),
    ("4 tata salt", "Tata Salt", 4, AMB, ""),
    ("1 tata salt", "Tata Salt", 1, AMB, ""),
    ("6 tata salt", "Tata Salt", 6, AMB, ""),
    ("2 lux soap 150g", "Lux Soap 150g", 2, 4, ""),
    ("3 lux soap 100g", "Lux Soap 100g", 3, 3, ""),
    ("2 lux soap 100 g", "Lux Soap 100g", 2, 3, ""),
    ("5 lux soap 150 gram", "Lux Soap 150g", 5, 4, ""),
    ("4 tata salt 1kg", "Tata Salt 1kg", 4, 6, ""),
    ("3 tata salt 2kg", "Tata Salt 2kg", 3, 7, ""),
    ("2 tata salt 2 kg", "Tata Salt 2kg", 2, 7, ""),
    ("1 tata salt 1 kg", "Tata Salt 1kg", 1, 6, ""),
    ("2 lux soap 100g and 3 lux soap 150g", None, None, None, None),  # two lines
    ("3 soap", "Soap", 3, AMB, ""),
    ("2 soap", "Soap", 2, AMB, ""),
    ("2 salt", "Salt", 2, AMB, ""),
]:
    if name is None:
        add("ambiguous_variants", "en", text, text,
            [item("Lux Soap 100g", "", 2, "", 3), item("Lux Soap 150g", "", 3, "", 4)])
    else:
        add("ambiguous_variants", "en", text, text, [item(name, "", q, unit, pid)])
add("ambiguous_variants", "en", "2 rice", "2 rice", [item("Rice", "", 2, "", AMB)], catalog="rice2")
add("ambiguous_variants", "en", "2 basmati rice", "2 basmati rice", [item("Basmati Rice", "", 2, "", 2)], catalog="rice2")
add("ambiguous_variants", "en", "3 kg sona masoori rice", "3 kg sona masoori rice", [item("Sona Masoori Rice", "", 3, "kg", 1)], catalog="rice2")
add("ambiguous_variants", "en", "2 kg rice and 3 lux soap", "2 kg rice and 3 lux soap",
    [item("Rice", "", 2, "kg", AMB), item("Lux Soap", "", 3, "", AMB)], catalog="rice2")

# 4. unit conversion ----------------------------------------------------------
for text, name, q, u, pid, exp in [
    ("500 grams sugar", "Sugar", 500, "grams", 9, "0.500"),
    ("250 grams toor dal", "Toor Dal", 250, "grams", 13, "0.250"),
    ("750 ml sunflower oil", "Sunflower Oil", 750, "ml", 8, "0.750"),
    ("1500 grams sona masoori rice", "Sona Masoori Rice", 1500, "grams", 1, "1.500"),
    ("1.5 kg sugar", "Sugar", "1.5", "kg", 9, "1.5"),
    ("half kilo sugar", "Sugar", "0.5", "kilo", 9, "0.5"),
    ("quarter kilo toor dal", "Toor Dal", "0.25", "kilo", 13, "0.25"),
    ("2 dozen eggs", "Eggs", 2, "dozen", 15, "24.000"),
    ("1 dozen eggs", "Eggs", 1, "dozen", 15, "12.000"),
    ("a dozen eggs", "Eggs", 1, "dozen", 15, "12.000"),
    ("200 ml milk", "Milk", 200, "ml", 12, "0.200"),
    ("500 ml milk", "Milk", 500, "ml", 12, "0.500"),
    ("2 litres milk", "Milk", 2, "litres", 12, "2"),
    ("1 litre sunflower oil", "Sunflower Oil", 1, "litre", 8, "1"),
    ("100 grams sugar", "Sugar", 100, "grams", 9, "0.100"),
    ("50 grams toor dal", "Toor Dal", 50, "gm", 13, "0.050"),
    ("3 kilos sugar", "Sugar", 3, "kilos", 9, "3"),
    ("2 kg toor dal", "Toor Dal", 2, "kg", 13, "2"),
    ("1250 ml milk", "Milk", 1250, "ml", 12, "1.250"),
    ("half dozen eggs", "Eggs", "0.5", "dozen", 15, "6.000"),
    ("2 packets parle g biscuits", "Parle G Biscuits", 2, "packets", 10, "2"),
    ("3 boxes boost", "Boost", 3, "boxes", 11, "3"),
    ("900 grams sona masoori rice", "Sona Masoori Rice", 900, "grams", 1, "0.900"),
    ("300 grams sugar", "Sugar", 300, "grams", 9, "0.300"),
]:
    spoken = text
    add("unit_conversion", "en", spoken, spoken, [item(name, "", q, u, pid, exp)])
# half / quarter are spoken words; grounding must accept them
# 5. incompatible units -------------------------------------------------------
for text, name, q, u, pid in [
    ("2 litres sugar", "Sugar", 2, "litres", 9),
    ("3 kg milk", "Milk", 3, "kg", 12),
    ("2 kg eggs", "Eggs", 2, "kg", 15),
    ("1 litre toor dal", "Toor Dal", 1, "litre", 13),
    ("500 ml sona masoori rice", "Sona Masoori Rice", 500, "ml", 1),
    ("2 kg boost", "Boost", 2, "kg", 11),
    ("3 litres colgate toothpaste", "Colgate Toothpaste", 3, "litres", 14),
    ("250 grams sunflower oil", "Sunflower Oil", 250, "grams", 8),
]:
    add("unit_incompatible", "en", text, text, [item(name, "", q, u, pid, q, True, True)])

for text, name, q, u, pid in [
    ("2 bottles sunflower oil", "Sunflower Oil", 2, "bottles", 8),
    ("1 bottle sunflower oil", "Sunflower Oil", 1, "bottle", 8),
    ("3 bottles milk", "Milk", 3, "bottles", 12),
]:
    add("unit_incompatible", "en", text, text, [item(name, "", q, u, pid, q, True, True)])

# 6. Telugu script ------------------------------------------------------------
tel = [
    ("రెండు కిలోల బియ్యం", "2 kg rice", "Rice", "బియ్యం", 2, "kg", 1),
    ("మూడు కిలోల పంచదార", "3 kg sugar", "Sugar", "పంచదార", 3, "kg", 9),
    ("ఒక లీటర్ నూనె", "1 litre oil", "Sunflower Oil", "నూనె", 1, "litre", 8),
    ("అర కిలో చక్కెర", "half kilo sugar", "Sugar", "చక్కెర", "0.5", "kilo", 9),
    ("రెండు లీటర్ల పాలు", "2 litres milk", "Milk", "పాలు", 2, "litres", 12),
    ("ఒక కిలో పప్పు", "1 kg dal", "Toor Dal", "పప్పు", 1, "kg", 13),
    ("ఐదు గుడ్లు", "5 eggs", "Eggs", "గుడ్లు", 5, "", 15),
    ("మూడు కిలోల పంచదార, ఒక లీటర్ నూనె", "3 kg sugar, 1 litre oil", None, None, None, None, None),
    ("నాలుగు బిస్కెట్ ప్యాకెట్లు", "4 packets biscuits", "Parle G Biscuits", "బిస్కెట్", 4, "packets", 10),
    ("రెండు ప్యాకెట్లు బిస్కెట్", "2 packets biscuits", "Parle G Biscuits", "బిస్కెట్", 2, "packets", 10),
    ("మూడు సబ్బులు", "3 soap", "Soap", "సబ్బు", 3, "", AMB),
    ("రెండు కిలోల పంచదార", "2 kg sugar", "Sugar", "పంచదార", 2, "kg", 9),
    ("ఆరు గుడ్లు", "6 eggs", "Eggs", "గుడ్లు", 6, "", 15),
    ("ఒక కిలో బియ్యం", "1 kg rice", "Rice", "బియ్యం", 1, "kg", 1),
    ("పది గుడ్లు", "10 eggs", "Eggs", "గుడ్లు", 10, "", 15),
    ("రెండు లీటర్ల నూనె", "2 litres oil", "Sunflower Oil", "నూనె", 2, "litres", 8),
    ("ఏడు బిస్కెట్ ప్యాకెట్లు", "7 packets biscuits", "Parle G Biscuits", "బిస్కెట్", 7, "packets", 10),
    ("అర లీటర్ పాలు", "half litre milk", "Milk", "పాలు", "0.5", "litre", 12),
    ("రెండు కిలోల బియ్యం, మూడు సబ్బులు, ఒక లీటర్ ఆయిల్, ఐదు బిస్కెట్ ప్యాకెట్లు", None, None, None, None, None, None),
    ("ఒక డజను గుడ్లు", "1 dozen eggs", "Eggs", "గుడ్లు", 1, "dozen", 15),
]
for spoken, eng, name, local, q, u, pid in tel:
    if name is None and spoken.startswith("మూడు కిలోల పంచదార"):
        add("telugu_script", "te", spoken, eng,
            [item("Sugar", "పంచదార", 3, "kg", 9), item("Sunflower Oil", "నూనె", 1, "litre", 8)])
    elif name is None:
        add("telugu_script", "te", spoken, "2 kg rice, 3 soap, 1 litre oil, 5 packets biscuits",
            [item("Rice", "బియ్యం", 2, "kg", 1), item("Soap", "సబ్బు", 3, "", AMB),
             item("Sunflower Oil", "నూనె", 1, "litre", 8), item("Parle G Biscuits", "బిస్కెట్", 5, "packets", 10)])
    else:
        exp = {"1": "1"}.get(str(q), None)
        if u == "dozen":
            exp = "12.000"
        add("telugu_script", "te", spoken, eng, [item(name, local, q, u, pid, exp)])

# 7. Roman Telugu ------------------------------------------------------------
roman = [
    ("rendu kilolu biyyam", "2 kg rice", "Rice", "biyyam", 2, "kg", 1),
    ("moodu kilolu panchadara", "3 kg sugar", "Sugar", "panchadara", 3, "kg", 9),
    ("oka litre noone", "1 litre oil", "Sunflower Oil", "noone", 1, "litre", 8),
    ("rendu litres paalu", "2 litres milk", "Milk", "paalu", 2, "litres", 12),
    ("aidu gudlu", "5 eggs", "Eggs", "gudlu", 5, "", 15),
    ("oka kilo pappu", "1 kg dal", "Toor Dal", "pappu", 1, "kg", 13),
    ("nalugu biscuit packets", "4 packets biscuits", "Parle G Biscuits", "biscuit", 4, "packets", 10),
    ("moodu sabbulu", "3 soap", "Soap", "sabbu", 3, "", AMB),
    ("rendu kilolu chakkera", "2 kg sugar", "Sugar", "chakkera", 2, "kg", 9),
    ("ara kilo pappu", "half kilo dal", "Toor Dal", "pappu", "0.5", "kilo", 13),
    ("padi gudlu", "10 eggs", "Eggs", "gudlu", 10, "", 15),
    ("oka kilo biyyam", "1 kg rice", "Rice", "biyyam", 1, "kg", 1),
    ("aaru gudlu", "6 eggs", "Eggs", "gudlu", 6, "", 15),
    ("rendu kilolu biyyam, moodu sabbulu", None, None, None, None, None, None),
    ("rendu litres noone", "2 litres oil", "Sunflower Oil", "noone", 2, "litres", 8),
    ("edu gudlu", "7 eggs", "Eggs", "gudlu", 7, "", 15),
    ("oka litre paalu", "1 litre milk", "Milk", "paalu", 1, "litre", 12),
    ("moodu kilolu pappu", "3 kg dal", "Toor Dal", "pappu", 3, "kg", 13),
    ("aidu biscuit packets", "5 packets biscuits", "Parle G Biscuits", "biscuit", 5, "packets", 10),
    ("nalugu kilolu panchadara", "4 kg sugar", "Sugar", "panchadara", 4, "kg", 9),
]
for spoken, eng, name, local, q, u, pid in roman:
    if name is None:
        add("roman_telugu", "te-Latn", spoken, "2 kg rice, 3 soap",
            [item("Rice", "biyyam", 2, "kg", 1), item("Soap", "sabbu", 3, "", AMB)])
    else:
        add("roman_telugu", "te-Latn", spoken, eng, [item(name, local, q, u, pid)])

# 8. Telugu-English code switching ---------------------------------------------
cs = [
    ("2 kg rice kavali", "2 kg rice", "Rice", 2, "kg", 1),
    ("5 Lux soaps ivvandi", "5 lux soaps", "Lux Soap", 5, "", AMB),
    ("oka litre sunflower oil", "1 litre sunflower oil", "Sunflower Oil", 1, "litre", 8),
    ("rendu packets parle g biscuits", "2 packets parle g biscuits", "Parle G Biscuits", 2, "packets", 10),
    ("3 kilos sugar and moodu eggs", None, None, None, None, None),
    ("one litre oil and two soaps", "1 litre oil and 2 soaps", None, None, None, None),
    ("rendu boost add cheyyandi", "2 boost add", "Boost", 2, "", 11),
    ("5 eggs kavali", "5 eggs", "Eggs", 5, "", 15),
    ("1 kg toor dal ivvandi", "1 kg toor dal", "Toor Dal", 1, "kg", 13),
    ("nalugu colgate toothpaste", "4 colgate toothpaste", "Colgate Toothpaste", 4, "", 14),
    ("2 litres milk kavali", "2 litres milk", "Milk", 2, "litres", 12),
    ("moodu lifebuoy soap", "3 lifebuoy soap", "Lifebuoy Soap", 3, "", 5),
    ("2 tata salt ivvandi", "2 tata salt", "Tata Salt", 2, "", AMB),
    ("half kilo sugar kavali", "half kilo sugar", "Sugar", "0.5", "kilo", 9),
    ("padi parle g biscuits", "10 parle g biscuits", "Parle G Biscuits", 10, "", 10),
]
for spoken, eng, name, q, u, pid in cs:
    if name is None and spoken.startswith("3 kilos"):
        add("code_switching", "te-en", spoken, "3 kilos sugar and 3 eggs", [item("Sugar", "", 3, "kilos", 9), item("Eggs", "", 3, "", 15)])
    elif name is None:
        add("code_switching", "te-en", spoken, eng, [item("Sunflower Oil", "", 1, "litre", 8), item("Soap", "", 2, "", AMB)])
    else:
        add("code_switching", "te-en", spoken, eng, [item(name, "", q, u, pid)])

# 9. number words ---------------------------------------------------------------
for text, name, q, pid in [
    ("twenty five eggs", "Eggs", 25, 15), ("one hundred parle g biscuits", "Parle G Biscuits", 100, 10),
    ("two hundred eggs", "Eggs", 200, 15), ("thirty colgate toothpaste", "Colgate Toothpaste", 30, 14),
    ("fifteen milk", "Milk", 15, 12), ("forty five eggs", "Eggs", 45, 15),
    ("ten boost", "Boost", 10, 11), ("eleven lifebuoy soap", "Lifebuoy Soap", 11, 5),
    ("sixty eggs", "Eggs", 60, 15), ("ninety parle g biscuits", "Parle G Biscuits", 90, 10),
    ("rendu vandalu eggs", "Eggs", 200, 15), ("moodu vandalu parle g biscuits", "Parle G Biscuits", 300, 10),
    ("iravai eggs", "Eggs", 20, 15), ("yabhai parle g biscuits", "Parle G Biscuits", 50, 10),
    ("padi eggs", "Eggs", 10, 15),
]:
    add("number_words", "en/te", text, text, [item(name, "", q, "", pid)])

# 10. LLM hallucinated quantity (must be flagged, not silently billed) ---------------
for text, name, spoken_q, llm_q, pid in [
    ("3 eggs", "Eggs", 3, 7, 15), ("2 sugar", "Sugar", 2, 9, 9), ("4 milk", "Milk", 4, 14, 12),
    ("5 boost", "Boost", 5, 8, 11), ("1 kg toor dal", "Toor Dal", 1, 6, 13),
    ("2 colgate toothpaste", "Colgate Toothpaste", 2, 22, 14), ("6 lifebuoy soap", "Lifebuoy Soap", 6, 3, 5),
    ("3 parle g biscuits", "Parle G Biscuits", 3, 33, 10), ("2 kg rice", "Sona Masoori Rice", 2, 12, 1),
    ("4 eggs", "Eggs", 4, 8, 15),
]:
    add("hallucinated_quantity", "en", text, text, [item(name, "", llm_q, "", pid, llm_q, False)])

# 11. ASR variants / catalog-aware aliases ------------------------------------------
add("asr_variants", "te", "3 bubt", "3 bubt", [item("Boost", "", 3, "", 11)])
add("asr_variants", "te", "2 bubt", "2 bubt", [item("Boost", "", 2, "", 11)])
add("asr_variants", "te", "5 bubt", "5 bubt", [item("Boost", "", 5, "", 11)])
add("asr_variants", "en", "2 biskut", "2 biscuits", [item("Parle G Biscuits", "", 2, "", 10)])
add("asr_variants", "hi", "do kilo chawal", "2 kg rice", [item("Rice", "chawal", 2, "kg", 1)])
add("asr_variants", "hi", "teen kilo cheeni", "3 kg sugar", [item("Sugar", "cheeni", 3, "kg", 9)])
add("asr_variants", "hi", "paanch ande", "5 eggs", [item("Eggs", "ande", 5, "", 15)])
add("asr_variants", "hi", "ek litre doodh", "1 litre milk", [item("Milk", "doodh", 1, "litre", 12)])
add("asr_variants", "hi", "do kilo dal", "2 kg dal", [item("Toor Dal", "dal", 2, "kg", 13)])
add("asr_variants", "hi", "char sabun", "4 soap", [item("Soap", "sabun", 4, "", AMB)])

# 12. products not in the catalog stay custom lines -----------------------------------
for text, name, q, u in [
    ("2 kg dragon fruit", "Dragon Fruit", 2, "kg"), ("3 mango juice", "Mango Juice", 3, ""),
    ("1 kg cashew nuts", "Cashew Nuts", 1, "kg"), ("2 shampoo", "Shampoo", 2, ""),
    ("4 notebooks", "Notebooks", 4, ""), ("1 litre coconut oil", "Coconut Oil", 1, "litre"),
    ("5 pens", "Pens", 5, ""), ("2 kg jaggery", "Jaggery", 2, "kg"),
    ("3 detergent", "Detergent", 3, ""), ("1 kg onions", "Onions", 1, "kg"),
]:
    add("unknown_product", "en", text, text, [item(name, "", q, u, None)])

# 13. repeated submission / retry --------------------------------------------------------
for text, name, q, u, pid in [
    ("2 kg sugar", "Sugar", 2, "kg", 9), ("3 eggs", "Eggs", 3, "", 15), ("1 litre milk", "Milk", 1, "litre", 12),
    ("2 boost", "Boost", 2, "", 11), ("4 colgate toothpaste", "Colgate Toothpaste", 4, "", 14),
    ("1 kg toor dal", "Toor Dal", 1, "kg", 13), ("5 parle g biscuits", "Parle G Biscuits", 5, "", 10),
    ("2 litres sunflower oil", "Sunflower Oil", 2, "litres", 8),
]:
    add("duplicate_submission", "en", text, text, [item(name, "", q, u, pid)], replay=True)

out = Path(__file__).resolve().parent.parent / "tests" / "data" / "voice_billing_eval_cases.json"
out.write_text(json.dumps({"catalogs": CATALOGS, "cases": cases}, ensure_ascii=False, indent=1), encoding="utf-8")
by_cat: dict[str, int] = {}
for c in cases:
    by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
print(f"wrote {len(cases)} cases, {sum(len(c['items']) for c in cases)} line items -> {out}")
for k, v in by_cat.items():
    print(f"  {k}: {v}")
