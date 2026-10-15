"""Grounded response summaries: describe only what the validated SQL result proves."""
from __future__ import annotations

from typing import Any

import sqlglot
from sqlglot import exp


_AGGREGATE_ALIASES: dict[str, tuple[str, tuple[str, ...], bool]] = {
    "sales_amount": (
        "Total billed sales",
        ("total_sales_amount", "sales_amount", "total_revenue", "revenue_total"),
        True,
    ),
    "expenses": (
        "Total expenses",
        ("total_expenses", "total_expense_amount", "expenses_total", "expense_total"),
        True,
    ),
    "profit": (
        "Total profit",
        ("total_profit", "profit_total"),
        True,
    ),
    "payments": (
        "Total payments collected",
        ("total_payments", "total_collected", "total_received", "collected_amount"),
        True,
    ),
    "units_sold": (
        "Total units sold",
        ("total_units_sold", "units_sold", "quantity_sold", "total_quantity"),
        False,
    ),
    "sales_count": (
        "Number of sales",
        ("sales_count", "invoice_count", "total_invoices", "count"),
        False,
    ),
    "customers": (
        "Number of customers",
        ("customer_count", "total_customers", "count"),
        False,
    ),
}


def _money(value: Any) -> str:
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _is_scalar_aggregate(sql: str) -> bool:
    """Only summarize a scalar result as a total if top-level SQL proves it is an aggregate."""
    try:
        statement = sqlglot.parse_one(str(sql or ""), read="postgres")
    except Exception:
        return False
    if not isinstance(statement, exp.Select) or statement.args.get("group") is not None:
        return False
    return any(
        any(isinstance(node, exp.AggFunc) for node in expression.walk())
        for expression in statement.expressions
    )


def format_query_answer(
    rows: list[dict[str, Any]],
    query_plan: dict[str, Any] | None,
    sql: str,
) -> str:
    """Generate a factual summary from returned rows without inferring row meaning."""
    if not rows:
        return "No matching records were found for your question."

    plan = query_plan if isinstance(query_plan, dict) else {}
    metric = str(plan.get("metric") or "other").casefold()
    intent = str(plan.get("intent") or "general").casefold()

    # Never present a regular record field such as invoices.total_amount as an
    # aggregate. The SQL AST must prove a single scalar aggregate without GROUP BY.
    if len(rows) == 1 and _is_scalar_aggregate(sql):
        row = rows[0]
        fields = {str(key).casefold(): key for key in row.keys()}
        spec = _AGGREGATE_ALIASES.get(metric)
        if spec is not None and intent == "aggregate":
            label, aliases, is_currency = spec
            key = next((fields[alias] for alias in aliases if alias in fields), None)
            if key is not None:
                value = _money(row[key]) if is_currency else str(row[key])
                return f"{label}: {value}."

        # A SQL COUNT alias is intrinsically a count, even where the planner does
        # not know the business noun. Do not generalize other generic column names.
        key = next((fields[name] for name in ("count", "row_count") if name in fields), None)
        if key is not None:
            return f"The query returned a count of {row[key]}."

    if len(rows) == 1:
        return (
            "The query returned one matching record. See the result table for its exact "
            "fields and values; no overall total has been inferred from a single record."
        )

    return (
        f"Found {len(rows)} matching records. See the result table for the exact "
        "values; no total has been inferred from a partial or grouped result set."
    )
