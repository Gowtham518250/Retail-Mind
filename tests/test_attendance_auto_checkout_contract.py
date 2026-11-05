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


def test_legacy_checkout_maps_evening_to_afternoon_and_closes_at_11pm():
    session_key, checkout, hours, updated_notes = production_boot._legacy_checkout_details(
        date(2026, 10, 9),
        datetime(2026, 10, 9, 15, 0),
        json.dumps({
            "_retail_mind_sessions": {
                "active_session": "evening",
                "evening": {
                    "check_in_time": "2026-10-09T15:00:00+05:30",
                    "check_out_time": None,
                    "working_hours": 0,
                },
            },
        }),
    )

    assert session_key == "afternoon"
    assert checkout == datetime(2026, 10, 9, 23, 0)
    assert hours == 8.0
    metadata = json.loads(updated_notes)["_retail_mind_sessions"]
    assert metadata["afternoon"]["check_out_time"] == "2026-10-09T23:00:00+05:30"
    assert metadata["afternoon"]["working_hours"] == 8.0
    assert "evening" not in metadata


def test_scheduler_closes_expired_rows_in_both_attendance_tables(monkeypatch):
    shift_rows = [{
        "id": 17,
        "employee_id": 10,
        "worker_id": 22,
        "attendance_date": date(2026, 10, 10),
        "shift": "MORNING",
        "check_in_time": datetime(2026, 10, 10, 9, 0),
        "check_out_time": None,
        "status": "PRESENT",
        "working_hours": 0.0,
        "checkout_reason": "MANUAL",
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
    assert shift_update["check_out_time"] == datetime(2026, 10, 10, 14, 0)
    assert shift_update["working_hours"] == 5.0
    assert durable_events[0]["attendance_status"] == "HALF_DAY"
    assert durable_events[0]["attendance_complete"] is False

    legacy_update = fake_db.updates[1][1]
    assert legacy_update["id"] == 23
    assert legacy_update["check_out_time"] == datetime(2026, 10, 9, 14, 0)
    assert legacy_update["working_hours"] == 5.5
    assert "active_session" not in json.loads(legacy_update["notes"])["_retail_mind_sessions"]



def test_production_boot_patches_routes_registered_on_the_running_app():
    import app
    import attendance

    api = production_boot._patch_routes()
    assert api is app.api

    # FastAPI 0.137+ stores included routers as lazy route-tree nodes, so the
    # root app.routes list isn't a flat list of APIRoute objects anymore. The
    # attendance router remains the canonical, live source of its operations.
    expected = {
        "/check-in": "shift_check_in",
        "/check-out": "shift_check_out",
        "/employee/{employee_id}": "get_shift_attendance",
        "/date/{date_str}": "get_shift_attendance_by_date",
    }
    registered = {}
    for route in attendance.router.routes:
        route_path = str(getattr(route, "path", "") or "")
        # APIRouter may expose the prefix in router.routes depending on the
        # FastAPI version. Normalize so the contract test supports both forms.
        if route_path.startswith("/api/attendance/"):
            route_path = route_path.removeprefix("/api/attendance")
        if route_path in expected:
            registered[route_path] = route
    assert set(registered) == set(expected)

    from inspect import signature
    from fastapi.params import Depends as DependsParam

    for path, endpoint_name in expected.items():
        route = registered[path]
        assert route.endpoint.__name__ == endpoint_name
        # Keep FastAPI's original dependency graph: authenticated user + DB
        # dependencies must not be dropped while swapping the endpoint handler.
        assert route.dependant.call is route.endpoint
        assert len(route.dependant.dependencies) >= 2

        if path in {"/employee/{employee_id}", "/date/{date_str}"}:
            parameters = signature(route.endpoint).parameters
            assert isinstance(parameters["current_user_id"].default, DependsParam)
            assert isinstance(parameters["db"].default, DependsParam)



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

    # Afternoon has stable index 1 regardless of whether it is the first
    # session recorded that day.
    assert len(normalized) == 1
    assert normalized[0]["session_index"] == 1
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
    assert [row["session_key"] for row in by_time] == ["morning", "afternoon"]



def test_huggingface_cache_directories_are_initialized_before_app_import():
    assert production_boot.RENDER_CACHE_DIR.is_dir()
    assert production_boot.HF_CACHE_DIR.is_dir()
    assert production_boot.HF_CACHE_DIR.parent == production_boot.RENDER_CACHE_DIR


def test_legacy_checkout_uses_latest_afternoon_checkin_not_stale_morning_metadata():
    notes = json.dumps({
        "_retail_mind_sessions": {
            "active_session": "evening",
            "morning": {
                "check_in_time": "2026-10-23T09:00:00+05:30",
                "check_out_time": "2026-10-23T14:00:00+05:30",
                "working_hours": 5,
            },
            "evening": {
                "check_in_time": "2026-10-23T19:07:00+05:30",
                "check_out_time": None,
                "working_hours": 0,
            },
        },
    })
    key, checkout, hours, updated_notes = production_boot._legacy_checkout_details(
        date(2026, 10, 23), datetime(2026, 10, 23, 19, 7), notes
    )
    assert key == "afternoon"
    assert checkout == datetime(2026, 10, 23, 23, 0)
    assert round(hours, 2) == 3.88
    updated = json.loads(updated_notes)["_retail_mind_sessions"]["afternoon"]
    assert updated["check_in_time"] == "2026-10-23T19:07:00+05:30"
    assert updated["check_out_time"] == "2026-10-23T23:00:00+05:30"


def test_scheduler_has_exactly_two_configured_shift_windows():
    assert set(production_boot.SHIFT_WINDOWS) == {"MORNING", "AFTERNOON"}
    assert production_boot.SHIFT_WINDOWS["MORNING"][0].isoformat() == "09:00:00"
    assert production_boot.SHIFT_WINDOWS["MORNING"][1].isoformat() == "14:00:00"
    assert production_boot.SHIFT_WINDOWS["AFTERNOON"][0].isoformat() == "14:00:00"
    assert production_boot.SHIFT_WINDOWS["AFTERNOON"][1].isoformat() == "23:00:00"



def test_daily_attendance_payload_requires_two_completed_shifts_for_complete():
    one_completed = production_boot._attendance_summary_for_records([
        {
            "session_index": 0,
            "session_key": "morning",
            "check_in_time": "2026-11-05T09:00:00+05:30",
            "check_out_time": "2026-11-05T14:00:00+05:30",
        },
    ])
    assert one_completed["attendance_status"] == "HALF_DAY"
    assert one_completed["attended_sessions"] == 1
    assert one_completed["completed_sessions"] == 1
    assert one_completed["attendance_complete"] is False

    both_completed = production_boot._attendance_summary_for_records([
        {
            "session_index": 0,
            "session_key": "morning",
            "check_in_time": "2026-11-05T09:00:00+05:30",
            "check_out_time": "2026-11-05T14:00:00+05:30",
        },
        {
            "session_index": 1,
            "session_key": "afternoon",
            "check_in_time": "2026-11-05T14:00:00+05:30",
            "check_out_time": "2026-11-05T23:00:00+05:30",
        },
    ])
    assert both_completed["attendance_status"] == "PRESENT"
    assert both_completed["attended_sessions"] == 2
    assert both_completed["completed_sessions"] == 2
    assert both_completed["attendance_complete"] is True

    no_attendance = production_boot._attendance_summary_for_records([])
    assert no_attendance["attendance_status"] == "ABSENT"
    assert no_attendance["attended_sessions"] == 0
    assert no_attendance["attendance_complete"] is False


def test_legacy_checkout_never_writes_before_an_out_of_window_checkin():
    _key, checkout, hours, _notes = production_boot._legacy_checkout_details(
        date(2026, 10, 9),
        datetime(2026, 10, 9, 23, 20),
        None,
    )
    assert checkout == datetime(2026, 10, 9, 23, 20)
    assert hours == 0.0
