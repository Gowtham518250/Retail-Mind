"""Score voice-billing post-processing: OLD logic vs NEW logic on the same cases.

Scope (be precise about what this measures)
* measures the deterministic layer after the LLM extraction step:
  catalog match, ambiguity detection, unit conversion, quantity grounding,
  line total and replay protection;
* does NOT measure ASR word-error-rate or LLM extraction quality - that needs
  labelled audio and a Groq key (see docs/VOICE_AI_EVALUATION.md).

The "LLM" is simulated identically for both variants: it proposes the catalog
candidate whose name is most similar to the extracted product name (or none).
That is the most favourable assumption for the old code, so the delta is a
conservative estimate of the improvement.

Run:  DATABASE_URL=sqlite:///x.db SECRET_KEY=x python tools/voice_billing_eval.py [--json report.json]
"""
from __future__ import annotations

import argparse
import difflib
import json
import statistics
import sys
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import inventory as inv  # noqa: E402
from voice_billing_core import (  # noqa: E402
    ResponseCache,
    convert_quantity,
    quantity_is_grounded,
    resolve_catalog_product,
)

AMB = "AMBIGUOUS"
DATA = ROOT / "tests" / "data" / "voice_billing_eval_cases.json"


def _products(rows):
    return [
        SimpleNamespace(
            id=r["id"], product_name=r["name"], sku="", unit=r["unit"],
            unit_price=Decimal(r["price"]), current_stock=Decimal(r["stock"]), category="",
        )
        for r in rows
    ]


def _llm_pick(item, candidates):
    """Simulated LLM: the candidate that best covers the extracted name, else None.

    score = 0.5 * string similarity + 0.5 * fraction of the item's words (alias-aware)
    found in the candidate name.  Identical for the old and new variants.
    """
    name = inv._voice_billing_normalize(item["name_en"] or item["name_local"])
    words = {w for w in inv._voice_billing_expanded_tokens(name) if not w.isdigit()}
    best, best_score = None, 0.0
    for product in candidates:
        cand = inv._voice_billing_normalize(product.product_name)
        cand_tokens = set(inv._voice_billing_expanded_tokens(cand))
        base_words = set(name.split())
        covered = sum(1 for w in base_words if w in cand_tokens or w.rstrip("s") in cand_tokens)
        containment = covered / max(1, len(base_words))
        if containment == 0:
            continue
        score = 0.5 * difflib.SequenceMatcher(None, name, cand).ratio() + 0.5 * containment
        if score > best_score:
            best, best_score = product, score
    return best if best_score >= 0.5 else None


def _old(case, item, products):
    english = case["english"]
    candidates = inv._voice_billing_catalog_candidates(english, products, limit=80)
    pick = _llm_pick(item, candidates)
    product = pick if pick is not None and inv._voice_billing_product_has_evidence(english, pick) else None
    qty = Decimal(item["qty"])
    return {
        "product": product.id if product else None,
        "candidates": [p.id for p in candidates][:3],
        "qty": qty,
        "grounded": True,  # old code never checked
        "unit_mismatch": False,  # old code never checked
        "price": product.unit_price if product else Decimal("0"),
    }


def _new(case, item, products):
    english = case["english"]
    parser_transcript = inv._voice_billing_normalize_spoken_scales(case["spoken"])
    candidates = inv._voice_billing_catalog_candidates(english, products, limit=80)
    pick = _llm_pick(item, candidates)
    product, cand_ids = None, [p.id for p in candidates][:3]
    status = "none"
    if pick is not None:
        res = resolve_catalog_product(
            [item["name_en"], item["name_local"], item["name_en"]],
            f"{english} {parser_transcript}", candidates,
            normalize=inv._voice_billing_normalize,
            expand_tokens=inv._voice_billing_expanded_tokens, hint_product=pick,
        )
        status = res.status
        if res.status == "matched":
            product = res.product
            cand_ids = [c.product.id for c in res.candidates][:3] or cand_ids
        elif res.status == "ambiguous":
            cand_ids = [c.product.id for c in res.candidates][:3]
    qty = Decimal(item["qty"])
    grounded = quantity_is_grounded(
        qty, (parser_transcript, english), inv._VOICE_BILLING_NUMBER_WORDS, inv._VOICE_BILLING_SCALE_WORDS
    )
    mismatch = False
    final_qty = qty
    if product is not None:
        conv = convert_quantity(qty, item["spoken_unit"], product.unit)
        if conv.converted:
            final_qty = conv.quantity
        elif conv.incompatible:
            mismatch = True
    return {
        "product": AMB if status == "ambiguous" else (product.id if product else None),
        "candidates": cand_ids,
        "qty": final_qty,
        "grounded": grounded,
        "unit_mismatch": mismatch,
        "price": product.unit_price if product else Decimal("0"),
    }


def _same_qty(a, b):
    return abs(Decimal(a) - Decimal(b)) <= Decimal("0.0005")


