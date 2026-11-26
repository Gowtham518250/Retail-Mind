"""Owner-confirmed, tenant-scoped attendance corrections for the agent."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .preview_policy import preview_expires_at, preview_ttl_seconds

from models import AgentPendingAction, Attendance, User, Worker

_ATTENDANCE_ACTION = "ATTENDANCE_RECORD"
_IST = ZoneInfo("Asia/Kolkata")
_ALLOWED_STATUSES = {"PRESENT", "ABSENT", "LEAVE", "HALF_DAY", "LATE"}


def _status_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value)).upper().replace("-", "_")


def _timestamp_value(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(action_id: str, shop_id: int, preview: dict, payload: dict) -> str:
    return hashlib.sha256(_canonical({
        "action_id": action_id,
        "shop_id": int(shop_id),
        "preview": preview,
        "payload": payload,
    }).encode("utf-8")).hexdigest()


def _existing_attendance_note(raw_notes: str | None) -> str:
    raw = str(raw_notes or "")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if isinstance(data, dict) and "_retail_mind_sessions" in data:
        return str(data.get("_retail_mind_agent_note") or "")
    return raw


def _merge_attendance_note(raw_notes: str | None, new_note: str | None) -> str | None:
    """Merge human notes without destroying check-in session JSON in notes."""
    clean = " ".join(str(new_note or "").split())[:500]
    if not clean:
        return raw_notes
    raw = str(raw_notes or "")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        data = None
    if isinstance(data, dict) and isinstance(data.get("_retail_mind_sessions"), dict):
        # Preserve the canonical active/completed shift metadata consumed by
        # attendance._session_meta; keep the assistant note in a separate key.
        data["_retail_mind_agent_note"] = clean
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if not raw.strip():
        return clean
    return (raw.rstrip() + "\n" + clean)[:1500]


def _attendance_snapshot(row: Attendance | None) -> dict:
    if row is None:
        return {
            "attendance_id": None,
            "status": None,
            "check_in_time": None,
            "check_out_time": None,
            "working_hours": None,
            "notes": None,
        }
    return {
        "attendance_id": int(row.id),
        "status": _status_value(row.status),
        "check_in_time": _timestamp_value(row.check_in_time),
        "check_out_time": _timestamp_value(row.check_out_time),
        "working_hours": float(row.working_hours or 0),
        "notes": str(row.notes or ""),
    }


def prepare_attendance_record(
    db: Session,
    *,
    shop_id: int,
    conversation_id: str,
    request_text: str,
    worker_id: int,
    attendance_date: date,
    status: str,
    notes: str | None = None,
) -> dict:
    normalized_status = str(status or "").strip().upper().replace("-", "_")
    if normalized_status not in _ALLOWED_STATUSES:
        raise ValueError("Choose PRESENT, ABSENT, LEAVE, HALF_DAY or LATE")
    if not conversation_id:
        raise ValueError("A saved conversation is required to prepare attendance")
    today = datetime.now(_IST).date()
    if attendance_date > today:
        raise ValueError("Attendance cannot be recorded for a future date")
    if (today - attendance_date).days > 90:
        raise ValueError("Agent attendance corrections are limited to the last 90 days")
    clean_notes = " ".join(str(notes or "").split())[:500]
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.shopkeeper_id == shop_id,
    ).first()
    if worker is None:
        raise ValueError("The selected employee was not found in this shop")
    existing = db.query(Attendance).filter(
        Attendance.employee_id == shop_id,
        Attendance.worker_id == worker_id,
        Attendance.attendance_date == attendance_date,
    ).first()
    before = _attendance_snapshot(existing)
    action_id = str(uuid.uuid4())
    preview = {
        "operation": "UPDATE_ATTENDANCE",
        "worker_id": int(worker.id),
        "employee_name": str(worker.name or "Employee")[:100],
        "attendance_date": attendance_date.isoformat(),
        "status_before": before["status"] or "NOT_RECORDED",
        "status_after": normalized_status,
        "record_before": "EXISTS" if existing else "NOT_RECORDED",
        "check_in_time_preserved": before["check_in_time"],
        "check_out_time_preserved": before["check_out_time"],
        "working_hours_preserved": before["working_hours"],
        "notes": clean_notes or _existing_attendance_note(before["notes"]) or None,
        "requires_owner_confirmation": True,
        "expires_in_seconds": preview_ttl_seconds(),
        "warning": "This changes the daily attendance status only. Existing check-in/out timestamps and calculated working hours are preserved.",
    }
    payload = {
        "worker_id": int(worker.id),
        "attendance_date": attendance_date.isoformat(),
        "status": normalized_status,
        "notes": clean_notes or None,
        "expected": before,
    }
    key = hashlib.sha256(_canonical({
        "shop_id": int(shop_id),
        "conversation_id": conversation_id,
        "request_text": " ".join(str(request_text or "").split()).casefold()[:1000],
        "payload": payload,
    }).encode("utf-8")).hexdigest()
    prior = db.query(AgentPendingAction).filter(
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.idempotency_key == key,
    ).first()
    if prior:
        if prior.status in {"PENDING", "EXECUTING", "COMPLETED"}:
            return {
                "success": True,
                "duplicate_request": True,
                "action_id": prior.id,
                "status": prior.status,
                "preview_hash": prior.preview_hash,
                "preview": prior.preview,
                "message": "This attendance correction already has a confirmation action.",
            }
        return {"success": False, "needs_clarification": True, "message": "This attendance action expired or failed. Prepare it again."}
    digest = _hash(action_id, shop_id, preview, payload)
    db.add(AgentPendingAction(
        id=action_id,
        user_id=shop_id,
        conversation_id=conversation_id,
        action_type=_ATTENDANCE_ACTION,
        status="PENDING",
        idempotency_key=key,
        preview=preview,
        payload=payload,
        preview_hash=digest,
        expires_at=preview_expires_at(),
    ))
    db.flush()
    return {
        "success": True,
        "action_id": action_id,
        "status": "PENDING",
        "preview_hash": digest,
        "preview": preview,
        "message": "Attendance correction preview prepared. No attendance data has changed. Review and confirm it in Retail Mind.",
    }


def confirm_attendance_record(
    db: Session,
    *,
    shop_id: int,
    action_id: str,
    supplied_preview_hash: str,
) -> dict:
    action = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.action_type == _ATTENDANCE_ACTION,
    ).with_for_update().first()
    if action is None:
        raise HTTPException(status_code=404, detail="Attendance preview not found.")
    expected_hash = _hash(action.id, shop_id, action.preview, action.payload)
    if (
        not supplied_preview_hash
        or not hmac.compare_digest(action.preview_hash, supplied_preview_hash)
        or not hmac.compare_digest(action.preview_hash, expected_hash)
    ):
        raise HTTPException(status_code=409, detail="The attendance preview changed. Prepare it again.")
    if action.status == "COMPLETED":
        return {**(action.result or {}), "duplicate_confirmation": True}
    if action.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This attendance preview cannot be confirmed in state {action.status}.")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if action.expires_at <= now:
        action.status = "EXPIRED"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=410, detail="The attendance preview expired. Prepare it again.")

    owner = db.query(User).filter(User.id == shop_id).with_for_update().first()
    if owner is None:
        raise HTTPException(status_code=404, detail="Shop owner not found.")
    payload = action.payload
    worker = db.query(Worker).filter(
        Worker.id == int(payload["worker_id"]),
        Worker.shopkeeper_id == shop_id,
    ).with_for_update().first()
    if worker is None:
        action.status = "FAILED"
        action.error_code = "WORKER_NOT_FOUND"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=404, detail="The employee no longer belongs to this shop.")

    attendance_date = date.fromisoformat(payload["attendance_date"])
    record = db.query(Attendance).filter(
        Attendance.employee_id == shop_id,
        Attendance.worker_id == worker.id,
        Attendance.attendance_date == attendance_date,
    ).with_for_update().first()
    current = _attendance_snapshot(record)
    if current != payload["expected"]:
        action.status = "FAILED"
        action.error_code = "ATTENDANCE_CHANGED_AFTER_PREVIEW"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=409, detail="This employee's attendance changed after preview. Refresh and prepare a new correction.")

    if record is None:
        record = Attendance(
            employee_id=shop_id,
            worker_id=worker.id,
            attendance_date=attendance_date,
            status=payload["status"],
            working_hours=0.0,
            notes=_merge_attendance_note(None, payload.get("notes")),
        )
        db.add(record)
    else:
        record.status = payload["status"]
        record.notes = _merge_attendance_note(record.notes, payload.get("notes"))
    try:
        db.flush()
        # Use the same durable outbox and realtime event path as the existing
        # manual attendance route so app sync and live dashboards stay aligned.
        from attendance import _serialize_attendance_time
        from durable_sync import append_sync_event
        from realtime import publish_realtime_event

        sync_event = append_sync_event(db, {
            "event_id": str(uuid.uuid4()),
            "type": "attendance.changed",
            "shop_id": int(shop_id),
            "attendance_id": int(record.id),
            "employee_id": int(shop_id),
            "worker_id": int(worker.id),
            "attendance_date": attendance_date.isoformat(),
            "check_in_time": _serialize_attendance_time(record.check_in_time),
            "check_out_time": _serialize_attendance_time(record.check_out_time),
            "status": str(_status_value(record.status) or ""),
            "change": "agent_confirmed_manual_record",
            "agent_action_id": action.id,
        })
        result = {
            "success": True,
            "verified": True,
            "action_id": action.id,
            "worker_id": int(worker.id),
            "employee_name": str(worker.name or "Employee"),
            "attendance_date": attendance_date.isoformat(),
            "status": _status_value(record.status),
            "check_in_time_preserved": _timestamp_value(record.check_in_time),
            "check_out_time_preserved": _timestamp_value(record.check_out_time),
            "working_hours_preserved": float(record.working_hours or 0),
            "message": "Attendance updated successfully.",
        }
        action.status = "COMPLETED"
        action.result = result
        action.completed_at = now
        action.updated_at = now
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Attendance could not be safely saved. Refresh the attendance screen before retrying.") from exc

    persisted = db.query(Attendance).filter(
        Attendance.id == record.id,
        Attendance.employee_id == shop_id,
        Attendance.worker_id == worker.id,
    ).first()
    if persisted is None or _status_value(persisted.status) != payload["status"]:
        raise HTTPException(status_code=503, detail="Attendance was saved but could not be verified. Refresh the attendance screen.")
    try:
        publish_realtime_event(sync_event)
    except Exception:
        # The durable event remains queued for the app's normal sync worker.
        pass
    return result
