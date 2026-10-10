"""Production bootstrap for backend-only compatibility fixes.

Keeps the existing Flutter/API contracts while fixing invoice numeric types and
adding shift-aware worker attendance without replacing the main route modules.
Render should start this file after Alembic migrations.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
import threading
import json
import time as time_module
import os
from pathlib import Path

# Render uses /opt/render as the writable application area. Some Hugging Face\n# components default to /app/.cache, which does not exist on Render.\n# Set the cache locations before importing application modules so ML/RAG\n# dependencies use a writable directory.\nRENDER_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", "/tmp/.cache"))\nHF_CACHE_DIR = RENDER_CACHE_DIR / "huggingface"\nHF_CACHE_DIR.mkdir(parents=True, exist_ok=True)\nos.environ.setdefault("XDG_CACHE_HOME", str(RENDER_CACHE_DIR))\nos.environ.setdefault("HF_HOME", str(HF_CACHE_DIR))\nos.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE_DIR / "hub"))\nos.environ.setdefault("TRANSFORMERS_CACHE", str(HF_CACHE_DIR / "transformers"))\n\nfrom fastapi import HTTPException
from sqlalchemy import text

from db import get_db
from models import Worker, User

SHIFT_WINDOWS = {
    "MORNING": (time(6, 0), time(12, 0)),
    "AFTERNOON": (time(12, 0), time(17, 0)),
    "EVENING": (time(17, 0), time(23, 0)),
}
IST = ZoneInfo("Asia/Kolkata")


def _current_shift():
    now = datetime.now(IST)
    for name, (start, end) in SHIFT_WINDOWS.items():
        if start <= now.time() < end:
            return name, now
    return None, now


LEGACY_SESSION_META_KEY = "_retail_mind_sessions"


def _attendance_ist_iso(value):
    """Return a timestamp with an explicit IST offset for session metadata."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    else:
        value = value.astimezone(IST)
    return value.isoformat()


def _legacy_checkout_details(attendance_date, check_in_time, notes):
    """Build a safe automatic checkout for a legacy daily Attendance row.

    Older app versions store sessions in attendance.notes as JSON. Morning
    attendance closes at 14:00 IST; the afternoon/evening session closes at
    midnight. If legacy notes are absent, infer the session from check-in time.
    """
    raw_notes = notes or ""
    try:
        meta = json.loads(raw_notes) if raw_notes else {}
    except (TypeError, ValueError):
        meta = {"note": str(raw_notes)} if raw_notes else {}
    if not isinstance(meta, dict):
        meta = {"note": str(raw_notes)} if raw_notes else {}

    session_history = meta.get(LEGACY_SESSION_META_KEY)
    if not isinstance(session_history, dict):
        session_history = {}
    active_session = session_history.get("active_session")
    if active_session not in {"morning", "evening"}:
        active_session = "morning" if check_in_time.time() < time(14, 0) else "evening"

    if active_session == "morning":
        checkout_at = datetime.combine(attendance_date, time(14, 0))
        label, window = "Morning", "Before 2:00 PM"
    else:
        checkout_at = datetime.combine(
            attendance_date + timedelta(days=1),
            time.min,
        )
        label, window = "Afternoon", "2:00 PM onward"

    normalized_check_in = (
        check_in_time.replace(tzinfo=None)
        if check_in_time.tzinfo is not None
        else check_in_time
    )
    hours = max(0.0, (checkout_at - normalized_check_in).total_seconds() / 3600.0)

    session = session_history.get(active_session)
    if not isinstance(session, dict):
        session = {}
    session.update({
        "label": session.get("label") or label,
        "window": session.get("window") or window,
        "check_in_time": session.get("check_in_time") or _attendance_ist_iso(check_in_time),
        "check_out_time": _attendance_ist_iso(checkout_at),
        "working_hours": hours,
    })
    session_history[active_session] = session
    session_history.pop("active_session", None)
    meta[LEGACY_SESSION_META_KEY] = session_history

    return (
        active_session,
        checkout_at,
        hours,
        json.dumps(meta, separators=(",", ":"), default=str),
    )


