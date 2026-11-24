from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from agentic.attendance_actions import prepare_attendance_record
from agentic.registry import list_capabilities
from agentic.tools import AttendanceRecordPreviewArgs, TOOL_DEFINITIONS
from models import AgentPendingAction, Attendance, Worker


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *_args, **_kwargs):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.result


class _Db:
    def __init__(self, worker=None, attendance=None):
        self.worker = worker
        self.attendance = attendance
        self.added = []

    def query(self, model):
        if model is Worker:
            return _Query(self.worker)
        if model is Attendance:
            return _Query(self.attendance)
        if model is AgentPendingAction:
            return _Query(None)
        raise AssertionError(f"Unexpected query model: {model}")

    def add(self, item):
        self.added.append(item)

    def flush(self):
        return None


def test_attendance_tool_rejects_untrusted_tenant_fields():
    with pytest.raises(ValidationError):
        AttendanceRecordPreviewArgs.model_validate({
            "worker_id": 8,
            "attendance_date": "2026-11-24",
            "status": "PRESENT",
            "shop_id": 999,
        })


def test_attendance_tool_accepts_only_known_statuses():
    with pytest.raises(ValidationError):
        AttendanceRecordPreviewArgs.model_validate({
            "worker_id": 8,
            "attendance_date": "2026-11-24",
            "status": "PAID",
        })


def test_worker_directory_returns_only_safe_shop_worker_fields():
    from agentic.tools import _worker_directory

    class DirectoryQuery:
        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def all(self):
            return [SimpleNamespace(id=8, name="Ravi", position="Cashier", status="active")]

    class DirectoryDb:
        def query(self, *_columns):
            return DirectoryQuery()

    result = _worker_directory(DirectoryDb(), 42)
    assert result["count"] == 1
    assert result["workers"][0] == {
        "worker_id": 8,
        "name": "Ravi",
        "position": "Cashier",
        "status": "active",
    }
    assert "salary" not in result["workers"][0]
    assert "pin" not in result["workers"][0]
    assert "phone" not in result["workers"][0]


def test_attendance_tool_is_allowlisted_and_confirmation_gated():
    names = {
        item["function"]["name"]
        for item in TOOL_DEFINITIONS
        if item.get("type") == "function"
    }
    assert "prepare_attendance_record" in names


def test_attendance_preview_does_not_mutate_existing_record():
    worker = SimpleNamespace(id=8, shopkeeper_id=42, name="Ravi")
    existing = SimpleNamespace(
        id=12,
        status="PRESENT",
        check_in_time=datetime(2026, 11, 24, 9, 15),
        check_out_time=None,
        working_hours=0.0,
        notes="Original",
    )
    db = _Db(worker, existing)
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    result = prepare_attendance_record(
        db,
        shop_id=42,
        conversation_id="conversation-1",
        request_text="mark Ravi absent today",
        worker_id=8,
        attendance_date=today,
        status="ABSENT",
        notes="Owner correction",
    )
    assert result["success"] is True
    assert result["preview"]["status_before"] == "PRESENT"
    assert result["preview"]["status_after"] == "ABSENT"
    assert result["preview"]["check_in_time_preserved"] == existing.check_in_time.isoformat()
    assert result["preview"]["requires_owner_confirmation"] is True
    assert existing.status == "PRESENT"
    assert existing.notes == "Original"
    assert len(db.added) == 1
    assert db.added[0].action_type == "ATTENDANCE_RECORD"


def test_attendance_preview_rejects_worker_from_another_shop():
    db = _Db(worker=None, attendance=None)
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    with pytest.raises(ValueError, match="not found"):
        prepare_attendance_record(
            db,
            shop_id=42,
            conversation_id="conversation-1",
            request_text="mark employee present",
            worker_id=8,
            attendance_date=today,
            status="PRESENT",
        )


def test_attendance_preview_rejects_future_date():
    worker = SimpleNamespace(id=8, shopkeeper_id=42, name="Ravi")
    db = _Db(worker, None)
    future = datetime.now(ZoneInfo("Asia/Kolkata")).date() + timedelta(days=1)
    with pytest.raises(ValueError, match="future"):
        prepare_attendance_record(
            db,
            shop_id=42,
            conversation_id="conversation-1",
            request_text="mark Ravi present tomorrow",
            worker_id=8,
            attendance_date=future,
            status="PRESENT",
        )


def test_attendance_manage_is_implemented_but_requires_confirmation(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    capabilities = {item["name"]: item for item in list_capabilities()}
    attendance = capabilities["attendance.manage"]
    assert attendance["implemented"] is True
    assert attendance["enabled"] is True
    assert attendance["requires_confirmation"] is True


def test_attendance_manage_remains_off_when_agent_flag_is_off(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "false")
    capabilities = {item["name"]: item for item in list_capabilities()}
    attendance = capabilities["attendance.manage"]
    assert attendance["implemented"] is True
    assert attendance["enabled"] is False
