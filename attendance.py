"""
Attendance Management Router
Check-in/Check-out, Attendance tracking, Leave management, Attendance analytics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from pydantic import BaseModel, Field
from datetime import datetime, date, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo
import json
from db import sessionLocal, get_db
from security import get_current_user as check_current_user
from models import Attendance, LeaveRequest, User, Worker

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

# Three attendance sessions per business day.  Times are evaluated in India time
# because Retail Mind is intended for the Indian retail market.
ATTENDANCE_TZ = ZoneInfo("Asia/Kolkata")
ATTENDANCE_SESSIONS = (
    ("morning", 6, 12, "Morning", "6:00 AM–12:00 PM"),
    ("afternoon", 12, 17, "Afternoon", "12:00 PM–5:00 PM"),
    ("evening", 17, 24, "Evening", "5:00 PM–12:00 AM"),
)
SESSION_META_KEY = "_retail_mind_sessions"


def _local_now():
    return datetime.now(ATTENDANCE_TZ)


def _session_for_time(value=None):
    value = value or _local_now()
    hour = value.hour
    for key, start_hour, end_hour, label, window in ATTENDANCE_SESSIONS:
        if start_hour <= hour < end_hour:
            return key, label, window
    return None, None, None


def _session_meta(attendance):
    """Read session history stored in the existing notes column.

    This deliberately avoids a schema change so existing production databases
    and existing attendance rows remain compatible.
    """
    raw = attendance.notes or ""
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and isinstance(data.get(SESSION_META_KEY), dict):
            return data
    except (TypeError, ValueError):
        pass
    return {SESSION_META_KEY: {}, "note": raw if raw else None}


def _save_session_meta(attendance, data):
    attendance.notes = json.dumps(data, separators=(",", ":"), default=str)


def _completed_session_message(meta, current_key):
    completed = meta.get(SESSION_META_KEY, {})
    session = completed.get(current_key)
    if session and session.get("check_in_time"):
        label = session.get("label", current_key.title())
        _, next_label, next_window = next((x for x in ATTENDANCE_SESSIONS if x[0] != current_key and x[2] == session.get("next_window")), (None, None, None)) if False else (None, None, None)
        remaining = []
        for key, start_hour, end_hour, session_label, window in ATTENDANCE_SESSIONS:
            if key != current_key and not completed.get(key, {}).get("check_in_time"):
                remaining.append(f"{session_label} ({window})")
        next_text = f" Try {remaining[0]}." if remaining else " All three sessions are already marked for today."
        return f"{label} attendance already marked for today.{next_text}"
    return None

# ==================== PYDANTIC MODELS FOR WORKERS ====================

class WorkerCreate(BaseModel):
    name: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    salary: float = 0
    assigned_work: Optional[str] = ""
    position: Optional[str] = "Staff"
    pin: Optional[str] = ""

class WorkerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    salary: Optional[float] = None
    assigned_work: Optional[str] = None
    position: Optional[str] = None
    pin: Optional[str] = None

# ==================== WORKER MANAGEMENT ====================

@router.post("/workers")
def create_worker(
    worker_data: WorkerCreate,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Create a new worker for a shopkeeper"""
    worker = Worker(
        shopkeeper_id=user_id,
        **worker_data.dict()
    )
    db.add(worker)
    try:
        db.commit()
        db.refresh(worker)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create worker: {str(e)}")
    return worker