def _auto_checkout_expired_shifts(now=None, log_summary=False):
    """Close expired records in both the shift table and legacy attendance table.

    The app has used both storage formats: newer check-ins use attendance_shifts,
    while older/local-first syncs can still leave open rows in attendance. Both
    must be reconciled or the app can keep showing a running attendance timer.
    """
    db = next(get_db())
    try:
        current = now or datetime.now(IST)
        if current.tzinfo is not None:
            current = current.astimezone(IST).replace(tzinfo=None)

        shift_rows = db.execute(text("""
            SELECT id, attendance_date, shift, check_in_time
            FROM attendance_shifts
            WHERE check_in_time IS NOT NULL
              AND check_out_time IS NULL
              AND attendance_date <= :today
            ORDER BY attendance_date, check_in_time
        """), {"today": current.date()}).mappings().all()

        shift_updates = 0
        for row in shift_rows:
            window = SHIFT_WINDOWS.get(str(row["shift"]).upper())
            if not window:
                continue

            shift_end = datetime.combine(row["attendance_date"], window[1])
            if shift_end > current:
                continue

            check_in = row["check_in_time"]
            normalized_check_in = (
                check_in.replace(tzinfo=None)
                if check_in.tzinfo is not None
                else check_in
            )
            hours = max(0.0, (shift_end - normalized_check_in).total_seconds() / 3600.0)
            result = db.execute(text("""
                UPDATE attendance_shifts
                SET check_out_time = :check_out_time,
                    working_hours = :working_hours,
                    checkout_reason = 'SHIFT_EXPIRED'
                WHERE id = :id
                  AND check_out_time IS NULL
            """), {
                "check_out_time": shift_end,
                "working_hours": hours,
                "id": row["id"],
            })
            if getattr(result, "rowcount", 1) != 0:
                shift_updates += 1

        legacy_rows = db.execute(text("""
            SELECT id, attendance_date, check_in_time, notes
            FROM attendance
            WHERE check_in_time IS NOT NULL
              AND check_out_time IS NULL
              AND attendance_date <= :today
            ORDER BY attendance_date, check_in_time
        """), {"today": current.date()}).mappings().all()

        legacy_updates = 0
        for row in legacy_rows:
            _session_key, checkout_at, hours, notes_json = _legacy_checkout_details(
                row["attendance_date"],
                row["check_in_time"],
                row["notes"],
            )
            if checkout_at > current:
                continue

            result = db.execute(text("""
                UPDATE attendance
                SET check_out_time = :check_out_time,
                    working_hours = :working_hours,
                    notes = :notes
                WHERE id = :id
                  AND check_out_time IS NULL
            """), {
                "check_out_time": checkout_at,
                "working_hours": hours,
                "notes": notes_json,
                "id": row["id"],
            })
            if getattr(result, "rowcount", 1) != 0:
                legacy_updates += 1

        if shift_updates or legacy_updates:
            db.commit()
            print(
                "[ATTENDANCE] auto-checkout completed: "
                f"{shift_updates} shift row(s), {legacy_updates} legacy row(s)",
                flush=True,
            )
        else:
            db.rollback()
            if log_summary:
                print(
                    "[ATTENDANCE] auto-checkout scan complete; "
                    f"{len(shift_rows)} open shift row(s), "
                    f"{len(legacy_rows)} open legacy row(s), none expired yet",
                    flush=True,
                )
    except Exception as exc:
        db.rollback()
        print(f"[ATTENDANCE] auto-checkout pass failed: {exc}", flush=True)
    finally:
        db.close()


def _start_attendance_auto_checkout():
    """Run an immediate reconciliation and then check for expired shifts."""
    _auto_checkout_expired_shifts(log_summary=True)

    def loop():
        while True:
            time_module.sleep(30)
            _auto_checkout_expired_shifts()

    thread = threading.Thread(
        target=loop,
        name="attendance-auto-checkout",
        daemon=True,
    )
    thread.start()
    print("[ATTENDANCE] automatic shift checkout worker started", flush=True)

def _ensure_online_order_status_enum():
    """Keep production PostgreSQL enum values aligned with the online-order state machine."""
    from db import engine

    with engine.begin() as conn:
        conn.execute(text("""
            DO $rm_order_status$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_type WHERE typname = 'online_order_status'
                ) THEN
                    ALTER TYPE online_order_status ADD VALUE IF NOT EXISTS 'CANCELLED';
                    ALTER TYPE online_order_status ADD VALUE IF NOT EXISTS 'RETURNED';
                END IF;
            END
            $rm_order_status$;
        """))


