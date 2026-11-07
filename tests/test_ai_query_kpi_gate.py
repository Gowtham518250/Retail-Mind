"""The deterministic KPI shortcut must only answer PURE shop-wide KPIs.

"sales of rice today" used to be answered with the whole shop's total, silently
dropping the product filter. Qualified questions must go to the schema-SQL path.
"""
import pytest

import query_retrival as qr


def _fast(question: str) -> bool:
    return qr._can_use_fast_business_query(question, qr._resolve_explicit_date_scope(question))


@pytest.mark.parametrize("question", [
    "sales today",
    "what is today's sales",
    "total sales yesterday",
    "what were my total sales yesterday?",
    "sales this week",
    "sales last month",
    "sales on 5th november",
    "sales from 1 november to 5 november",
    "sales last 14 days",
    "how many sales this month",
    "how many items were sold today",
    "total expenses this month",
    "what is the total sales amount for the last 7 days",
    "How much sales did my shop make in the last 1 month up to today?",
    "how much did my shop earn today in sales",
])
def test_pure_shop_wide_kpis_use_the_deterministic_fast_path(question):
    assert _fast(question) is True


@pytest.mark.parametrize("question", [
    "sales of rice today",
    "rice sales today",
    "total sales of Lux soap yesterday",
    "sales to Ravi today",
    "revenue from sugar today",
    "total sales for ramesh today",
    "sales of rice this week",
    "sales at guntur branch this month",
])
def test_filtered_questions_never_get_a_shop_wide_total(question):
    assert _fast(question) is False


def test_unresolved_dates_still_do_not_use_the_fast_path():
    assert _fast("sales on monday") is False
    assert _fast("sales of last quarter") is False


def test_plan_without_scope_is_unchanged_for_bare_period_phrasing():
    # Without a resolved date scope the planner keeps its old, narrower behaviour.
    assert qr._make_deterministic_query_plan("sales this week")["intent"] == "general"
    assert qr._make_deterministic_query_plan("sales today")["intent"] == "aggregate"


@pytest.mark.parametrize("question", [
    "sales to 123 today",
    "sales of 500 today",
    "sales in customer 123 yesterday",
    "revenue for account 42 this week",
])
def test_numeric_entities_never_get_a_shop_wide_total(question):
    assert _fast(question) is False


@pytest.mark.parametrize("question", [
    "sales last 14 days",
    "sales from 1 november to 5 november",
    "sales on 2026-11-05",
])
def test_numeric_date_values_remain_eligible_for_kpi_fast_path(question):
    assert _fast(question) is True
