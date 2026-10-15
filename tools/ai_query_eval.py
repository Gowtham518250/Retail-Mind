"""Deterministic evaluator for labelled Retail Mind AI query cases.

The runner scores exported cases/results; it does not call production APIs and
therefore cannot expose production data or credentials.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


_MONEY_ONLY = re.compile(
    r"^\s*(?:(?:₹|rs\.?|inr)\s*)?[-+]?\d[\d,]*(?:\.\d+)?\s*$",
    re.IGNORECASE,
)


def _money_only(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not _MONEY_ONLY.fullmatch(text):
        return None
    text = re.sub(r"^(?:₹|rs\.?|inr)\s*", "", text, flags=re.IGNORECASE)
    try:
        return Decimal(text.replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def normalize_answer(value: Any) -> str:
    """Normalize whitespace, case, Unicode compatibility characters and punctuation."""
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    text = text.casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def answer_matches(expected: Any, actual: Any, tolerance: Decimal = Decimal("0.01")) -> bool:
    expected_money = _money_only(expected)
    actual_money = _money_only(actual)
    if expected_money is not None and actual_money is not None:
        return abs(expected_money - actual_money) <= tolerance
    return normalize_answer(expected) == normalize_answer(actual)


def _as_bool(value: Any) -> bool:
    return value is True


def _source_ids(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def evaluate_cases(cases: Iterable[dict[str, Any]], results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Compare labelled cases with captured answers and safety/source metadata.

    Case fields:
      case_id, expected_answer (optional), requires_clarification (bool),
      expected_date_range (optional mapping), expected_source_record_ids (optional list),
      must_be_shop_scoped (default true).

    Result fields:
      case_id, answer, needs_clarification, shop_scope_valid, date_range,
      source_record_ids.
    """
    case_rows = list(cases)
    result_rows = list(results)
    case_map: dict[str, dict[str, Any]] = {}
    result_map: dict[str, dict[str, Any]] = {}

    for row in case_rows:
        case_id = str(row.get("case_id", "")).strip()
        if not case_id:
            raise ValueError("Every case needs a non-empty case_id.")
        if case_id in case_map:
            raise ValueError(f"Duplicate case_id in cases: {case_id}")
        case_map[case_id] = row

    if not case_map:
        raise ValueError("The labelled case set must contain at least one case.")

    for row in result_rows:
        result_id = str(row.get("case_id", "")).strip()
        if not result_id:
            raise ValueError("Every result needs a non-empty case_id.")
        if result_id in result_map:
            raise ValueError(f"Duplicate case_id in results: {result_id}")
        if result_id not in case_map:
            raise ValueError(f"Result has no labelled case: {result_id}")
        result_map[result_id] = row

    answer_total = answer_correct = 0
    clarification_total = clarification_correct = 0
    scope_total = scope_correct = 0
    date_total = date_correct = 0
    expected_source_total = covered_source_total = 0
    predicted_source_total = relevant_predicted_source_total = 0
    critical_passes = 0

    for case_id, case in case_map.items():
        result = result_map.get(case_id, {})
        is_critical_pass = True

        expected_answer = case.get("expected_answer")
        if expected_answer is not None and str(expected_answer).strip() != "":
            answer_total += 1
            matched = answer_matches(expected_answer, result.get("answer"))
            answer_correct += int(matched)
            is_critical_pass = is_critical_pass and matched

        expected_clarification = _as_bool(case.get("requires_clarification", False))
        clarification_matches = (
            _as_bool(result.get("needs_clarification")) == expected_clarification
        )
        clarification_total += 1
        clarification_correct += int(clarification_matches)
        is_critical_pass = is_critical_pass and clarification_matches

        if case.get("must_be_shop_scoped", True):
            scope_total += 1
            scoped = _as_bool(result.get("shop_scope_valid"))
            scope_correct += int(scoped)
            is_critical_pass = is_critical_pass and scoped

        expected_range = case.get("expected_date_range")
        if expected_range is not None:
            date_total += 1
            range_matches = result.get("date_range") == expected_range
            date_correct += int(range_matches)
            is_critical_pass = is_critical_pass and range_matches

        expected_sources = _source_ids(case.get("expected_source_record_ids"))
        if expected_sources:
            actual_sources = _source_ids(result.get("source_record_ids"))
            covered = expected_sources & actual_sources
            exact_sources = actual_sources == expected_sources
            expected_source_total += len(expected_sources)
            covered_source_total += len(covered)
            predicted_source_total += len(actual_sources)
            relevant_predicted_source_total += len(actual_sources & expected_sources)
            # Evidence cases are labelled against canonical shop records. An extra
            # returned record is a false positive, even when every expected ID is
            # present; critical accuracy must therefore require exact source sets.
            if case.get("require_exact_source_record_ids", True):
                is_critical_pass = is_critical_pass and exact_sources
            else:
                is_critical_pass = is_critical_pass and expected_sources.issubset(actual_sources)

        critical_passes += int(is_critical_pass)

    return {
        "total_cases": len(case_map),
        "results_received": len(result_map),
        "missing_results": len(case_map) - len(result_map),
        "answer_cases": answer_total,
        "answer_accuracy": _ratio(answer_correct, answer_total),
        "clarification_accuracy": _ratio(clarification_correct, clarification_total),
        "shop_scope_accuracy": _ratio(scope_correct, scope_total),
        "date_range_accuracy": _ratio(date_correct, date_total),
        "source_recall": _ratio(covered_source_total, expected_source_total),
        "source_precision": _ratio(relevant_predicted_source_total, predicted_source_total),
        "critical_pass_rate": _ratio(critical_passes, len(case_map)),
    }


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: each line must be a JSON object.")
            rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, help="JSONL file with labelled questions and expected facts.")
    parser.add_argument("--results", required=True, help="JSONL file with captured AI answers and verification metadata.")
    parser.add_argument(
        "--min-critical-pass-rate",
        type=float,
        default=0.0,
        help="Fail if the critical pass rate is below this fraction (for example 0.85).",
    )
    parser.add_argument("--min-answer-accuracy", type=float, default=None)
    parser.add_argument("--min-shop-scope-accuracy", type=float, default=None)
    parser.add_argument("--min-date-range-accuracy", type=float, default=None)
    parser.add_argument("--min-source-precision", type=float, default=None)
    parser.add_argument("--min-source-recall", type=float, default=None)
    args = parser.parse_args(argv)
    for name in (
        "min_critical_pass_rate",
        "min_answer_accuracy",
        "min_shop_scope_accuracy",
        "min_date_range_accuracy",
        "min_source_precision",
        "min_source_recall",
    ):
        value = getattr(args, name)
        if value is not None and not 0.0 <= value <= 1.0:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1.")
    try:
        report = evaluate_cases(read_jsonl(args.cases), read_jsonl(args.results))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    gates = {
        "critical_pass_rate": args.min_critical_pass_rate,
        "answer_accuracy": args.min_answer_accuracy,
        "shop_scope_accuracy": args.min_shop_scope_accuracy,
        "date_range_accuracy": args.min_date_range_accuracy,
        "source_precision": args.min_source_precision,
        "source_recall": args.min_source_recall,
    }
    failures = []
    for metric, minimum in gates.items():
        if minimum is None:
            continue
        value = report.get(metric)
        if value is None or value < minimum:
            failures.append({
                "metric": metric,
                "minimum": minimum,
                "actual": value,
            })
    report["release_gate"] = {
        "passed": not failures,
        "thresholds": {key: val for key, val in gates.items() if val is not None},
        "failures": failures,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
