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
from db import sessionLocal, get_db
from security import get_current_user as check_current_user
from models import Attendance, LeaveRequest, User, Worker

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

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
    db: Session = Depends(get_db)
):
    """Update worker details"""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
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
    """Employee check-in - accepts both user_id and worker_id"""
    # First try to find as Worker
    employee = db.query(Worker).filter(Worker.id == employee_id).first()
    is_worker = employee is not None

    # If not found as Worker, try to find as User (for shopkeepers/owners checking in)
    if not employee:
        employee = db.query(User).filter(User.id == employee_id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Security check: verify the current user owns/manages this employee
    if is_worker:
        # For workers, check that the current user is the shopkeeper
        if employee.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check in your own workers")
    else:
        # For shopkeepers/owners, they can only check in themselves
        if employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check in yourself")

    today = date.today()
    
    # For workers, use shopkeeper_id as employee_id but store worker_id separately
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
            check_in_time=datetime.now(),
            status="PRESENT"
        )
        db.add(attendance)
    elif attendance.check_in_time is None:
        attendance.check_in_time = datetime.now()
        if attendance.status == "ABSENT":
            attendance.status = "PRESENT"
    else:
        raise HTTPException(status_code=400, detail="Already checked in today")

    try:
        db.commit()
        db.refresh(attendance)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Check-in failed: {str(e)}")

    return {
        "message": "Check-in successful",
        "employee_id": actual_employee_id,
        "worker_id": worker_id_to_store,
        "check_in_time": attendance.check_in_time,
        "status": attendance.status
    }

