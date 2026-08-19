"""
Attendance Management Router
Check-in/Check-out, Attendance tracking, Leave management, Attendance analytics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
from sqlalchemy.exc import IntegrityError
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

    attendance_filters = [
        Attendance.employee_id == actual_employee_id,
        Attendance.attendance_date == today,
    ]
    if worker_id_to_store is None:
        attendance_filters.append(Attendance.worker_id.is_(None))
    else:
        attendance_filters.append(Attendance.worker_id == worker_id_to_store)

    attendance = db.query(Attendance).filter(and_(*attendance_filters)).first()

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
    except IntegrityError:
        # A concurrent second request may race past the SELECT before the
        # first transaction commits. The DB uniqueness rule is the final
        # authority; reconcile the conflict to the existing attendance row
        # instead of returning a misleading 500.
        db.rollback()
        existing_filters = [
            Attendance.employee_id == actual_employee_id,
            Attendance.attendance_date == today,
        ]
        if worker_id_to_store is None:
            existing_filters.append(Attendance.worker_id.is_(None))
        else:
            existing_filters.append(Attendance.worker_id == worker_id_to_store)

        existing = db.query(Attendance).filter(and_(*existing_filters)).first()
        if existing is None:
            raise HTTPException(status_code=500, detail="Check-in failed: could not reconcile after conflict")
        return {
            "message": "Already checked in today",
            "employee_id": actual_employee_id,
            "worker_id": worker_id_to_store,
            "check_in_time": existing.check_in_time,
            "status": existing.status,
        }
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

    today = date.today()
    
    # For workers, use shopkeeper_id as employee_id but store worker_id separately
    actual_employee_id = employee.shopkeeper_id if is_worker else employee_id
    worker_id_to_store = employee.id if is_worker else None

    attendance_filters = [
        Attendance.employee_id == actual_employee_id,
        Attendance.attendance_date == today,
    ]
    if worker_id_to_store is None:
        attendance_filters.append(Attendance.worker_id.is_(None))
    else:
        attendance_filters.append(Attendance.worker_id == worker_id_to_store)

    attendance = db.query(Attendance).filter(and_(*attendance_filters)).first()

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
        STATUS_MAP = {"present": "PRESENT", "absent": "ABSENT", "leave": "LEAVE",
                      "half_day": "HALF_DAY", "halfday": "HALF_DAY", "late": "LATE"}
        normalized_status = STATUS_MAP.get(record.status.lower(), "PRESENT")
    
    # Attendance.employee_id is the shopkeeper/user FK; worker_id identifies a worker.
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
    """Request leave for a worker"""
    employee = db.query(Worker).filter(Worker.id == leave_request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if employee.shopkeeper_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only request leave for your own workers")

    try:
        from_date = datetime.strptime(leave_request.from_date, "%Y-%m-%d").date()
        to_date = datetime.strptime(leave_request.to_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if to_date < from_date:
        raise HTTPException(status_code=400, detail="to_date cannot be before from_date")

    leave = LeaveRequest(
        employee_id=leave_request.employee_id,
        leave_type=leave_request.leave_type,
        from_date=from_date,
        to_date=to_date,
        reason=leave_request.reason,
        status="PENDING"
    )
    db.add(leave)
    try:
        db.commit()
        db.refresh(leave)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to request leave: {str(e)}")

    return {"message": "Leave request submitted successfully", "leave_id": leave.id}

@router.get("/leave-requests")
def get_leave_requests(
    current_user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Get leave requests for the current user's workers"""
    workers = db.query(Worker).filter(Worker.shopkeeper_id == current_user_id).all()
    worker_ids = [w.id for w in workers]
    if not worker_ids:
        return []

    return db.query(LeaveRequest).filter(LeaveRequest.employee_id.in_(worker_ids)).all()

