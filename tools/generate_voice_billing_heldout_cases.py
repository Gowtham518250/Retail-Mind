"""Held-out voice-billing cases: different catalog/products/phrasing from the tuning set.

Written and frozen BEFORE the held-out run; the resolver was not tuned on these.
Usage: python tools/generate_voice_billing_heldout_cases.py
"""
from __future__ import annotations

import json
from pathlib import Path

AMB = "AMBIGUOUS"
CAT = [
    (21, "Aashirvaad Atta 1kg", "pcs", "55.00"), (22, "Aashirvaad Atta 5kg", "pcs", "260.00"),
    (23, "Surf Excel 500g", "pcs", "120.00"), (24, "Vim Bar", "pcs", "10.00"),
    (25, "Maggi Noodles", "pcs", "14.00"), (26, "Amul Butter 100g", "pcs", "56.00"),
    (27, "Amul Butter 500g", "pcs", "270.00"), (28, "Fortune Oil", "l", "150.00"),
    (29, "Red Label Tea 250g", "pcs", "130.00"), (30, "Red Label Tea 500g", "pcs", "250.00"),
    (31, "Dettol Soap", "pcs", "45.00"), (32, "Basmati Rice", "kg", "105.00"),
    (33, "Jaggery", "kg", "70.00"), (34, "Curd", "kg", "60.00"), (35, "Tomato", "kg", "30.00"),
]
catalogs = {"retail2": [{"id": i, "name": n, "unit": u, "price": p, "stock": "50"} for i, n, u, p in CAT]}
cases = []


def item(name, local, qty, unit, pid, exp_qty=None, grounded=True, mismatch=False):
    return {"name_en": name, "name_local": local, "qty": str(qty), "spoken_unit": unit,
            "expect": {"product": pid, "qty": str(exp_qty if exp_qty is not None else qty),
                       "grounded": grounded, "unit_mismatch": mismatch}}


def add(spoken, english, items, lang="en"):
    cases.append({"id": f"heldout-{len(cases) + 1:03d}", "category": "heldout", "language": lang,
                  "spoken": spoken, "english": english, "catalog": "retail2", "items": items,
                  "replay_same_request": False})


add("2 maggi noodles", "2 maggi noodles", [item("Maggi Noodles", "", 2, "", 25)])
add("3 vim bar", "3 vim bar", [item("Vim Bar", "", 3, "", 24)])
add("1 surf excel", "1 surf excel", [item("Surf Excel", "", 1, "", 23)])
add("2 aashirvaad atta", "2 aashirvaad atta", [item("Aashirvaad Atta", "", 2, "", AMB)])
add("2 aashirvaad atta 5kg", "2 aashirvaad atta 5kg", [item("Aashirvaad Atta 5kg", "", 2, "", 22)])
add("1 amul butter", "1 amul butter", [item("Amul Butter", "", 1, "", AMB)])
add("4 amul butter 100g", "4 amul butter 100g", [item("Amul Butter 100g", "", 4, "", 26)])
add("2 red label tea", "2 red label tea", [item("Red Label Tea", "", 2, "", AMB)])
add("3 red label tea 250 gram", "3 red label tea 250 gram", [item("Red Label Tea 250g", "", 3, "", 29)])
add("2 litres fortune oil", "2 litres fortune oil", [item("Fortune Oil", "", 2, "litres", 28)])
add("500 ml fortune oil", "500 ml fortune oil", [item("Fortune Oil", "", 500, "ml", 28, "0.500")])
add("1 kg tomato and 2 kg jaggery", "1 kg tomato and 2 kg jaggery",
    [item("Tomato", "", 1, "kg", 35), item("Jaggery", "", 2, "kg", 33)])
add("250 grams curd", "250 grams curd", [item("Curd", "", 250, "grams", 34, "0.250")])
add("2 dettol soap and 3 vim bar", "2 dettol soap and 3 vim bar",
    [item("Dettol Soap", "", 2, "", 31), item("Vim Bar", "", 3, "", 24)])
add("2 kg basmati rice", "2 kg basmati rice", [item("Basmati Rice", "", 2, "kg", 32)])
add("half kilo tomato", "half kilo tomato", [item("Tomato", "", "0.5", "kilo", 35)])
add("3 dettol soap, 2 maggi noodles, 1 surf excel, 2 kg tomato",
    "3 dettol soap, 2 maggi noodles, 1 surf excel, 2 kg tomato",
    [item("Dettol Soap", "", 3, "", 31), item("Maggi Noodles", "", 2, "", 25),
     item("Surf Excel", "", 1, "", 23), item("Tomato", "", 2, "kg", 35)])
add("2 atta", "2 atta", [item("Atta", "", 2, "", AMB)])
add("5 butter", "5 butter", [item("Butter", "", 5, "", AMB)])
add("2 tea", "2 tea", [item("Tea", "", 2, "", AMB)])
add("3 maggi noodles", "3 maggi noodles", [item("Maggi Noodles", "", 8, "", 25, 8, False)])
add("2 kg dettol soap", "2 kg dettol soap", [item("Dettol Soap", "", 2, "kg", 31, 2, True, True)])
add("1 dozen maggi noodles", "1 dozen maggi noodles", [item("Maggi Noodles", "", 1, "dozen", 25, "12.000")])
add("రెండు కిలోల టమాటా", "2 kg tomato", [item("Tomato", "టమాటా", 2, "kg", 35)], "te")
add("మూడు మ్యాగీ ప్యాకెట్లు", "3 packets maggi noodles", [item("Maggi Noodles", "మ్యాగీ", 3, "packets", 25)], "te")
add("oka kilo tomato", "1 kg tomato", [item("Tomato", "tomato", 1, "kg", 35)], "te-Latn")
add("rendu dettol soap", "2 dettol soap", [item("Dettol Soap", "", 2, "", 31)], "te-Latn")
add("2 kg jaggery kavali", "2 kg jaggery", [item("Jaggery", "", 2, "kg", 33)], "te-en")
add("2 kg garlic", "2 kg garlic", [item("Garlic", "", 2, "kg", None)])
add("3 colgate", "3 colgate", [item("Colgate", "", 3, "", None)])
add("2 amul butter 500g and 3 amul butter 100g", "2 amul butter 500g and 3 amul butter 100g",
    [item("Amul Butter 500g", "", 2, "", 27), item("Amul Butter 100g", "", 3, "", 26)])
add("ten maggi noodles", "ten maggi noodles", [item("Maggi Noodles", "", 10, "", 25)])
add("twenty vim bar", "twenty vim bar", [item("Vim Bar", "", 20, "", 24)])
add("1.5 kg jaggery", "1.5 kg jaggery", [item("Jaggery", "", "1.5", "kg", 33)])
add("750 grams curd", "750 grams curd", [item("Curd", "", 750, "grams", 34, "0.750")])
add("4 fortune oil", "4 fortune oil", [item("Fortune Oil", "", 4, "", 28)])
add("3 packets vim bar", "3 packets vim bar", [item("Vim Bar", "", 3, "packets", 24)])
add("2 tomato", "2 tomato", [item("Tomato", "", 2, "", 35)])
add("6 curd", "6 curd", [item("Curd", "", 6, "", 34)])

out = Path(__file__).resolve().parent.parent / "tests" / "data" / "voice_billing_heldout_cases.json"
out.write_text(json.dumps({"catalogs": catalogs, "cases": cases}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {len(cases)} held-out cases, {sum(len(c['items']) for c in cases)} line items -> {out}")
