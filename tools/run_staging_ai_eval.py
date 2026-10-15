"""Read-only staging evaluation of Retail Mind AI answers against canonical invoices.

Required environment:
  STAGING_BASE_URL
  STAGING_TEST_EMAIL
  STAGING_TEST_PASSWORD

This script only logs in, reads invoices, and submits read-only AI queries. It
never creates, edits, pays, restores, or deletes financial records.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from query_safety import validate_read_only_tenant_sql
from tools.ai_query_eval import evaluate_cases
from tools.staging_config import validate_staging_base_url
MONEY_FIELDS = (
    "total_sales_amount",
    "sales_amount",
    "total_revenue",
    "revenue_total",
    "total_amount",
    "total",
    "amount",
)
ID_FIELDS = ("invoice_number", "invoiceNumber", "invoice_no", "bill_number", "number")
DATE_FIELDS = ("invoice_date", "invoiceDate", "business_date", "sale_date", "date")


def _as_text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Expected a numeric value, received {value!r}.")
    try:
        return Decimal(str(value).replace(",", "")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Expected a numeric value, received {value!r}.") from exc


def _status(value: Any) -> str:
    return _as_text(value).split(".")[-1].upper()


def _field(row: dict[str, Any], choices: tuple[str, ...]) -> Any:
    lookup = {str(key).casefold(): value for key, value in row.items()}
    for name in choices:
        if name.casefold() in lookup:
            return lookup[name.casefold()]
    return None


def _eligible_invoice(row: dict[str, Any]) -> bool:
    return _status(row.get("status")) not in {
        "DRAFT", "CANCELLED", "CANCELED", "VOID", "DELETED"
    }


def _fetch_invoices(session: requests.Session, base_url: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page_size = 100
    for page in range(100):
        response = session.get(
            f"{base_url}/api/invoices/",
            params={"skip": page * page_size, "limit": page_size},
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload if isinstance(payload, list) else (
            payload.get("invoices", payload.get("items", []))
            if isinstance(payload, dict) else []
        )
        if not isinstance(rows, list):
            raise ValueError("The invoices API returned an unexpected response shape.")
        result.extend(dict(row) for row in rows if isinstance(row, dict))
        if len(rows) < page_size:
            return result
    raise ValueError("Invoice scan exceeded 10,000 rows; narrow the staging dataset before evaluation.")


def _login(base_url: str, email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{base_url}/auth/login",
        json={"email": email, "password": password},
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token") or payload.get("token")
    if not token:
        raise ValueError("Login succeeded but the response contained no access token.")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _ask(session: requests.Session, base_url: str, question: str) -> dict[str, Any]:
    response = session.post(
        f"{base_url}/askquery",
        data={"query": question, "language_code": "en"},
        timeout=120,
    )
    if response.status_code != 200:
        raise ValueError(
            f"AI query failed with HTTP {response.status_code}: "
            f"{response.text[:350]}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("AI query returned an unexpected response shape.")
    return payload


def _query_sql_is_shop_scoped(sql: Any) -> tuple[bool, str]:
    candidate = _as_text(sql)
    if not candidate:
        return False, "missing_sql"
    if candidate.upper().startswith("DIRECT_KPI:"):
        # Fast KPI code paths are separately checked by the offline contract tests;
        # the live result is still compared to invoices read through this shop's
        # authenticated canonical invoice endpoint.
        return True, "authenticated_fast_kpi_checked_against_invoice_api"
    catalog_path = ROOT / "rag_table_catalog.json"
    try:
        with catalog_path.open("r", encoding="utf-8") as stream:
            catalog = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return False, "missing_or_invalid_schema_catalog"
    return validate_read_only_tenant_sql(candidate, catalog)


def _choose_evaluation_day(invoices: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in invoices:
        if not _eligible_invoice(row):
            continue
        raw_date = _field(row, DATE_FIELDS)
        parsed = _as_text(raw_date)[:10]
        try:
            parsed_date = date.fromisoformat(parsed)
        except ValueError:
            continue
        grouped.setdefault(parsed_date.isoformat(), []).append(row)

    if not grouped:
        raise ValueError(
            "No eligible invoices with a valid date were found in this staging shop. "
            "Use a dedicated staging account seeded with a few non-draft invoices."
        )

    # Prefer the newest non-empty date with a small result set so the detailed
    # query can verify every source row rather than a truncated page.
    for day in sorted(grouped, reverse=True):
        if len(grouped[day]) <= 25:
            return day, grouped[day]
    return min(grouped.items(), key=lambda pair: (len(pair[1]), pair[0]))


def _extract_amount(payload: dict[str, Any]) -> Decimal:
    rows = payload.get("results")
    if isinstance(rows, list) and rows:
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = _field(row, MONEY_FIELDS)
            if value is not None:
                return _decimal(value)

    answer = _as_text(payload.get("answer") or payload.get("message"))
    matches = re.findall(
        r"(?:₹|Rs\.?|INR)\s*([-+]?\d[\d,]*(?:\.\d{1,2})?)",
        answer,
        flags=re.IGNORECASE,
    )
    if matches:
        return _decimal(matches[-1])
    raise ValueError(
        "AI response contained no auditable monetary result in results[] or its answer text."
    )


def run_evaluation() -> dict[str, Any]:
    base_url = validate_staging_base_url(os.environ.get("STAGING_BASE_URL"))
    email = os.environ.get("STAGING_TEST_EMAIL", "").strip()
    password = os.environ.get("STAGING_TEST_PASSWORD", "")
    if not email or not password:
        raise ValueError("STAGING_TEST_EMAIL and STAGING_TEST_PASSWORD are required.")

    with _login(base_url, email, password) as session:
        invoices = _fetch_invoices(session, base_url)
        day, expected_rows = _choose_evaluation_day(invoices)
        expected_by_id = {
            _as_text(_field(row, ID_FIELDS)): row
            for row in expected_rows
            if _as_text(_field(row, ID_FIELDS))
        }
        if not expected_by_id:
            raise ValueError("Eligible staging invoices have no stable invoice_number values.")

        expected_total = sum(
            (_decimal(row.get("total_amount")) for row in expected_by_id.values()),
            start=Decimal("0.00"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expected_ids = set(expected_by_id)

        detail_question = (
            f"List the invoice_number, invoice_date, and total_amount "
            f"for invoices dated {day}."
        )
        detail = _ask(session, base_url, detail_question)
        detail_sql = detail.get("generated_sql") or detail.get("sql")
        detail_scope_valid, detail_scope_reason = _query_sql_is_shop_scoped(detail_sql)
        detail_rows = detail.get("results")
        if not isinstance(detail_rows, list):
            detail_rows = []
        actual_ids: set[str] = set()
        detail_rows_valid = bool(detail_rows)
        for row in detail_rows:
            if not isinstance(row, dict):
                detail_rows_valid = False
                continue
            invoice_id = _as_text(_field(row, ID_FIELDS))
            if not invoice_id:
                detail_rows_valid = False
                continue
            actual_ids.add(invoice_id)
            source_date = _as_text(_field(row, DATE_FIELDS))[:10]
            if source_date != day or invoice_id not in expected_by_id:
                detail_rows_valid = False
                continue
            try:
                actual_amount = _decimal(_field(row, MONEY_FIELDS))
                expected_amount = _decimal(expected_by_id[invoice_id].get("total_amount"))
                if actual_amount != expected_amount:
                    detail_rows_valid = False
            except ValueError:
                detail_rows_valid = False

        detail_scope_valid = bool(
            detail_scope_valid and detail_rows_valid and actual_ids == expected_ids
            and day in str(detail_sql or "")
        )

        aggregate_question = f"What was the total billed sales amount for {day}?"
        aggregate = _ask(session, base_url, aggregate_question)
        aggregate_sql = aggregate.get("generated_sql") or aggregate.get("sql")
        aggregate_scope_valid, aggregate_scope_reason = _query_sql_is_shop_scoped(aggregate_sql)
        if not str(aggregate_sql or "").upper().startswith("DIRECT_KPI:"):
            aggregate_scope_valid = bool(
                aggregate_scope_valid and day in str(aggregate_sql or "")
            )
        actual_total = _extract_amount(aggregate)

        expected_range = {"start": day, "end": day}
        cases = [
            {
                "case_id": "record-level-source-verification",
                "expected_answer": None,
                "requires_clarification": False,
                "expected_date_range": expected_range,
                "expected_source_record_ids": sorted(expected_ids),
            },
            {
                "case_id": "aggregate-sales-total",
                "expected_answer": f"{expected_total:.2f}",
                "requires_clarification": False,
                "expected_date_range": expected_range,
            },
        ]
        results = [
            {
                "case_id": "record-level-source-verification",
                "needs_clarification": bool(detail.get("needs_clarification", False)),
                "shop_scope_valid": detail_scope_valid,
                "date_range": expected_range if detail_scope_valid else None,
                "source_record_ids": sorted(actual_ids),
            },
            {
                "case_id": "aggregate-sales-total",
                "answer": f"{actual_total:.2f}",
                "needs_clarification": bool(aggregate.get("needs_clarification", False)),
                "shop_scope_valid": bool(aggregate_scope_valid),
                "date_range": expected_range if aggregate_scope_valid else None,
            },
        ]
        report = evaluate_cases(cases, results)
        report["evidence"] = {
            "environment": "staging",
            "query_engine_version": detail.get("query_engine_version"),
            "evaluation_date": day,
            "eligible_invoice_count": len(expected_ids),
            "expected_total": f"{expected_total:.2f}",
            "actual_total": f"{actual_total:.2f}",
            "record_source_set_exact": actual_ids == expected_ids,
            "detail_sql_scope_check": detail_scope_reason,
            "aggregate_sql_scope_check": aggregate_scope_reason,
            "detail_answer_preview": _as_text(detail.get("answer") or detail.get("message"))[:300],
            "aggregate_answer_preview": _as_text(aggregate.get("answer") or aggregate.get("message"))[:300],
        }
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--min-critical-pass-rate", type=float, default=1.0)
    parser.add_argument("--min-answer-accuracy", type=float, default=1.0)
    parser.add_argument("--min-shop-scope-accuracy", type=float, default=1.0)
    parser.add_argument("--min-date-range-accuracy", type=float, default=1.0)
    parser.add_argument("--min-source-precision", type=float, default=1.0)
    parser.add_argument("--min-source-recall", type=float, default=1.0)
    args = parser.parse_args(argv)
    thresholds = {
        "critical_pass_rate": args.min_critical_pass_rate,
        "answer_accuracy": args.min_answer_accuracy,
        "shop_scope_accuracy": args.min_shop_scope_accuracy,
        "date_range_accuracy": args.min_date_range_accuracy,
        "source_precision": args.min_source_precision,
        "source_recall": args.min_source_recall,
    }
    if any(not 0.0 <= value <= 1.0 for value in thresholds.values()):
        parser.error("All minimum thresholds must be between 0 and 1.")
    try:
        report = run_evaluation()
    except (OSError, ValueError, requests.RequestException) as exc:
        report = {"release_gate": {"passed": False, "error": str(exc)}}
        rendered = json.dumps(report, indent=2, sort_keys=True)
        print(rendered)
        if args.output:
            args.output.write_text(rendered + "\n", encoding="utf-8")
        return 1

    failures = []
    for metric, minimum in thresholds.items():
        actual = report.get(metric)
        if actual is None or actual < minimum:
            failures.append({"metric": metric, "minimum": minimum, "actual": actual})
    report["release_gate"] = {
        "passed": not failures,
        "thresholds": thresholds,
        "failures": failures,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
