from decimal import Decimal

import pytest

from tools.ai_query_eval import answer_matches, evaluate_cases, normalize_answer


def test_answer_comparison_normalizes_text_and_currency_amounts():
    assert normalize_answer("  TOTAL   SALES — TODAY ") == "total sales today"
    assert answer_matches("₹1,200.00", "Rs 1,200")
    assert answer_matches("1200.00", "1200.01")
    assert not answer_matches("1200.00", "1200.02")


def test_evaluator_reports_answer_scope_date_clarification_and_source_metrics():
    cases = [
        {
            "case_id": "sales-today",
            "expected_answer": "₹1200.00",
            "requires_clarification": False,
            "expected_date_range": {"start": "2026-10-15", "end": "2026-10-15"},
            "expected_source_record_ids": ["INV-101", "INV-102"],
        },
        {
            "case_id": "unknown-period",
            "expected_answer": None,
            "requires_clarification": True,
            "must_be_shop_scoped": True,
        },
    ]
    results = [
        {
            "case_id": "sales-today",
            "answer": "Rs 1,200",
            "needs_clarification": False,
            "shop_scope_valid": True,
            "date_range": {"start": "2026-10-15", "end": "2026-10-15"},
            "source_record_ids": ["INV-101", "INV-102", "INV-EXTRA"],
        },
        {
            "case_id": "unknown-period",
            "answer": "Please specify the period.",
            "needs_clarification": True,
            "shop_scope_valid": True,
        },
    ]

    report = evaluate_cases(cases, results)

    assert report["total_cases"] == 2
    assert report["answer_accuracy"] == 1.0
    assert report["clarification_accuracy"] == 1.0
    assert report["shop_scope_accuracy"] == 1.0
    assert report["date_range_accuracy"] == 1.0
    assert report["source_recall"] == 1.0
    assert report["source_precision"] == 0.6667
    assert report["critical_pass_rate"] == 1.0


def test_missing_answer_result_fails_critical_pass_and_scope():
    cases = [{"case_id": "one", "expected_answer": "42", "requires_clarification": False}]
    report = evaluate_cases(cases, [])
    assert report["missing_results"] == 1
    assert report["answer_accuracy"] == 0.0
    assert report["shop_scope_accuracy"] == 0.0
    assert report["critical_pass_rate"] == 0.0


def test_duplicate_and_unknown_ids_are_rejected():
    with pytest.raises(ValueError, match="Duplicate case_id"):
        evaluate_cases([{"case_id": "x"}, {"case_id": "x"}], [])
    with pytest.raises(ValueError, match="no labelled case"):
        evaluate_cases([{"case_id": "x"}], [{"case_id": "other"}])


def test_empty_labelled_case_set_is_rejected():
    with pytest.raises(ValueError, match="at least one case"):
        evaluate_cases([], [])