@router.put("/leave-requests/{leave_id}")
def update_leave_request(
    leave_id: int,
    status: str = Query(...),
    current_user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Approve or reject a leave request"""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    employee = db.query(Worker).filter(Worker.id == leave.employee_id).first()
    if not employee or employee.shopkeeper_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only update leave requests for your workers")

    if status.upper() not in ["APPROVED", "REJECTED"]:
        raise HTTPException(status_code=400, detail="Status must be APPROVED or REJECTED")

    leave.status = status.upper()
    try:
        db.commit()
        db.refresh(leave)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update leave request: {str(e)}")

    return {"message": f"Leave request {status.lower()} successfully", "leave_id": leave_id}

@router.get("/summary")
def get_attendance_summary(
    current_user_id: int = Depends(check_current_user),
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get attendance summary for current user's workers"""
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year
    
    # Get workers for this shopkeeper
    workers = db.query(Worker).filter(Worker.shopkeeper_id == current_user_id).all()
    worker_ids = [w.id for w in workers]
    
    # Get attendance records for the month
    query = db.query(Attendance).filter(
        Attendance.employee_id == current_user_id,
        func.extract('month', Attendance.attendance_date) == target_month,
        func.extract('year', Attendance.attendance_date) == target_year
    )
    
    records = query.all()
    
    # Group by employee
    summary = {}
    for record in records:
        emp_id = record.worker_id or record.employee_id
        if emp_id not in summary:
            summary[emp_id] = {"present": 0, "absent": 0, "leave": 0, "half_day": 0, "total": 0}
        summary[emp_id]["total"] += 1
        status = record.status.lower()
        if status == "present":
            summary[emp_id]["present"] += 1
        elif status == "absent":
            summary[emp_id]["absent"] += 1
        elif status == "leave":
            summary[emp_id]["leave"] += 1
        elif status == "half_day":
            summary[emp_id]["half_day"] += 1
    
    return {
        "month": target_month,
        "year": target_year,
        "summary": summary,
        "workers_count": len(workers),
        "total_records": len(records)
    }

@router.get("/today")
def get_today_attendance(
    current_user_id: int = Depends(check_current_user),
    db: Session = Depends(get_db)
):
    """Get today's attendance for all workers"""
    today = date.today()
    
    workers = db.query(Worker).filter(Worker.shopkeeper_id == current_user_id).all()
    worker_ids = [w.id for w in workers]
    
    if not worker_ids:
        return []
    
    records = db.query(Attendance).filter(
        Attendance.employee_id == current_user_id,
        Attendance.worker_id.in_(worker_ids),
        Attendance.attendance_date == today
    ).all()
    
    return records

@router.get("/stats")
def get_attendance_stats(
    current_user_id: int = Depends(check_current_user),
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get detailed attendance statistics"""
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year
    
    workers = db.query(Worker).filter(Worker.shopkeeper_id == current_user_id).all()
    worker_ids = [w.id for w in workers]
    
    if not worker_ids:
        return {"total_workers": 0, "statistics": {}}
    
    records = db.query(Attendance).filter(
        Attendance.employee_id == current_user_id,
        Attendance.worker_id.in_(worker_ids),
        func.extract('month', Attendance.attendance_date) == target_month,
        func.extract('year', Attendance.attendance_date) == target_year
    ).all()
    
    stats = {}
    for worker in workers:
        worker_records = [r for r in records if r.worker_id == worker.id]
        present = sum(1 for r in worker_records if r.status == "PRESENT")
        absent = sum(1 for r in worker_records if r.status == "ABSENT")
        leave = sum(1 for r in worker_records if r.status == "LEAVE")
        half_day = sum(1 for r in worker_records if r.status == "HALF_DAY")
        total_days = len(worker_records)
        
        stats[worker.id] = {
            "worker_name": worker.name,
            "present": present,
            "absent": absent,
            "leave": leave,
            "half_day": half_day,
            "total_days": total_days,
            "attendance_percentage": round((present / total_days * 100) if total_days > 0 else 0, 2)
        }
    
    return {
        "total_workers": len(workers),
        "statistics": stats
    }
