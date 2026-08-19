"""Production bootstrap for backend-only compatibility fixes.

Keeps the existing Flutter/API contracts while fixing invoice numeric types and
adding shift-aware worker attendance without replacing the main route modules.
Render should start this file after Alembic migrations.
"""

from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo
import os

from fastapi import HTTPException
from fastapi.dependencies.utils import get_dependant
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
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_attendance_shift UNIQUE
                    (employee_id, worker_id, attendance_date, shift)
            )
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


def _patch_routes():
    import app as app_module
    import invoices_billing
    import attendance

    # Existing mobile payloads use float quantities. PostgreSQL NUMERIC values
    # are Decimal. Convert the Pydantic values before the existing sync logic
    # performs stock arithmetic. No Flutter change is required.
    for route in invoices_billing.router.routes:
        if getattr(route, "path", "") == "/sync" and "POST" in getattr(route, "methods", set()):
            original = route.endpoint

            def invoice_sync_wrapper(data, db, current_user, _original=original):
                for item in data.line_items or []:
                    object.__setattr__(item, "quantity", Decimal(str(item.quantity)))
                    object.__setattr__(item, "unit_price", Decimal(str(item.unit_price)))
                    object.__setattr__(item, "discount_amount", Decimal(str(item.discount_amount)))
                return _original(data=data, db=db, current_user=current_user)

            route.endpoint = invoice_sync_wrapper
            route.dependant = get_dependant(path=route.path, call=invoice_sync_wrapper)
            break

    def shift_check_in(employee_id: int, db, current_user_id: int):
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
        }

    def shift_check_out(employee_id: int, db, current_user_id: int):
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
            SET check_out_time = :check_out_time, working_hours = :working_hours
            WHERE id = :id
        """), {"check_out_time": now, "working_hours": hours, "id": row["id"]})
        db.commit()
        return {
            "message": f"{row['shift'].title()} check-out successful",
            "employee_id": actual_employee_id,
            "worker_id": worker_id,
            "shift": row["shift"],
            "check_out_time": now.isoformat(),
            "working_hours": round(hours, 2),
        }

    def get_shift_attendance(employee_id: int, from_date=None, to_date=None, db=None, current_user_id=None):
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
            "check_in_time, check_out_time, status, working_hours "
            "FROM attendance_shifts WHERE " + " AND ".join(clauses) +
            " ORDER BY attendance_date DESC, check_in_time DESC"
        ), params).mappings().all()
        return {
            "employee_id": employee_id,
            "records": [dict(row) for row in rows],
            "total_records": len(rows),
        }

    for route in attendance.router.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if path == "/check-in" and "POST" in methods:
            route.endpoint = shift_check_in
            route.dependant = get_dependant(path=route.path, call=shift_check_in)
        elif path == "/check-out" and "POST" in methods:
            route.endpoint = shift_check_out
            route.dependant = get_dependant(path=route.path, call=shift_check_out)
        elif path == "/employee/{employee_id}" and "GET" in methods:
            route.endpoint = get_shift_attendance
            route.dependant = get_dependant(path=route.path, call=get_shift_attendance)

    return app_module.api


if __name__ == "__main__":
    _ensure_shift_table()
    api = _patch_routes()
    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
