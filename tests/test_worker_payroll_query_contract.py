import json
from datetime import date
from types import SimpleNamespace


class _FakeQuery:
    def __init__(self, model, workers, attendance_rows):
        self.model = model
        self.workers = workers
        self.attendance_rows = attendance_rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        from models import Worker
        return self.workers if self.model is Worker else self.attendance_rows


class _FakeDb:
    def __init__(self, workers, attendance_rows):
        self.workers = workers
        self.attendance_rows = attendance_rows

    def query(self, model):
        return _FakeQuery(model, self.workers, self.attendance_rows)


def _worker():
    return SimpleNamespace(id=3, shopkeeper_id=10, name="Ganesh", salary=25000)


def _attendance_row(hours=2.4):
    notes = {
        "_retail_mind_sessions": {
            "morning": {
                "label": "Morning",
                "window": "Before 2:00 PM",
                "check_in_time": "2026-10-14T09:00:00+05:30",
                "check_out_time": "2026-10-14T11:24:00+05:30",
                "working_hours": hours,
            }
        }
    }
    return SimpleNamespace(
        id=9,
        worker_id=3,
        employee_id=10,
        attendance_date=date(2026, 10, 14),
        status="PRESENT",
        notes=json.dumps(notes),
        working_hours=hours,
        check_in_time=None,
        check_out_time=None,
    )


def test_worker_pay_question_routes_to_payroll_shortcut():
    from query_retrival import _is_explicit_worker_salary_guidance_query

    assert _is_explicit_worker_salary_guidance_query(
        "How much I need to pay for my worker Ganesh?"
    )
    assert _is_explicit_worker_salary_guidance_query(
        "How much should I pay Ganesh based on attendance?"
    )


def test_payroll_estimate_matches_flutter_baseline_hours_formula(monkeypatch):
    import query_retrival

    monkeypatch.setattr(
        query_retrival,
        "_business_dates",
        lambda: (date(2026, 10, 14), date(2026, 10, 13)),
    )
    result = query_retrival._fast_worker_payroll_query(
        "How much I need to pay for my worker Ganesh?",
        _FakeDb([_worker()], [_attendance_row(2.4)]),
        user_id=10,
    )

    row = result["results"][0]
    assert row["hourly_rate"] == 125.0
    assert row["estimated_pay"] == 300.0
    assert row["attendance_records"] == 1
    assert row["attendance_sync_status"] == "synced"
    assert "₹300.00" in result["answer"]


def test_missing_server_attendance_is_not_reported_as_zero_pay(monkeypatch):
    import query_retrival

    monkeypatch.setattr(
        query_retrival,
        "_business_dates",
        lambda: (date(2026, 10, 14), date(2026, 10, 13)),
    )
    result = query_retrival._fast_worker_payroll_query(
        "How much I need to pay for my worker Ganesh?",
        _FakeDb([_worker()], []),
        user_id=10,
    )

    row = result["results"][0]
    assert row["estimated_pay"] is None
    assert row["attendance_sync_status"] == "missing_or_not_synced"
    assert "cannot calculate a reliable amount" in result["answer"].lower()
    assert "₹0.00" not in result["answer"]


def test_groq_output_budget_is_clamped_below_the_observed_quota(monkeypatch):
    import query_retrival

    monkeypatch.setenv("GROQ_SQL_MAX_TOKENS", "1800")
    monkeypatch.setenv("GROQ_SQL_REVIEW_MAX_TOKENS", "1000")
    assert query_retrival._bounded_groq_max_tokens("GROQ_SQL_MAX_TOKENS", 800) == 900
    assert query_retrival._bounded_groq_max_tokens("GROQ_SQL_REVIEW_MAX_TOKENS", 700) == 900