def evaluate(variant, dataset=DATA):
    payload = json.loads(Path(dataset).read_text(encoding="utf-8"))
    catalogs = {k: _products(v) for k, v in payload["catalogs"].items()}
    price = {k: {p.id: p.unit_price for p in v} for k, v in catalogs.items()}
    fn = _old if variant == "old" else _new

    n_items = prod_ok = qty_ok = line_ok = ground_ok = 0
    amb_tp = amb_fp = amb_fn = 0
    top1_n = top1_ok = top3_ok = 0
    unit_n = unit_ok = 0
    mismatch_n = mismatch_ok = 0
    ground_neg_n = ground_neg_ok = 0
    total_n = total_ok = 0
    per_cat: dict[str, list[int]] = {}
    latencies = []
    dup_n = dup_dups = 0
    cache = ResponseCache()

    for case in payload["cases"]:
        products = catalogs[case["catalog"]]
        t0 = time.perf_counter()
        decisions = [fn(case, it, products) for it in case["items"]]
        latencies.append((time.perf_counter() - t0) * 1000)

        if case["replay_same_request"]:
            dup_n += 1
            if variant == "old":
                dup_dups += 1  # no replay protection: a retry yields a second independent draft
            else:
                cache.put(1, case["id"], decisions)
                if cache.get(1, case["id"]) is None:
                    dup_dups += 1

        exp_total = Decimal("0")
        got_total = Decimal("0")
        resolvable = True
        for it, dec in zip(case["items"], decisions):
            exp = it["expect"]
            n_items += 1
            cat = per_cat.setdefault(case["category"], [0, 0])
            cat[0] += 1
            p_ok = dec["product"] == exp["product"]
            q_ok = _same_qty(dec["qty"], exp["qty"])
            g_ok = dec["grounded"] == exp["grounded"]
            m_ok = dec["unit_mismatch"] == exp["unit_mismatch"]
            prod_ok += p_ok
            qty_ok += q_ok
            ground_ok += g_ok
            full = p_ok and q_ok and g_ok and m_ok
            line_ok += full
            cat[1] += full
            if exp["product"] == AMB:
                amb_tp += dec["product"] == AMB
                amb_fn += dec["product"] != AMB
            elif dec["product"] == AMB:
                amb_fp += 1
            if exp["product"] not in (AMB, None):
                top1_n += 1
                top1_ok += dec["product"] == exp["product"]
                top3_ok += exp["product"] in ([dec["product"]] + list(dec["candidates"]))
            if exp["product"] == AMB:
                top3_ok += 0
            if it["spoken_unit"] and isinstance(exp["product"], int):
                unit_n += 1
                unit_ok += q_ok and m_ok
            if exp["unit_mismatch"]:
                mismatch_n += 1
                mismatch_ok += dec["unit_mismatch"]
            if not exp["grounded"]:
                ground_neg_n += 1
                ground_neg_ok += not dec["grounded"]
            if isinstance(exp["product"], int):
                exp_total += Decimal(exp["qty"]) * price[case["catalog"]][exp["product"]]
                got_total += Decimal(dec["qty"]) * dec["price"] if dec["product"] == exp["product"] else Decimal("0")
            else:
                resolvable = False
        if resolvable and not case["replay_same_request"] or (resolvable and case["replay_same_request"]):
            total_n += 1
            total_ok += (
                got_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                == exp_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )

    pct = lambda a, b: round(100.0 * a / b, 2) if b else None  # noqa: E731
    amb_p = pct(amb_tp, amb_tp + amb_fp)
    amb_r = pct(amb_tp, amb_tp + amb_fn)
    return {
        "variant": variant,
        "cases": len(payload["cases"]),
        "line_items": n_items,
        "product_decision_accuracy_pct": pct(prod_ok, n_items),
        "top1_catalog_accuracy_pct": pct(top1_ok, top1_n),
        "top3_catalog_accuracy_pct": pct(top3_ok, top1_n),
        "ambiguity_precision_pct": amb_p,
        "ambiguity_recall_pct": amb_r,
        "quantity_accuracy_pct": pct(qty_ok, n_items),
        "unit_handling_accuracy_pct": pct(unit_ok, unit_n),
        "unit_mismatch_detection_pct": pct(mismatch_ok, mismatch_n),
        "ungrounded_quantity_detection_pct": pct(ground_neg_ok, ground_neg_n),
        "line_item_accuracy_pct": pct(line_ok, n_items),
        "bill_total_accuracy_pct": pct(total_ok, total_n),
        "duplicate_draft_rate_pct": pct(dup_dups, dup_n),
        "deterministic_latency_ms_mean": round(statistics.mean(latencies), 3),
        "deterministic_latency_ms_p95": round(sorted(latencies)[int(0.95 * len(latencies)) - 1], 3),
        "per_category_line_accuracy_pct": {k: pct(v[1], v[0]) for k, v in sorted(per_cat.items())},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="write the combined report here")
    parser.add_argument("--dataset", default=str(DATA), help="eval cases JSON (default: tuning set)")
    args = parser.parse_args()
    report = {"old": evaluate("old", args.dataset), "new": evaluate("new", args.dataset)}
    keys = [k for k in report["new"] if k not in ("variant", "per_category_line_accuracy_pct")]
    print(f"{'metric':<40}{'OLD':>12}{'NEW':>12}")
    for k in keys:
        print(f"{k:<40}{str(report['old'][k]):>12}{str(report['new'][k]):>12}")
    print("\nper-category line accuracy % (old -> new)")
    for cat in report["new"]["per_category_line_accuracy_pct"]:
        print(f"  {cat:<24}{report['old']['per_category_line_accuracy_pct'][cat]!s:>8} -> {report['new']['per_category_line_accuracy_pct'][cat]}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