@router.get("/workers")
def get_workers(
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Get all workers for a shopkeeper"""
    return db.query(Worker).filter(Worker.shopkeeper_id == user_id).all()

@router.put("/workers/{worker_id}")
def update_worker(
    worker_id: int,
    data: WorkerUpdate,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Update worker details belonging to the authenticated shopkeeper."""
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.shopkeeper_id == user_id,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(worker, key, value)
    try:
        db.commit()
        db.refresh(worker)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update worker: {str(e)}")
    return worker

@router.delete("/workers/{worker_id}")
def delete_worker(
    worker_id: int,
    user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Delete a worker from the database"""
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.shopkeeper_id == user_id  # Fixed: use shopkeeper_id not shop_id
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    db.delete(worker)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete worker: {str(e)}")
    return {"message": "Worker deleted successfully", "worker_id": worker_id}


# ==================== PYDANTIC MODELS ====================

class CheckInOut(BaseModel):
    employee_id: int
    check_in: bool = True  # True for check-in, False for check-out

class AttendanceRecord(BaseModel):
    employee_id: int
    attendance_date: str
    status: str  # PRESENT, ABSENT, LEAVE, HALF_DAY
    notes: Optional[str] = None

class LeaveRequestCreate(BaseModel):
    employee_id: int
    leave_type: str  # VACATION, SICK, PERSONAL
    from_date: str
    to_date: str
    reason: Optional[str] = None

class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    attendance_date: date
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    status: str
    working_hours: float

    class Config:
        from_attributes = True

# ==================== CHECK-IN/CHECK-OUT ====================

@router.post("/check-in")
def employee_check_in(
    employee_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Check in once per morning/afternoon/evening session.

    The active session is represented by the existing check_in_time and
    check_out_time fields. Completed sessions are retained in notes as JSON,
    so clearing mobile app data does not reset the server-side state.
    """
    employee = db.query(Worker).filter(Worker.id == employee_id).first()
    is_worker = employee is not None

    if not employee:
        employee = db.query(User).filter(User.id == employee_id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if is_worker:
        if employee.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check in your own workers")
    else:
        if employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check in yourself")

    today = date.today()
    now = _local_now()
    session_key, session_label, session_window = _session_for_time(now)
    if not session_key:
        raise HTTPException(status_code=400, detail="Attendance is currently outside the configured sessions.")

    actual_employee_id = employee.shopkeeper_id if is_worker else employee_id
    worker_id_to_store = employee.id if is_worker else None

    attendance = db.query(Attendance).filter(
        and_(
            Attendance.employee_id == actual_employee_id,
            Attendance.attendance_date == today,
            Attendance.worker_id == worker_id_to_store if worker_id_to_store is not None else True
        )
    ).first()

    if not attendance:
        attendance = Attendance(
            employee_id=actual_employee_id,
            worker_id=worker_id_to_store,
            attendance_date=today,
            check_in_time=now.replace(tzinfo=None),
            status="PRESENT",
            working_hours=0.0
        )
        meta = {SESSION_META_KEY: {}}
        meta[SESSION_META_KEY][session_key] = {
            "label": session_label,
            "window": session_window,
            "check_in_time": now.isoformat(),
            "check_out_time": None,
            "working_hours": 0.0,
        }
        _save_session_meta(attendance, meta)
        db.add(attendance)
    else:
        meta = _session_meta(attendance)
        completed_message = _completed_session_message(meta, session_key)
        if completed_message:
            raise HTTPException(status_code=400, detail=completed_message)

        # If the current row is still active, do not create a duplicate check-in.
        if attendance.check_in_time and not attendance.check_out_time:
            active_meta = meta.get(SESSION_META_KEY, {})
            active_label = active_meta.get("active_session", session_label)
            raise HTTPException(status_code=400, detail=f"{active_label.title()} attendance is currently checked in. Please check out before starting another session.")

        # The previous session is completed. Reuse the existing attendance row
        # for the new active session and retain the completed session in notes.
        attendance.check_in_time = now.replace(tzinfo=None)
        attendance.check_out_time = None
        attendance.working_hours = 0.0
        meta.setdefault(SESSION_META_KEY, {})[session_key] = {
            "label": session_label,
            "window": session_window,
            "check_in_time": now.isoformat(),
            "check_out_time": None,
            "working_hours": 0.0,
        }
        meta[SESSION_META_KEY]["active_session"] = session_key
        _save_session_meta(attendance, meta)
        if attendance.status == "ABSENT":
            attendance.status = "PRESENT"

    try:
        meta = _session_meta(attendance)
        meta.setdefault(SESSION_META_KEY, {})["active_session"] = session_key
        _save_session_meta(attendance, meta)
        db.commit()
        db.refresh(attendance)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Check-in failed: {str(e)}")

    return {
        "message": f"{session_label} check-in successful",
        "employee_id": actual_employee_id,
        "worker_id": worker_id_to_store,
        "session": session_key,
        "session_label": session_label,
        "session_window": session_window,
        "check_in_time": attendance.check_in_time,
        "check_out_time": attendance.check_out_time,
        "status": attendance.status,
        "can_check_out": True
    }

@router.post("/check-out")
def employee_check_out(
    employee_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Check out the currently active attendance session."""
    employee = db.query(Worker).filter(Worker.id == employee_id).first()
    is_worker = employee is not None

    if not employee:
        employee = db.query(User).filter(User.id == employee_id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if is_worker:
        if employee.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check out your own workers")
    else:
        if employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check out yourself")

    today = date.today()
    actual_employee_id = employee.shopkeeper_id if is_worker else employee_id
    worker_id_to_store = employee.id if is_worker else None

    attendance = db.query(Attendance).filter(
        and_(
            Attendance.employee_id == actual_employee_id,
            Attendance.attendance_date == today,
            Attendance.worker_id == worker_id_to_store if worker_id_to_store is not None else True
        )
    ).first()

    if not attendance or not attendance.check_in_time:
        raise HTTPException(status_code=400, detail="No active check-in found for today")

    if attendance.check_out_time:
        meta = _session_meta(attendance)
        active_session = meta.get(SESSION_META_KEY, {}).get("active_session")
        if active_session:
            label = next((x[3] for x in ATTENDANCE_SESSIONS if x[0] == active_session), active_session.title())
            raise HTTPException(status_code=400, detail=f"{label} attendance is already checked out. Try the next session when its time starts.")
        raise HTTPException(status_code=400, detail="Attendance is already checked out. Try the next session when its time starts.")

    now = _local_now().replace(tzinfo=None)
    attendance.check_out_time = now

    duration = attendance.check_out_time - attendance.check_in_time
    session_hours = max(0.0, duration.total_seconds() / 3600)
    attendance.working_hours = session_hours

    meta = _session_meta(attendance)
    sessions = meta.setdefault(SESSION_META_KEY, {})
    active_session = sessions.get("active_session")
    if not active_session:
        active_session, session_label, session_window = _session_for_time()
    else:
        match = next((x for x in ATTENDANCE_SESSIONS if x[0] == active_session), None)
        session_label = match[3] if match else active_session.title()
        session_window = match[4] if match else ""

    if active_session:
        sessions[active_session] = {
            "label": session_label,
            "window": session_window,
            "check_in_time": sessions.get(active_session, {}).get("check_in_time", attendance.check_in_time.isoformat()),
            "check_out_time": now.isoformat(),
            "working_hours": session_hours,
        }
    sessions.pop("active_session", None)
    _save_session_meta(attendance, meta)

    try:
        db.commit()
        db.refresh(attendance)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Check-out failed: {str(e)}")

    return {
        "message": f"{session_label} check-out successful",
        "employee_id": actual_employee_id,
        "worker_id": worker_id_to_store,
        "session": active_session,
        "session_label": session_label,
        "check_out_time": attendance.check_out_time,
        "working_hours": attendance.working_hours,
        "can_check_in_next_session": True
    }

# ==================== ATTENDANCE RECORDS ====================

@router.post("/record-manual")
def record_manual_attendance(
    record: AttendanceRecord,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Manually record attendance"""
    employee = db.query(Worker).filter(Worker.id == record.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if employee.shopkeeper_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only record attendance for your own workers")
    
    att_date = datetime.strptime(record.attendance_date, "%Y-%m-%d").date()
    
    VALID_STATUSES = {"PRESENT", "ABSENT", "LEAVE", "HALF_DAY", "LATE"}
    normalized_status = record.status.upper()
    if normalized_status not in VALID_STATUSES:
        STATUS_MAP = {"present": "PRESENT", "absent": "ABSENT", "leave": "LEAVE",
                      "half_day": "HALF_DAY", "halfday": "HALF_DAY", "late": "LATE"}
        normalized_status = STATUS_MAP.get(record.status.lower(), "PRESENT")
    
    worker_id = employee.id
    employee_user_id = employee.shopkeeper_id

    existing = db.query(Attendance).filter(
        and_(
            Attendance.worker_id == worker_id,
            Attendance.attendance_date == att_date
        )
    ).first()

    if existing:
        existing.employee_id = employee_user_id
        existing.worker_id = worker_id
        existing.status = normalized_status.upper().replace('-', '_')
        existing.notes = record.notes
        db.add(existing)
    else:
        attendance = Attendance(
            employee_id=employee_user_id,
            worker_id=worker_id,
            attendance_date=att_date,
            status=normalized_status.upper().replace('-', '_'),
            notes=record.notes
        )
        db.add(attendance)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record attendance: {str(e)}")
    
    return {"message": "Attendance recorded successfully", "worker_id": record.employee_id, "status": normalized_status}

@router.get("/employee/{employee_id}")
def get_employee_attendance(
    employee_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Get attendance records for an employee"""
    worker = db.query(Worker).filter(Worker.id == employee_id).first()
    if worker:
        if worker.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only view your own workers' attendance")
    else:
        if employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only view your own attendance")
    
    if worker:
        query = db.query(Attendance).filter(Attendance.worker_id == worker.id)
    else:
        query = db.query(Attendance).filter(Attendance.employee_id == employee_id)
    
    if from_date:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
        query = query.filter(Attendance.attendance_date >= from_dt)
    
    if to_date:
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
        query = query.filter(Attendance.attendance_date <= to_dt)
    
    records = query.order_by(desc(Attendance.attendance_date)).all()
    
    return {
        "employee_id": employee_id,
        "records": records,
        "total_records": len(records)
    }

@router.get("/date/{date_str}")
def get_attendance_by_date(
    date_str: str,
    employee_id: Optional[int] = Query(None),
    current_user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Get all attendance records for a specific date (optionally filtered by employee_id)"""
    att_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    query = db.query(Attendance).filter(Attendance.attendance_date == att_date)

    if employee_id is not None:
        worker = db.query(Worker).filter(Worker.id == employee_id).first()
        if worker is not None:
            if worker.shopkeeper_id != current_user_id:
                raise HTTPException(status_code=403, detail="You can only view your own workers' attendance")
            query = query.filter(Attendance.worker_id == worker.id)
        else:
            if employee_id != current_user_id:
                raise HTTPException(status_code=403, detail="You can only view your own attendance")
            query = query.filter(Attendance.employee_id == current_user_id)
    else:
        query = query.filter(Attendance.employee_id == current_user_id)

    records = query.order_by(desc(Attendance.attendance_date)).all()
    present = sum(1 for r in records if r.status == "PRESENT")
    absent = sum(1 for r in records if r.status == "ABSENT")
    leave = sum(1 for r in records if r.status == "LEAVE")

    return {
        "date": att_date,
        "total_records": len(records),
        "present": present,
        "absent": absent,
        "leave": leave,
        "records": records
    }

# ==================== LEAVE MANAGEMENT ====================

@router.post("/leave-request")
def request_leave(
    leave_request: LeaveRequestCreate,
    current_user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Request leave for a worker owned by the authenticated shopkeeper."""
    employee = db.query(Worker).filter(Worker.id == leave_request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if employee.shopkeeper_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only request leave for your own workers")

    from_dt = datetime.strptime(leave_request.from_date, "%Y-%m-%d").date()
    to_dt = datetime.strptime(leave_request.to_date, "%Y-%m-%d").date()
    if to_dt < from_dt:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")

    valid_leave_types = {"VACATION", "SICK", "PERSONAL"}
    leave_type_map = {
        "casual": "PERSONAL", "cl": "PERSONAL", "annual": "VACATION",
        "earned": "VACATION", "medical": "SICK", "sl": "SICK",
        "vacation": "VACATION", "sick": "SICK", "personal": "PERSONAL"
    }
    normalized_leave_type = leave_request.leave_type.upper()
    if normalized_leave_type not in valid_leave_types:
        normalized_leave_type = leave_type_map.get(leave_request.leave_type.lower(), "PERSONAL")

    db_leave = LeaveRequest(
        employee_id=employee.shopkeeper_id,
        leave_type=normalized_leave_type,
        from_date=from_dt,
        to_date=to_dt,
        reason=leave_request.reason,
        status="PENDING"
    )
    db.add(db_leave)
    try:
        db.commit()
        db.refresh(db_leave)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create leave request: {str(e)}")
    return db_leave

@router.get("/leave-requests")
def get_leave_requests(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Get leave requests scoped to the authenticated shopkeeper."""
    query = db.query(LeaveRequest).filter(LeaveRequest.employee_id == current_user_id)

    if employee_id is not None:
        worker = db.query(Worker).filter(Worker.id == employee_id).first()
        if worker and worker.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only view your own workers' leave requests")
        if not worker and employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="Employee not found")

    if status:
        query = query.filter(LeaveRequest.status == status)

    requests = query.order_by(desc(LeaveRequest.created_at)).all()
    return {"leave_requests": requests, "total": len(requests)}

@router.put("/leave-request/{leave_id}/approve")
def approve_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Approve leave request"""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    worker = db.query(Worker).filter(Worker.id == leave.employee_id).first()
    if worker:
        if worker.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only approve leave for your own workers")
    else:
        if leave.employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only approve leave for yourself or your workers")
    
    leave.status = "APPROVED"
    
    from_date = leave.from_date if isinstance(leave.from_date, date) else leave.from_date.date()
    to_date = leave.to_date if isinstance(leave.to_date, date) else leave.to_date.date()
    current = from_date
    while current <= to_date:
        existing = db.query(Attendance).filter(
            and_(
            Attendance.employee_id == leave.employee_id,
            Attendance.attendance_date == current
            )
        ).first()
        
        if not existing:
            attendance = Attendance(
            employee_id=leave.employee_id,
            attendance_date=current,
            status="LEAVE"
            )
            db.add(attendance)
    
        current += timedelta(days=1)
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to approve leave: {str(e)}")

    return {"message": "Leave approved"}

@router.put("/leave-request/{leave_id}/reject")
def reject_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Reject leave request"""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    
    worker = db.query(Worker).filter(Worker.id == leave.employee_id).first()
    if worker:
        if worker.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only reject leave for your own workers")
    else:
        if leave.employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only reject leave for yourself or your workers")
    
    leave.status = "REJECTED"
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reject leave: {str(e)}")
    
    return {"message": "Leave rejected"}

# ==================== ANALYTICS ====================

@router.get("/analytics/summary")
def get_attendance_summary(
    days: int = Query(30),
    current_user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Get attendance summary for the authenticated shopkeeper's records."""
    days = max(1, min(days, 366))
    cutoff_date = date.today() - timedelta(days=days)
    
    records = db.query(Attendance).filter(
        Attendance.employee_id == current_user_id,
        Attendance.attendance_date >= cutoff_date
    ).all()
    
    worker_count = db.query(func.count(Worker.id)).filter(
        Worker.shopkeeper_id == current_user_id
    ).scalar() or 0
    
    present = sum(1 for r in records if r.status == "PRESENT")
    absent = sum(1 for r in records if r.status == "ABSENT")
    leave = sum(1 for r in records if r.status == "LEAVE")
    
    return {
        "period_days": days,
        "total_records": len(records),
        "present": present,
        "absent": absent,
        "leave": leave,
        "total_employees": int(worker_count) + 1,
        "attendance_percentage": (present / len(records) * 100) if records else 0
    }

@router.get("/analytics/employee/{employee_id}")
def get_employee_analytics(
    employee_id: int,
    days: int = Query(30),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Get analytics for a worker belonging to the authenticated shopkeeper, or the shopkeeper."""
    worker = db.query(Worker).filter(Worker.id == employee_id).first()
    if worker:
        if worker.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only view your own workers' analytics")
        query = db.query(Attendance).filter(Attendance.worker_id == worker.id)
    else:
        if employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only view your own attendance analytics")
        query = db.query(Attendance).filter(
            Attendance.employee_id == current_user_id,
            Attendance.worker_id.is_(None)
        )

    days = max(1, min(days, 366))
    cutoff_date = date.today() - timedelta(days=days)
    records = query.filter(Attendance.attendance_date >= cutoff_date).all()

    present = sum(1 for r in records if r.status == "PRESENT")
    absent = sum(1 for r in records if r.status == "ABSENT")
    leave = sum(1 for r in records if r.status == "LEAVE")
    total_hours = sum(r.working_hours for r in records if r.working_hours)
    
    return {
        "employee_id": employee_id,
        "period_days": days,
        "present": present,
        "absent": absent,
        "leave": leave,
        "total_working_hours": total_hours,
        "attendance_percentage": (present / len(records) * 100) if records else 0
    }
