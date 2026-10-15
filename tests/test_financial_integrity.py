from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import inspect

import pytest
from fastapi import HTTPException

from models import ShopExpense
from retail_intelligence import (
    ExpenseCreate,
    _expense_matches,
    _expense_money,
    _expense_response,
    _normalize_payroll_month,
    list_expenses,
    pay_worker_salary,
)


def _existing_expense(**overrides):
    values = {
        "id": 12,
        "shop_id": 7,
        "category": "utilities",
        "amount": Decimal("500.00"),
        "description": "Electric bill",
        "expense_date": date(2026, 10, 15),
        "payment_method": "cash",
        "idempotency_key": "expense-write-key-12",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _expense_request(**overrides):
    values = {
        "category": "Utilities",
        "amount": "500",
        "description": "Electric bill",
        "expense_date": date(2026, 10, 15),
        "payment_method": "CASH",
        "idempotency_key": "expense-write-key-12",
    }
    values.update(overrides)
    return ExpenseCreate(**values)


def test_shop_expense_model_has_nullable_shop_scoped_idempotency_index():
    assert "idempotency_key" in ShopExpense.__table__.columns
    index_names = {index.name for index in ShopExpense.__table__.indexes}
    assert "uq_shop_expense_shop_idempotency" in index_names


def test_expense_retry_requires_same_amount_category_date_description_and_method():
    existing = _existing_expense()
    request = _expense_request()
    assert _expense_matches(existing, request, "utilities", "Electric bill", "CASH")
    assert not _expense_matches(existing, _expense_request(amount="501"), "utilities", "Electric bill", "CASH")
    assert not _expense_matches(existing, _expense_request(expense_date=date(2026, 10, 14)), "utilities", "Electric bill", "CASH")
    assert not _expense_matches(existing, _expense_request(description="Different bill"), "utilities", "Different bill", "CASH")
    assert not _expense_matches(existing, _expense_request(payment_method="UPI"), "utilities", "Electric bill", "UPI")


def test_expense_response_exposes_canonical_id_and_retry_status():
    result = _expense_response(_existing_expense(), duplicate=True)
    assert result["expense_id"] == 12
    assert result["amount"] == 500.0
    assert result["duplicate"] is True
    assert result["expense_date"] == "2026-10-15"


def test_expense_money_rounds_to_paise():
    assert _expense_money("10.125") == Decimal("10.13")
    assert _expense_money("10.124") == Decimal("10.12")


def test_payroll_month_requires_canonical_yyyy_mm():
    assert _normalize_payroll_month("2026-10") == "2026-10"
    for bad in ("2026-13", "2026-1", "2026-10-15", "October 2026"):
        with pytest.raises(HTTPException) as exc:
            _normalize_payroll_month(bad)
        assert exc.value.status_code == 422


def test_expense_total_uses_same_filters_as_expense_rows():
    source = inspect.getsource(list_expenses)
    assert "q.with_entities(func.sum(ShopExpense.amount)).scalar()" in source
    assert "count = q.count()" in source
    assert "start_date must be on or before end_date" in source
    assert "offset(skip).limit(limit).all()" in source


def test_salary_route_locks_worker_and_checks_stable_month_reference_before_write():
    source = inspect.getsource(pay_worker_salary)
    assert ".with_for_update()" in source
    assert 'UniversalTransaction.category == "SALARY"' in source
    assert "UniversalTransaction.reference_id == reference" in source
    assert 'idempotency_key=f"salary-worker-{worker_id}-{month}"' in source
    assert "already_paid" in source