def _ensure_sales_reference_order_id():
    """Safely add the online-order reference column to legacy sales tables."""
    db = next(get_db())
    try:
        db.execute(text("""
            ALTER TABLE IF EXISTS sales
            ADD COLUMN IF NOT EXISTS reference_order_id INTEGER
        """))
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sales_reference_order_id
            ON sales (reference_order_id)
        """))
        db.commit()
    finally:
        db.close()


def _ensure_online_delivery_payment_trigger():
    """Create an idempotent DB trigger that records payment when an online invoice is settled."""
    db = next(get_db())
    try:
        db.execute(text("""
            CREATE OR REPLACE FUNCTION retail_mind_auto_record_online_payment()
            RETURNS TRIGGER
            LANGUAGE plpgsql
            AS $rm_payment$
            BEGIN
                IF NEW.source = 'ONLINE_ORDER'
                   AND NEW.status = 'PAID'
                   AND COALESCE(OLD.status::text, '') <> 'PAID'
                   AND NOT EXISTS (
                       SELECT 1
                       FROM payments
                       WHERE invoice_id = NEW.id
                         AND idempotency_key = 'AUTO_DELIVERY:' || NEW.id::text
                   )
                THEN
                    INSERT INTO payments (
                        invoice_id,
                        payment_method,
                        amount,
                        reference_number,
                        notes,
                        payment_date,
                        idempotency_key
                    )
                    VALUES (
                        NEW.id,
                        'ONLINE'::payment_method,
                        NEW.paid_amount,
                        'AUTO-DELIVERY-' || NEW.id::text,
                        'Automatically recorded when online order was delivered and delivery OTP was verified.',
                        CURRENT_TIMESTAMP,
                        'AUTO_DELIVERY:' || NEW.id::text
                    );
                END IF;
                RETURN NEW;
            END;
            $rm_payment$;
        """))
        db.execute(text("""
            DROP TRIGGER IF EXISTS trg_auto_record_online_payment ON invoices
        """))
        db.execute(text("""
            CREATE TRIGGER trg_auto_record_online_payment
            AFTER UPDATE OF status, payment_status, paid_amount ON invoices
            FOR EACH ROW
            EXECUTE FUNCTION retail_mind_auto_record_online_payment()
        """))
        db.commit()
        print("[DB] online delivery auto-payment trigger ready", flush=True)
    finally:
        db.close()


def _ensure_shift_table():
    db = next(get_db())
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS attendance_shifts (
                id SERIAL PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                worker_id INTEGER NULL,
                attendance_date DATE NOT NULL,
                shift VARCHAR(20) NOT NULL,
                check_in_time TIMESTAMP NULL,
                check_out_time TIMESTAMP NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'PRESENT',
                working_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
                checkout_reason VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_attendance_shift UNIQUE
                    (employee_id, worker_id, attendance_date, shift)
            )
        """))
        db.execute(text("""
            ALTER TABLE attendance_shifts
            ADD COLUMN IF NOT EXISTS checkout_reason VARCHAR(30) NOT NULL DEFAULT 'MANUAL'
        """))
        db.commit()
    finally:
        db.close()


def _resolve_employee(employee_id, current_user_id, db):
    worker = db.query(Worker).filter(Worker.id == employee_id).first()
    if worker:
        if worker.shopkeeper_id != current_user_id:
            raise HTTPException(403, "You can only manage your own workers")
        return worker.shopkeeper_id, worker.id

    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(404, "Employee not found")
    if employee_id != current_user_id:
        raise HTTPException(403, "You can only manage your own attendance")
    return employee_id, None


