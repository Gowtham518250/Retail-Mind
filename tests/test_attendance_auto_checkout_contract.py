import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import production_boot


IST = ZoneInfo("Asia/Kolkata")


class FakeResult:
    def __init__(self, rows=None, rowcount=1):
        self.rows = rows or []
        self.rowcount = rowcount

    def mappings(self):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, shift_rows, legacy_rows):
        self.shift_rows = shift_rows
        self.legacy_rows = legacy_rows
        self.updates = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}

        if sql.lstrip().startswith("SELECT") and "FROM attendance_shifts" in sql:
            return FakeResult(self.shift_rows, rowcount=len(self.shift_rows))
        if sql.lstrip().startswith("SELECT") and "FROM attendance" in sql:
            return FakeResult(self.legacy_rows, rowcount=len(self.legacy_rows))
        if sql.lstrip().startswith("UPDATE attendance_shifts"):
            self.updates.append(("shift", params))
            return FakeResult(rowcount=1)
        if sql.lstrip().startswith("UPDATE attendance"):
            self.updates.append(("legacy", params))
            return FakeResult(rowcount=1)

        raise AssertionError(f"Unexpected SQL in test fake: {sql}")

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_legacy_checkout_uses_session_deadline_and_saves_session_metadata():
    check_in = datetime(2026, 10, 9, 8, 30)
    notes = json.dumps({
        "_retail_mind_sessions": {
            "active_session": "morning",
            "morning": {
                "label": "Morning",
                "window": "Before 2:00 PM",
                "check_in_time": "2026-10-09T08:30:00+05:30",
                "check_out_time": None,
                "working_hours": 0,
            },
        },
    })

    session_key, checkout, hours, updated_notes = production_boot._legacy_checkout_details(
        date(2026, 10, 9),
        check_in,
        notes,
    )

    assert session_key == "morning"
    assert checkout == datetime(2026, 10, 9, 14, 0)
    assert hours == 5.5
    session_history = json.loads(updated_notes)["_retail_mind_sessions"]
    assert "active_session" not in session_history
    assert session_history["morning"]["check_out_time"] == "2026-10-09T14:00:00+05:30"
    assert session_history["morning"]["working_hours"] == 5.5


def test_legacy_checkout_infers_evening_and_closes_at_midnight():
    session_key, checkout, hours, updated_notes = production_boot._legacy_checkout_details(
        date(2026, 10, 9),
        datetime(2026, 10, 9, 15, 0),
        None,
    )

    assert session_key == "evening"
    assert checkout == datetime(2026, 10, 10, 0, 0)
    assert hours == 9.0
    metadata = json.loads(updated_notes)["_retail_mind_sessions"]
    assert metadata["evening"]["check_out_time"] == "2026-10-10T00:00:00+05:30"
    assert metadata["evening"]["working_hours"] == 9.0


def test_scheduler_closes_expired_rows_in_both_attendance_tables(monkeypatch):
    shift_rows = [{
        "id": 17,
        "employee_id": 10,
        "worker_id": 22,
        "attendance_date": date(2026, 10, 10),
        "shift": "MORNING",
        "check_in_time": datetime(2026, 10, 10, 9, 0),
    }]
    legacy_rows = [{
        "id": 23,
        "employee_id": 10,
        "worker_id": 22,
        "attendance_date": date(2026, 10, 9),
        "check_in_time": datetime(2026, 10, 9, 8, 30),
        "notes": json.dumps({
            "_retail_mind_sessions": {
                "active_session": "morning",
                "morning": {
                    "check_in_time": "2026-10-09T08:30:00+05:30",
                    "check_out_time": None,
                    "working_hours": 0,
                },
            },
        }),
    }]
    fake_db = FakeSession(shift_rows, legacy_rows)

    def fake_get_db():
        yield fake_db

    monkeypatch.setattr(production_boot, "get_db", fake_get_db)
    durable_events = []
    monkeypatch.setattr(
        production_boot,
        "append_sync_event",
        lambda db, event: {**event, "sync_seq": len(durable_events) + 1},
    )
    monkeypatch.setattr(
        production_boot,
        "publish_realtime_event",
        lambda event: durable_events.append(event) or True,
    )
    production_boot._auto_checkout_expired_shifts(
        now=datetime(2026, 10, 10, 16, 30, tzinfo=IST),
        log_summary=True,
    )

    assert fake_db.commits == 1
    assert fake_db.closed
    assert [kind for kind, _ in fake_db.updates] == ["shift", "legacy"]
    assert len(durable_events) == 2
    assert all(event["type"] == "attendance.changed" for event in durable_events)
    assert all(event["change"] == "auto_checkout" for event in durable_events)
    assert {event["attendance_record_id"] for event in durable_events} == {17, 23}

    shift_update = fake_db.updates[0][1]
    assert shift_update["id"] == 17
    assert shift_update["check_out_time"] == datetime(2026, 10, 10, 12, 0)
    assert shift_update["working_hours"] == 3.0

    legacy_update = fake_db.updates[1][1]
    assert legacy_update["id"] == 23
    assert legacy_update["check_out_time"] == datetime(2026, 10, 9, 14, 0)
    assert legacy_update["working_hours"] == 5.5
    assert "active_session" not in json.loads(legacy_update["notes"])["_retail_mind_sessions"]



def test_production_boot_patches_routes_registered_on_the_running_app():
    import app

    api = production_boot._patch_routes()
    assert api is app.api

    expected = {
        "/api/attendance/check-in": "shift_check_in",
        "/api/attendance/check-out": "shift_check_out",
        "/api/attendance/employee/{employee_id}": "get_shift_attendance",
        "/api/attendance/date/{date_str}": "get_shift_attendance_by_date",
    }
    registered = {
        getattr(route, "path", ""): route
        for route in app.api.routes
        if getattr(route, "path", "") in expected
    }
    assert set(registered) == set(expected)

    for path, endpoint_name in expected.items():
        route = registered[path]
        assert route.endpoint.__name__ == endpoint_name
        # Keep FastAPI's original dependency graph: authenticated user + DB
        # dependencies must not be dropped while swapping the endpoint handler.
        assert route.dependant.call is route.endpoint
        assert len(route.dependant.dependencies) >= 2



def test_shift_rows_use_chronological_session_indices_not_shift_names():
    rows = [
        {
            "id": 2,
            "employee_id": 10,
            "worker_id": 22,
            "attendance_date": date(2026, 10, 10),
            "shift": "AFTERNOON",
            "check_in_time": datetime(2026, 10, 10, 15, 0),
            "check_out_time": None,
            "status": "PRESENT",
            "working_hours": 0,
            "checkout_reason": "MANUAL",
        },
    ]

    normalized = production_boot._combine_shift_and_legacy_records(rows, [])

    # A first check-in at 15:00 still corresponds to local session index 0.
    assert len(normalized) == 1
    assert normalized[0]["session_index"] == 0
    assert normalized[0]["session_key"] == "afternoon"

    rows.append({
        "id": 1,
        "employee_id": 10,
        "worker_id": 22,
        "attendance_date": date(2026, 10, 10),
        "shift": "MORNING",
        "check_in_time": datetime(2026, 10, 10, 9, 0),
        "check_out_time": datetime(2026, 10, 10, 12, 0),
        "status": "PRESENT",
        "working_hours": 3,
        "checkout_reason": "SHIFT_EXPIRED",
    })
    normalized = production_boot._combine_shift_and_legacy_records(rows, [])
    by_time = sorted(normalized, key=lambda row: row["check_in_time"])
    assert [row["session_index"] for row in by_time] == [0, 1]