@router.post("/check-out")
def employee_check_out(
    employee_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Employee check-out - accepts both user_id and worker_id"""
    # First try to find as Worker
    employee = db.query(Worker).filter(Worker.id == employee_id).first()
    is_worker = employee is not None

    # If not found as Worker, try to find as User (for shopkeepers/owners checking out)
    if not employee:
        employee = db.query(User).filter(User.id == employee_id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Security check: verify the current user owns/manages this employee
    if is_worker:
        # For workers, check that the current user is the shopkeeper
        if employee.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check out your own workers")
    else:
        # For shopkeepers/owners, they can only check out themselves
        if employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check out yourself")
    """Employee check-out - accepts both user_id and worker_id"""
    # First try to find as Worker
    employee = db.query(Worker).filter(Worker.id == employee_id).first()
    is_worker = employee is not None

    # If not found as Worker, try to find as User (for shopkeepers/owners checking out)
    if not employee:
        employee = db.query(User).filter(User.id == employee_id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Security check: verify the current user owns/manages this employee
    if is_worker:
        # For workers, check that the current user is the shopkeeper
        if employee.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check out your own workers")
    else:
        # For shopkeepers/owners, they can only check out themselves
        if employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only check out yourself")

    today = date.today()
    
    # For workers, use shopkeeper_id as employee_id but store worker_id separately
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
        raise HTTPException(status_code=400, detail="No check-in found for today")

    if attendance.check_out_time:
        raise HTTPException(status_code=400, detail="Already checked out today")

    attendance.check_out_time = datetime.now()

    # Calculate working hours
    if attendance.check_in_time and attendance.check_out_time:
        duration = attendance.check_out_time - attendance.check_in_time
        attendance.working_hours = duration.total_seconds() / 3600  # Convert to hours

    try:
        db.commit()
        db.refresh(attendance)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Check-out failed: {str(e)}")

    return {
        "message": "Check-out successful",
        "employee_id": actual_employee_id,
        "worker_id": worker_id_to_store,
        "check_out_time": attendance.check_out_time,
        "working_hours": attendance.working_hours
    }

# ==================== ATTENDANCE RECORDS ====================

@router.post("/record-manual")
def record_manual_attendance(
    record: AttendanceRecord,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(check_current_user)
):
    """Manually record attendance"""
    # Accept worker_id from Worker table (or user_id from User table)
    employee = db.query(Worker).filter(Worker.id == record.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Security check: verify the current user owns this worker
    if employee.shopkeeper_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only record attendance for your own workers")
    
    att_date = datetime.strptime(record.attendance_date, "%Y-%m-%d").date()
    
    # Normalize status to uppercase valid enum value
    VALID_STATUSES = {"PRESENT", "ABSENT", "LEAVE", "HALF_DAY", "LATE"}
    normalized_status = record.status.upper()
    if normalized_status not in VALID_STATUSES:
        # Map common aliases
        STATUS_MAP = {"present": "PRESENT", "absent": "ABSENT", "leave": "LEAVE",
                      "half_day": "HALF_DAY", "halfday": "HALF_DAY", "late": "LATE"}
        normalized_status = STATUS_MAP.get(record.status.lower(), "PRESENT")
    
    # Use worker.shopkeeper_id as the employee reference for Attendance
    # Attendance.employee_id FK references user_details.id (shopkeeper), not worker
    # Worker attendance is keyed by Worker.id. Keep shopkeeper_id only as the
    # tenant/owner reference for the Attendance.employee_id FK.
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
    # Security check: verify the current user has access to this employee's data
    # First check if it's a worker belonging to the current user
    worker = db.query(Worker).filter(Worker.id == employee_id).first()
    if worker:
        if worker.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only view your own workers' attendance")
    else:
        # If not a worker, it might be the shopkeeper themselves
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
    db: Session = Depends(get_db)
):
    """Get all attendance records for a specific date (optionally filtered by employee_id)"""
    att_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Build query
    query = db.query(Attendance).filter(Attendance.attendance_date == att_date)

    # Filter by employee_id if provided
    if employee_id is not None:
        query = query.filter(Attendance.employee_id == employee_id)

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
    db: Session = Depends(get_db)
):
    """Request leave"""
    employee = db.query(Worker).filter(Worker.id == leave_request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    from_dt = datetime.strptime(leave_request.from_date, "%Y-%m-%d").date()
    to_dt = datetime.strptime(leave_request.to_date, "%Y-%m-%d").date()
    
    if to_dt < from_dt:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")
    
    # Normalize leave_type to valid enum values
    VALID_LEAVE_TYPES = {"VACATION", "SICK", "PERSONAL"}
    LEAVE_TYPE_MAP = {
        "casual": "PERSONAL", "cl": "PERSONAL", "annual": "VACATION",
        "earned": "VACATION", "medical": "SICK", "sl": "SICK",
        "vacation": "VACATION", "sick": "SICK", "personal": "PERSONAL"
    }
    normalized_leave_type = leave_request.leave_type.upper()
    if normalized_leave_type not in VALID_LEAVE_TYPES:
        normalized_leave_type = LEAVE_TYPE_MAP.get(leave_request.leave_type.lower(), "PERSONAL")
    
    # Use the shopkeeper's user_id as employee_id (FK references user_details)
    employee_user_id = employee.shopkeeper_id
    
    db_leave = LeaveRequest(
        employee_id=employee_user_id,
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
    db: Session = Depends(get_db)
):
    """Get leave requests"""
    query = db.query(LeaveRequest)
    
    if employee_id:
        query = query.filter(LeaveRequest.employee_id == employee_id)
    
    if status:
        query = query.filter(LeaveRequest.status == status)
    
    requests = query.order_by(desc(LeaveRequest.created_at)).all()
    
    return {
        "leave_requests": requests,
        "total": len(requests)
    }

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
    
    # Security check: verify the current user owns/manages this employee
    worker = db.query(Worker).filter(Worker.id == leave.employee_id).first()
    if worker:
        if worker.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only approve leave for your own workers")
    else:
        # If not a worker, check if it's the shopkeeper themselves
        if leave.employee_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only approve leave for yourself or your workers")
    
    leave.status = "APPROVED"
    
    # Create attendance records for leave period
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
    
    # Security check: verify the current user owns/manages this employee
    worker = db.query(Worker).filter(Worker.id == leave.employee_id).first()
    if worker:
        if worker.shopkeeper_id != current_user_id:
            raise HTTPException(status_code=403, detail="You can only reject leave for your own workers")
    else:
        # If not a worker, check if it's the shopkeeper themselves
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
    db: Session = Depends(get_db)
):
    """Get attendance summary for past N days"""
    cutoff_date = date.today() - timedelta(days=days)
    
    records = db.query(Attendance).filter(
        Attendance.attendance_date >= cutoff_date
    ).all()
    
    employees = db.query(User).all()
    
    present = sum(1 for r in records if r.status == "PRESENT")
    absent = sum(1 for r in records if r.status == "ABSENT")
    leave = sum(1 for r in records if r.status == "LEAVE")
    
    return {
        "period_days": days,
        "total_records": len(records),
        "present": present,
        "absent": absent,
        "leave": leave,
        "total_employees": len(employees),
        "attendance_percentage": (present / len(records) * 100) if records else 0
    }

@router.get("/analytics/employee/{employee_id}")
def get_employee_analytics(
    employee_id: int,
    days: int = Query(30),
    db: Session = Depends(get_db)
):
    """Get analytics for specific employee"""
    cutoff_date = date.today() - timedelta(days=days)
    
    records = db.query(Attendance).filter(
        and_(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date >= cutoff_date
        )
    ).all()
    
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