def _parse_attendance_datetime(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
    except (TypeError, ValueError):
        return None


def _same_check_in(first, second):
    left = _parse_attendance_datetime(first)
    right = _parse_attendance_datetime(second)
    return left is not None and right is not None and abs((left - right).total_seconds()) <= 60


def _serialize_shift_row(row):
    shift = str(row["shift"] or "").upper()
    session_index = {"MORNING": 0, "AFTERNOON": 1, "EVENING": 2}.get(shift, 0)
    session_key = "morning" if shift == "MORNING" else "afternoon"
    hours = float(row.get("working_hours") or 0.0)
    attendance_date = row["attendance_date"]
    check_in = row.get("check_in_time")
    check_out = row.get("check_out_time")
    return {
        "id": row["id"],
        "employee_id": row["employee_id"],
        "worker_id": row["worker_id"],
        "attendance_date": attendance_date.isoformat() if hasattr(attendance_date, "isoformat") else str(attendance_date),
        "check_in_time": check_in.isoformat() if hasattr(check_in, "isoformat") else check_in,
        "check_out_time": check_out.isoformat() if hasattr(check_out, "isoformat") else check_out,
        "status": str(row.get("status") or "PRESENT"),
        "working_hours": hours,
        "total_working_hours": hours,
        "session_index": session_index,
        "session_key": session_key,
        "checkout_reason": row.get("checkout_reason") or "MANUAL",
        "local_pending": False,
    }


def _combine_shift_and_legacy_records(shift_rows, legacy_records):
    shift_records = [_serialize_shift_row(row) for row in shift_rows]
    shifts_by_date = {}
    reserved_indexes = {}
    for record in shift_records:
        day = str(record.get("attendance_date") or "").split("T")[0]
        shifts_by_date.setdefault(day, []).append(record)
        reserved_indexes.setdefault(day, set()).add(int(record.get("session_index", 0)))

    records = list(shift_records)
    for legacy in legacy_records or []:
        day = str(legacy.get("attendance_date") or "").split("T")[0]
        day_shifts = shifts_by_date.get(day, [])
        if not day_shifts:
            records.append(legacy)
            continue

        raw_sessions = legacy.get("sessions")
        if isinstance(raw_sessions, dict) and raw_sessions:
            session_items = list(raw_sessions.items())
        else:
            session_items = [(None, legacy)]

        for session_key, session_value in session_items:
            if not isinstance(session_value, dict):
                continue
            check_in = session_value.get("check_in_time") or legacy.get("check_in_time")
            # The same check-in can exist in both formats during an upgrade.
            # Prefer the shift row so its automatic checkout remains authoritative.
            if any(_same_check_in(check_in, row.get("check_in_time")) for row in day_shifts):
                continue

            reserved = reserved_indexes.setdefault(day, set())
            if session_key is None:
                parsed = _parse_attendance_datetime(check_in)
                session_index = 0 if parsed is None or parsed.hour < 14 else 1
            else:
                session_index = 0 if str(session_key).lower() == "morning" else 1
            while session_index in reserved:
                session_index += 1
            reserved.add(session_index)

            record = {key: value for key, value in legacy.items() if key != "sessions"}
            record.update(session_value)
            record["id"] = f"legacy-{legacy.get('id', 'attendance')}-{session_key or session_index}"
            record["attendance_date"] = day
            record["session_index"] = session_index
            record["session_key"] = (
                "morning" if str(session_key).lower() == "morning"
                else ("afternoon" if session_key is not None else record.get("session_key", "morning"))
            )
            record["check_in_time"] = check_in
            record["working_hours"] = float(session_value.get("working_hours") or 0.0)
            record["total_working_hours"] = record["working_hours"]
            record["local_pending"] = False
            records.append(record)

    records.sort(
        key=lambda item: (
            str(item.get("attendance_date") or ""),
            str(item.get("check_in_time") or ""),
        ),
        reverse=True,
    )
    return records


def _patch_routes():
    import app as app_module
    import invoices_billing

    # Patch the actual APIRoute instances registered on app.api. Patching only
    # invoices_billing.router / attendance.router after include_router() is not
    # sufficient: FastAPI has already copied those routes into the app.
    invoice_sync_endpoints = {
        route.endpoint
        for route in invoices_billing.router.routes
        if getattr(route, "path", "") == "/sync"
        and "POST" in getattr(route, "methods", set())
    }
    for route in app_module.api.routes:
        if (
            getattr(route, "endpoint", None) in invoice_sync_endpoints
            and "POST" in getattr(route, "methods", set())
        ):
            original = route.endpoint

            def invoice_sync_wrapper(data, db, current_user, _original=original):
                for item in data.line_items or []:
                    object.__setattr__(item, "quantity", Decimal(str(item.quantity)))
                    object.__setattr__(item, "unit_price", Decimal(str(item.unit_price)))
                    object.__setattr__(item, "discount_amount", Decimal(str(item.discount_amount)))
                return _original(data=data, db=db, current_user=current_user)

            route.endpoint = invoice_sync_wrapper
            route.dependant.call = invoice_sync_wrapper
            break

    def shift_check_in(employee_id, db, current_user_id):
        shift, now = _current_shift()
        if not shift:
            raise HTTPException(
                400,
                "No attendance session is active. Morning: 6 AM-12 PM, "
                "Afternoon: 12 PM-5 PM, Evening: 5 PM-11 PM.",
            )

        actual_employee_id, worker_id = _resolve_employee(employee_id, current_user_id, db)
        today = now.date()
        row = db.execute(text("""
            SELECT id, check_in_time, check_out_time, status
            FROM attendance_shifts
            WHERE employee_id = :employee_id
              AND worker_id IS NOT DISTINCT FROM :worker_id
              AND attendance_date = :attendance_date
              AND shift = :shift
        """), {
            "employee_id": actual_employee_id,
            "worker_id": worker_id,
            "attendance_date": today,
            "shift": shift,
        }).mappings().first()

        if row:
            if row["check_out_time"]:
                raise HTTPException(
                    400,
                    f"{shift.title()} attendance already marked. Please try the next session.",
                )
            raise HTTPException(
                400,
                f"{shift.title()} attendance is already active. Please check out first.",
            )

        db.execute(text("""
            INSERT INTO attendance_shifts
                (employee_id, worker_id, attendance_date, shift, check_in_time, status)
            VALUES
                (:employee_id, :worker_id, :attendance_date, :shift, :check_in_time, 'PRESENT')
        """), {
            "employee_id": actual_employee_id,
            "worker_id": worker_id,
            "attendance_date": today,
            "shift": shift,
            "check_in_time": now.replace(tzinfo=None),
        })
        db.commit()
        return {
            "message": f"{shift.title()} check-in successful",
            "employee_id": actual_employee_id,
            "worker_id": worker_id,
            "shift": shift,
            "check_in_time": now.isoformat(),
            "status": "PRESENT",
            "checkout_reason": None,
        }

    def shift_check_out(employee_id, db, current_user_id):
        actual_employee_id, worker_id = _resolve_employee(employee_id, current_user_id, db)
        today = datetime.now(IST).date()
        row = db.execute(text("""
            SELECT id, shift, check_in_time, check_out_time
            FROM attendance_shifts
            WHERE employee_id = :employee_id
              AND worker_id IS NOT DISTINCT FROM :worker_id
              AND attendance_date = :attendance_date
              AND check_in_time IS NOT NULL
            ORDER BY check_in_time DESC
            LIMIT 1
        """), {
            "employee_id": actual_employee_id,
            "worker_id": worker_id,
            "attendance_date": today,
        }).mappings().first()

        if not row:
            raise HTTPException(400, "No active shift check-in found for today")
        if row["check_out_time"]:
            raise HTTPException(
                400,
                f"{row['shift'].title()} attendance already checked out. Try another session.",
            )

        now = datetime.now(IST).replace(tzinfo=None)
        hours = max(0.0, (now - row["check_in_time"]).total_seconds() / 3600)
        db.execute(text("""
            UPDATE attendance_shifts
            SET check_out_time = :check_out_time, working_hours = :working_hours,
                checkout_reason = 'MANUAL'
            WHERE id = :id AND check_out_time IS NULL
        """), {"check_out_time": now, "working_hours": hours, "id": row["id"]})
        db.commit()
        return {
            "message": f"{row['shift'].title()} check-out successful",
            "checkout_reason": "MANUAL",
            "employee_id": actual_employee_id,
            "worker_id": worker_id,
            "shift": row["shift"],
            "check_out_time": now.isoformat(),
            "working_hours": round(hours, 2),
        }

    def make_shift_attendance_endpoint(legacy_endpoint):
        def get_shift_attendance(employee_id, from_date=None, to_date=None, db=None, current_user_id=None):
            actual_employee_id, worker_id = _resolve_employee(employee_id, current_user_id, db)
            clauses = [
                "employee_id = :employee_id",
                "worker_id IS NOT DISTINCT FROM :worker_id",
            ]
            params = {"employee_id": actual_employee_id, "worker_id": worker_id}
            if from_date:
                clauses.append("attendance_date >= :from_date")
                params["from_date"] = from_date
            if to_date:
                clauses.append("attendance_date <= :to_date")
                params["to_date"] = to_date

            rows = db.execute(text(
                "SELECT id, employee_id, worker_id, attendance_date, shift, "
                "check_in_time, check_out_time, status, working_hours, checkout_reason "
                "FROM attendance_shifts WHERE " + " AND ".join(clauses) +
                " ORDER BY attendance_date DESC, check_in_time DESC"
            ), params).mappings().all()

            legacy_payload = legacy_endpoint(
                employee_id=employee_id,
                from_date=from_date,
                to_date=to_date,
                db=db,
                current_user_id=current_user_id,
            )
            legacy_records = legacy_payload.get("records", []) if isinstance(legacy_payload, dict) else []
            if not rows:
                return legacy_payload

            records = _combine_shift_and_legacy_records(rows, legacy_records)
            return {
                "employee_id": employee_id,
                "records": records,
                "total_records": len(records),
            }
        return get_shift_attendance

    def make_shift_date_endpoint(legacy_endpoint):
        def get_shift_attendance_by_date(date_str, employee_id=None, current_user_id=None, db=None):
            try:
                att_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                raise HTTPException(400, "Date must use YYYY-MM-DD format")

            if employee_id is None:
                actual_employee_id, worker_id = current_user_id, None
            else:
                actual_employee_id, worker_id = _resolve_employee(employee_id, current_user_id, db)

            rows = db.execute(text("""
                SELECT id, employee_id, worker_id, attendance_date, shift,
                       check_in_time, check_out_time, status, working_hours, checkout_reason
                FROM attendance_shifts
                WHERE employee_id = :employee_id
                  AND worker_id IS NOT DISTINCT FROM :worker_id
                  AND attendance_date = :attendance_date
                ORDER BY check_in_time DESC
            """), {
                "employee_id": actual_employee_id,
                "worker_id": worker_id,
                "attendance_date": att_date,
            }).mappings().all()

            legacy_payload = legacy_endpoint(
                date_str=date_str,
                employee_id=employee_id,
                current_user_id=current_user_id,
                db=db,
            )
            legacy_records = legacy_payload.get("records", []) if isinstance(legacy_payload, dict) else []
            if not rows:
                return legacy_payload

            records = _combine_shift_and_legacy_records(rows, legacy_records)
            statuses = [str(item.get("status", "PRESENT")).upper() for item in records]
            return {
                "date": date_str,
                "total_records": len(records),
                "present": sum(1 for status in statuses if status == "PRESENT"),
                "absent": sum(1 for status in statuses if status == "ABSENT"),
                "leave": sum(1 for status in statuses if status == "LEAVE"),
                "records": records,
            }
        return get_shift_attendance_by_date

    patched = set()
    for route in app_module.api.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())

        if path == "/api/attendance/check-in" and "POST" in methods:
            route.endpoint = shift_check_in
            route.dependant.call = shift_check_in
            patched.add("check-in")
        elif path == "/api/attendance/check-out" and "POST" in methods:
            route.endpoint = shift_check_out
            route.dependant.call = shift_check_out
            patched.add("check-out")
        elif path == "/api/attendance/employee/{employee_id}" and "GET" in methods:
            endpoint = make_shift_attendance_endpoint(route.endpoint)
            route.endpoint = endpoint
            route.dependant.call = endpoint
            patched.add("employee")
        elif path == "/api/attendance/date/{date_str}" and "GET" in methods:
            endpoint = make_shift_date_endpoint(route.endpoint)
            route.endpoint = endpoint
            route.dependant.call = endpoint
            patched.add("date")

    expected = {"check-in", "check-out", "employee", "date"}
    if patched == expected:
        print(
            "[ATTENDANCE] production routes patched: check-in, check-out, employee, date",
            flush=True,
        )
    else:
        print(
            f"[ATTENDANCE] route patch warning; found {sorted(patched)}, "
            f"expected {sorted(expected)}",
            flush=True,
        )

    return app_module.api

if __name__ == "__main__":
    _ensure_online_order_status_enum()
    _ensure_sales_reference_order_id()
    _ensure_online_delivery_payment_trigger()
    _ensure_shift_table()
    api = _patch_routes()
    # The FastAPI startup hook starts the scheduler for both production_boot.py
    # and direct `uvicorn app:api` launches; do not start a duplicate thread here.
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
