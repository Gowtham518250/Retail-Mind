"""
🏦 BANK RECONCILIATION API — AI Shop Pro Enterprise Backend
📊 RETAIL INTELLIGENCE API — AI Shop Pro Enterprise Backend
Covers:
  - Daily UPI/Cash reconciliation entries
  - Discrepancy flagging
  - Unified P&L (Profit & Loss) from Universal Transactions
  - Expense Tracker endpoints
  - Fast-moving vs Dead-stock analysis
  - Worker Management (salary tracking, shift assignment)
"""

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List
from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, and_

from db import get_db
from models import (
    BankReconciliation, UniversalTransaction, ShopExpense,
    Worker, Product, sales, Invoice, Customer, InvoiceLineItem
)
from security import owner_only, worker_or_owner, sanitize_input

router = APIRouter(tags=["Enterprise Intelligence"])

# =====================================
# EXPENSE TRACKER
# =====================================
class ExpenseCreate(BaseModel):
    category: str = Field(..., min_length=2, max_length=50)
    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = Field(None, max_length=200)
    expense_date: date
    payment_method: Optional[str] = Field(default="cash", max_length=50)
    # Optional for backwards compatibility. Clients should reuse this on retries.
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=128)


def _expense_money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _expense_matches(
    existing: ShopExpense,
    data: ExpenseCreate,
    category: str,
    description: Optional[str],
    payment_method: str,
) -> bool:
    """Only treat identical expense facts as an idempotent retry."""
    try:
        return (
            (existing.category or "").strip().casefold() == category.casefold()
            and _expense_money(existing.amount) == _expense_money(data.amount)
            and existing.expense_date == data.expense_date
            and (existing.description or None) == (description or None)
            and (existing.payment_method or "cash").strip().casefold() == payment_method.casefold()
        )
    except (ArithmeticError, TypeError, ValueError):
        return False


def _expense_response(expense: ShopExpense, *, duplicate: bool = False) -> dict:
    return {
        "message": "Expense already recorded; canonical record returned." if duplicate else "Expense logged successfully.",
        "expense_id": expense.id,
        "amount": float(expense.amount or 0),
        "category": expense.category,
        "description": expense.description,
        "expense_date": expense.expense_date.isoformat() if expense.expense_date else None,
        "payment_method": expense.payment_method,
        "duplicate": duplicate,
    }


@router.post("/expenses", tags=["Expense Tracker"])
def add_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Create an expense and its journal mirror as one retry-safe transaction."""
    shop_id = current_user["user_id"]
    category = sanitize_input(data.category, "category").strip()
    desc = sanitize_input(data.description or "", "description").strip() or None
    payment_method = sanitize_input(data.payment_method or "cash", "payment_method").strip() or "cash"
    idempotency_key = (data.idempotency_key or "").strip() or None

    if idempotency_key and len(idempotency_key) < 8:
        raise HTTPException(status_code=422, detail="idempotency_key must contain at least 8 non-space characters.")

    if idempotency_key:
        existing = db.query(ShopExpense).filter(
            ShopExpense.shop_id == shop_id,
            ShopExpense.idempotency_key == idempotency_key,
        ).first()
        if existing:
            if _expense_matches(existing, data, category, desc, payment_method):
                return _expense_response(existing, duplicate=True)
            raise HTTPException(
                status_code=409,
                detail="Expense idempotency key was reused with different financial details.",
            )

    expense = ShopExpense(
        shop_id=shop_id,
        category=category,
        amount=_expense_money(data.amount),
        description=desc,
        expense_date=data.expense_date,
        payment_method=payment_method,
        idempotency_key=idempotency_key,
    )
    db.add(expense)

    # Keep the source expense and reporting journal in one DB transaction.
    tx = UniversalTransaction(
        shop_id=shop_id,
        tx_type="EXPENSE",
        category=category.upper(),
        amount=_expense_money(data.amount),
        reference_id=(f"EXPENSE-{idempotency_key}" if idempotency_key else None),
        description=desc or f"{category} expense",
        tx_date=datetime.combine(data.expense_date, datetime.min.time()),
    )
    db.add(tx)
    try:
        db.commit()
        db.refresh(expense)
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(ShopExpense).filter(
                ShopExpense.shop_id == shop_id,
                ShopExpense.idempotency_key == idempotency_key,
            ).first()
            if existing and _expense_matches(existing, data, category, desc, payment_method):
                return _expense_response(existing, duplicate=True)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Expense idempotency key was reused with different financial details.",
                )
        raise HTTPException(status_code=409, detail="Expense write conflict; refresh records before retrying.")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to log expense.")

    return _expense_response(expense)


@router.get("/expenses", tags=["Expense Tracker"])
def list_expenses(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """List expenses and return totals/counts for the exact filtered set."""
    shop_id = current_user["user_id"]
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")

    q = db.query(ShopExpense).filter(ShopExpense.shop_id == shop_id)
    if start_date:
        q = q.filter(ShopExpense.expense_date >= start_date)
    if end_date:
        q = q.filter(ShopExpense.expense_date <= end_date)
    if category:
        safe_category = sanitize_input(category, "category").strip()
        q = q.filter(ShopExpense.category.ilike(f"%{safe_category}%"))

    # Aggregate before pagination. Previously this total ignored date/category filters.
    total = q.with_entities(func.sum(ShopExpense.amount)).scalar() or 0
    count = q.count()
    expenses = q.order_by(ShopExpense.expense_date.desc(), ShopExpense.id.desc()).offset(skip).limit(limit).all()

    return {
        "total_expenses": float(total),
        "total_count": count,
        "skip": skip,
        "limit": limit,
        "expenses": [
            {
                "id": e.id,
                "category": e.category,
                "amount": float(e.amount),
                "description": e.description,
                "expense_date": e.expense_date,
                "payment_method": e.payment_method,
            }
            for e in expenses
        ],
    }


# =====================================
# WORKER MANAGEMENT
# =====================================
class WorkerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=10, pattern=r"^\d{10}$")
    address: Optional[str] = None
    salary: float = Field(0, ge=0)
    assigned_work: Optional[str] = None
    position: Optional[str] = "Staff"
    pin: Optional[str] = None

class WorkerUpdate(BaseModel):
    salary: Optional[float] = None
    assigned_work: Optional[str] = None
    position: Optional[str] = None
    status: Optional[str] = None
    pin: Optional[str] = None

@router.post("/workers", tags=["Worker Management"])
def add_worker(
    data: WorkerCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Add a new worker/staff member"""
    shop_id = current_user["user_id"]  # FIX: owner_only returns dict, not int
    worker = Worker(
        shopkeeper_id=shop_id,
        name=sanitize_input(data.name, "name"),
        phone=data.phone,
        address=data.address,
        salary=data.salary,
        assigned_work=data.assigned_work,
        position=data.position or "Staff",
        pin=data.pin,
    )
    db.add(worker)
    try:
        db.commit()
        db.refresh(worker)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add worker: {str(e)}")
    return {"message": "Worker added successfully.", "worker_id": worker.id, "name": worker.name}


@router.get("/workers", tags=["Worker Management"])
def list_workers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """List all workers for this shop"""
    shop_id = current_user["user_id"]  # FIX: owner_only returns dict, not int
    workers = db.query(Worker).filter(
        Worker.shopkeeper_id == shop_id,
        Worker.status == "active",
    ).all()

    total_monthly_salary = sum(float(w.salary or 0) for w in workers)
    return {
        "total_monthly_salary": total_monthly_salary,
        "workers": [
            {
                "id": w.id,
                "name": w.name,
                "phone": w.phone,
                "position": w.position,
                "salary": float(w.salary or 0),
                "assigned_work": w.assigned_work,
                "status": w.status,
                "join_date": w.join_date,
            }
            for w in workers
        ],
    }


@router.put("/workers/{worker_id}", tags=["Worker Management"])
def update_worker(
    worker_id: int,
    data: WorkerUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Update worker details (salary, position, status)"""
    shop_id = current_user["user_id"]  # FIX: owner_only returns dict, not int
    worker = db.query(Worker).filter(
        Worker.id == worker_id,
        Worker.shopkeeper_id == shop_id,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")

    update_data = data.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(worker, key, value)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update worker: {str(e)}")
    return {"message": "Worker updated.", "worker_id": worker_id}


def _normalize_payroll_month(month: Optional[str]) -> str:
    """Require an exact YYYY-MM payroll period."""
    value = (month or "").strip()
    if not value:
        return date.today().strftime("%Y-%m")
    try:
        parsed = datetime.strptime(value, "%Y-%m")
        if parsed.strftime("%Y-%m") != value:
            raise ValueError("Non-canonical payroll month")
    except ValueError:
        raise HTTPException(status_code=422, detail="month must use the YYYY-MM format.")
    return value


@router.post("/workers/{worker_id}/pay-salary", tags=["Worker Management"])
def pay_worker_salary(
    worker_id: int,
    month: str = Query(None, description="Format: YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Record at most one salary expense per worker and payroll month."""
    month = _normalize_payroll_month(month)
    shop_id = current_user["user_id"]
    # On PostgreSQL, locking the shop-owned worker serializes concurrent retries.
    worker = db.query(Worker).with_for_update().filter(
        Worker.id == worker_id,
        Worker.shopkeeper_id == shop_id,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")

    salary = _expense_money(worker.salary or 0)
    if salary <= 0:
        raise HTTPException(status_code=400, detail="Worker has no salary configured.")

    reference = f"SALARY-W{worker_id}-{month}"
    # Legacy salary writes already share this stable journal reference.
    # Treat retries as success and never insert a second expense/journal row.
    existing_tx = db.query(UniversalTransaction).filter(
        UniversalTransaction.shop_id == shop_id,
        UniversalTransaction.category == "SALARY",
        UniversalTransaction.reference_id == reference,
    ).order_by(UniversalTransaction.id.asc()).first()
    if existing_tx:
        return {
            "message": f"Salary for {worker.name} in {month} was already recorded; no duplicate was created.",
            "amount": float(existing_tx.amount or 0),
            "worker_name": worker.name,
            "month": month,
            "reference_id": reference,
            "already_paid": True,
        }

    expense = ShopExpense(
        shop_id=shop_id,
        category="salary",
        amount=salary,
        description=f"Salary payment for {worker.name} - {month}",
        expense_date=date.today(),
        payment_method="bank_transfer",
        idempotency_key=f"salary-worker-{worker_id}-{month}",
    )
    db.add(expense)

    # Source expense and journal mirror are committed together.
    tx = UniversalTransaction(
        shop_id=shop_id,
        tx_type="EXPENSE",
        category="SALARY",
        amount=salary,
        reference_id=reference,
        description=f"Salary: {worker.name} ({month})",
        tx_date=datetime.combine(date.today(), datetime.min.time()),
    )
    db.add(tx)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_tx = db.query(UniversalTransaction).filter(
            UniversalTransaction.shop_id == shop_id,
            UniversalTransaction.category == "SALARY",
            UniversalTransaction.reference_id == reference,
        ).first()
        if existing_tx:
            return {
                "message": f"Salary for {worker.name} in {month} was already recorded; no duplicate was created.",
                "amount": float(existing_tx.amount or 0),
                "worker_name": worker.name,
                "month": month,
                "reference_id": reference,
                "already_paid": True,
            }
        raise HTTPException(status_code=409, detail="Salary write conflict; refresh the payroll record before retrying.")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to record salary payment.")

    return {
        "message": f"Salary of ₹{salary:.2f} paid to {worker.name} for {month}.",
        "amount": float(salary),
        "worker_name": worker.name,
        "month": month,
        "reference_id": reference,
        "already_paid": False,
    }


# =====================================
# BANK RECONCILIATION
# =====================================
class ReconCreate(BaseModel):
    recon_date: date
    expected_upi_amount: Decimal = Field(Decimal("0"), ge=0)
    actual_bank_deposit: Decimal = Field(Decimal("0"), ge=0)
    notes: Optional[str] = Field(None, max_length=2000)
    # Client must reuse this value for a retry of the same submission.
    idempotency_key: Optional[str] = Field(None, min_length=8, max_length=128)


def _recon_money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _reconciliation_matches(existing: BankReconciliation, data: ReconCreate, normalized_notes: Optional[str]) -> bool:
    """Only acknowledge retries whose immutable reconciliation facts match."""
    try:
        return (
            existing.recon_date == data.recon_date
            and _recon_money(existing.expected_upi_amount) == _recon_money(data.expected_upi_amount)
            and _recon_money(existing.actual_bank_deposit) == _recon_money(data.actual_bank_deposit)
            and (existing.notes or None) == (normalized_notes or None)
        )
    except (ArithmeticError, TypeError, ValueError):
        return False


def _reconciliation_response(record: BankReconciliation, *, duplicate: bool = False) -> dict:
    expected = _recon_money(record.expected_upi_amount)
    actual = _recon_money(record.actual_bank_deposit)
    difference = abs(expected - actual)
    status = getattr(record.status, "value", record.status)
    return {
        "message": "Reconciliation already recorded; canonical record returned." if duplicate else "Reconciliation recorded.",
        "reconciliation_id": record.id,
        "date": record.recon_date.isoformat() if record.recon_date else None,
        "expected_upi_amount": float(expected),
        "actual_bank_deposit": float(actual),
        # Keep old field names for consumers that display the history response.
        "expected_upi": float(expected),
        "actual_bank": float(actual),
        "status": str(status),
        "difference": float(difference),
        "notes": record.notes,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "duplicate": duplicate,
        "alert": (
            f"Discrepancy of ₹{difference:.2f} detected!"
            if str(status) == "DISCREPANCY"
            else "Accounts balanced."
        ),
    }


@router.post("/bank-recon", tags=["Bank Reconciliation"])
def add_reconciliation(
    data: ReconCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Append an auditable UPI-versus-bank comparison; retries are idempotent."""
    shop_id = current_user["user_id"]
    expected = _recon_money(data.expected_upi_amount)
    actual = _recon_money(data.actual_bank_deposit)
    difference = abs(expected - actual)
    status = "MATCHED" if difference < Decimal("1.00") else "DISCREPANCY"
    notes = sanitize_input(data.notes or "", "notes").strip() or None
    idempotency_key = (data.idempotency_key or "").strip() or None
    if idempotency_key is not None and len(idempotency_key) < 8:
        raise HTTPException(status_code=422, detail="idempotency_key must contain at least 8 non-space characters.")

    if idempotency_key:
        existing = db.query(BankReconciliation).filter(
            BankReconciliation.shop_id == shop_id,
            BankReconciliation.idempotency_key == idempotency_key,
        ).first()
        if existing:
            if _reconciliation_matches(existing, data, notes):
                return _reconciliation_response(existing, duplicate=True)
            raise HTTPException(
                status_code=409,
                detail="Reconciliation idempotency key was reused with different financial details.",
            )

    record = BankReconciliation(
        shop_id=shop_id,
        recon_date=data.recon_date,
        expected_upi_amount=expected,
        actual_bank_deposit=actual,
        status=status,
        notes=notes,
        idempotency_key=idempotency_key,
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(BankReconciliation).filter(
                BankReconciliation.shop_id == shop_id,
                BankReconciliation.idempotency_key == idempotency_key,
            ).first()
            if existing and _reconciliation_matches(existing, data, notes):
                return _reconciliation_response(existing, duplicate=True)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Reconciliation idempotency key was reused with different financial details.",
                )
        raise HTTPException(status_code=409, detail="Reconciliation write conflict; refresh history before retrying.")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to record reconciliation.")

    return _reconciliation_response(record)


@router.get("/bank-recon", tags=["Bank Reconciliation"])
def list_reconciliations(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """View append-only shop-scoped reconciliation history."""
    shop_id = current_user["user_id"]
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")

    q = db.query(BankReconciliation).filter(BankReconciliation.shop_id == shop_id)
    if start_date:
        q = q.filter(BankReconciliation.recon_date >= start_date)
    if end_date:
        q = q.filter(BankReconciliation.recon_date <= end_date)
    records = q.order_by(
        BankReconciliation.recon_date.desc(),
        BankReconciliation.created_at.desc(),
        BankReconciliation.id.desc(),
    ).all()

    return {
        "records": [
            {
                "id": record.id,
                "reconciliation_id": record.id,
                "date": record.recon_date.isoformat(),
                "expected_upi": float(_recon_money(record.expected_upi_amount)),
                "expected_upi_amount": float(_recon_money(record.expected_upi_amount)),
                "actual_bank": float(_recon_money(record.actual_bank_deposit)),
                "actual_bank_deposit": float(_recon_money(record.actual_bank_deposit)),
                "status": str(getattr(record.status, "value", record.status)),
                "difference": float(abs(_recon_money(record.expected_upi_amount) - _recon_money(record.actual_bank_deposit))),
                "notes": record.notes,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
            for record in records
        ]
    }


# =====================================
# ENTERPRISE TRACKER (Unified P&L)
# =====================================
@router.get("/enterprise/pnl", tags=["Enterprise Intelligence"])
def get_profit_and_loss(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """
    Full Profit & Loss summary:
    Revenue (sales) - Expenses (all categories) = Net Profit
    """
    shop_id = current_user["user_id"]  # FIX: owner_only returns dict, not int
    if not start_date:
        start_date = date.today().replace(day=1)  # Current month
    if not end_date:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # Total income from universal journal
    income = db.query(func.sum(UniversalTransaction.amount)).filter(
        UniversalTransaction.shop_id == shop_id,
        UniversalTransaction.tx_type == "INCOME",
        UniversalTransaction.tx_date >= start_dt,
        UniversalTransaction.tx_date <= end_dt,
    ).scalar() or 0

    # Total expenses
    expenses = db.query(func.sum(UniversalTransaction.amount)).filter(
        UniversalTransaction.shop_id == shop_id,
        UniversalTransaction.tx_type == "EXPENSE",
        UniversalTransaction.tx_date >= start_dt,
        UniversalTransaction.tx_date <= end_dt,
    ).scalar() or 0

    # Breakdown by category
    breakdown = db.query(
        UniversalTransaction.category,
        UniversalTransaction.tx_type,
        func.sum(UniversalTransaction.amount).label("total"),
        func.count(UniversalTransaction.id).label("count"),
    ).filter(
        UniversalTransaction.shop_id == shop_id,
        UniversalTransaction.tx_date >= start_dt,
        UniversalTransaction.tx_date <= end_dt,
    ).group_by(UniversalTransaction.category, UniversalTransaction.tx_type).all()

    net_profit = float(income) - float(expenses)

    return {
        "period": {"start": str(start_date), "end": str(end_date)},
        "total_income": float(income),
        "total_expenses": float(expenses),
        "net_profit": net_profit,
        "profit_margin_pct": round((net_profit / float(income) * 100) if income else 0, 2),
        "status": "PROFIT" if net_profit >= 0 else "LOSS",
        "breakdown": [
            {
                "category": b.category,
                "type": b.tx_type,
                "total": float(b.total),
                "transactions": b.count,
            }
            for b in breakdown
        ],
    }


@router.get("/enterprise/transactions", tags=["Enterprise Intelligence"])
def get_all_transactions(
    tx_type: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """All Transactions view: every money movement (sales, expenses, khata, PO)"""
    shop_id = current_user["user_id"]  # FIX: owner_only returns dict, not int
    q = db.query(UniversalTransaction).filter(UniversalTransaction.shop_id == shop_id)
    if tx_type:
        q = q.filter(UniversalTransaction.tx_type == tx_type.upper())
    if category:
        q = q.filter(UniversalTransaction.category.ilike(f"%{category}%"))
    if start_date:
        q = q.filter(UniversalTransaction.tx_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        q = q.filter(UniversalTransaction.tx_date <= datetime.combine(end_date, datetime.max.time()))

    txs = q.order_by(UniversalTransaction.tx_date.desc()).offset(skip).limit(limit).all()
    return {
        "transactions": [
            {
                "id": t.id,
                "type": t.tx_type,
                "category": t.category,
                "amount": float(t.amount),
                "reference_id": t.reference_id,
                "description": t.description,
                "date": t.tx_date,
            }
            for t in txs
        ]
    }


# =====================================
# RETAIL INTELLIGENCE
# =====================================
@router.get("/retail/stock-analysis", tags=["Retail Intelligence"])
def stock_analysis(
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """Identify fast-moving and dead-stock items"""
    shop_id = current_user["user_id"]  # FIX: owner_only returns dict, not int

    products = db.query(Product).filter(
        Product.user_id == shop_id,
        Product.is_active == True,
    ).all()

    fast_movers = []
    dead_stock = []
    low_stock = []

    for p in products:
        if p.current_stock <= 0:
            dead_stock.append({"id": p.id, "name": p.product_name, "stock": 0, "category": p.category})
        elif p.current_stock <= (p.min_stock or 10):
            low_stock.append({
                "id": p.id,
                "name": p.product_name,
                "stock": p.current_stock,
                "min_stock": p.min_stock,
                "category": p.category,
            })

    # Top selling products (from sales table)
    top_sales = (
        db.query(sales.product_name, func.sum(sales.quantity).label("total_qty"))
        .filter(sales.shopkeeper_id == shop_id)
        .group_by(sales.product_name)
        .order_by(func.sum(sales.quantity).desc())
        .limit(10)
        .all()
    )

    return {
        "fast_moving_products": [{"name": r.product_name, "total_sold": int(r.total_qty)} for r in top_sales],
        "low_stock_alerts": low_stock,
        "out_of_stock": dead_stock,
        "summary": {
            "total_products": len(products),
            "low_stock_count": len(low_stock),
            "out_of_stock_count": len(dead_stock),
        },
    }

# =====================================
# WHATSAPP SMART REMARKETING
# =====================================
class RemarketingOpportunity(BaseModel):
    customer_id: int
    name: str
    phone: str
    favorite_item: str
    days_since_last_purchase: int
    suggested_message: str

@router.get("/remarketing", response_model=List[RemarketingOpportunity], tags=["Smart Remarketing"])
def get_remarketing_opportunities(
    threshold_days: int = Query(30, description="Number of days of inactivity to trigger remarketing"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(owner_only),
):
    """
    Find customers who haven't purchased in `threshold_days`,
    determine their favorite item, and generate a WhatsApp message.
    """
    shop_id = current_user["user_id"]  # FIX: owner_only returns dict, not int
    threshold_date = datetime.now(timezone.utc) - timedelta(days=threshold_days)
    
    # 1. Get all customers for this shop (Customer uses user_id, not shop_id)
    customers = db.query(Customer).filter(Customer.user_id == shop_id).all()
    
    opportunities = []
    
    for customer in customers:
        if not customer.phone:
            continue
            
        # Get latest invoice
        latest_invoice = db.query(Invoice).filter(
            Invoice.user_id == shop_id,  # FIX: Invoice uses user_id not shop_id
            Invoice.customer_id == customer.id
        ).order_by(Invoice.created_at.desc()).first()
        
        # If no invoice or they bought recently, skip
        if not latest_invoice:
            continue
            
        # Ensure latest_invoice.created_at is aware or compare naively
        invoice_date = latest_invoice.created_at
        if invoice_date.tzinfo is None:
            invoice_date = invoice_date.replace(tzinfo=timezone.utc)
            
        days_since = (datetime.now(timezone.utc) - invoice_date).days
        if days_since < threshold_days:
            continue
            
        # 2. Find favorite item
        # Get all invoices for this customer
        invoices = db.query(Invoice).filter(
            Invoice.user_id == shop_id,  # FIX: Invoice uses user_id not shop_id
            Invoice.customer_id == customer.id
        ).all()
        invoice_ids = [inv.id for inv in invoices]
        
        if not invoice_ids:
            continue
            
        # Get all line items for these invoices
        line_items = db.query(InvoiceLineItem).filter(
            InvoiceLineItem.invoice_id.in_(invoice_ids)
        ).all()
        
        if not line_items:
            continue
            
        # Tally item frequency (InvoiceLineItem uses 'description', not 'product_name')
        item_counts = {}
        for item in line_items:
            item_desc = item.description or "Unknown Product"
            item_counts[item_desc] = item_counts.get(item_desc, 0) + 1
            
        # Get item with max frequency
        favorite_item = max(item_counts, key=item_counts.get)
        
        name = customer.customer_name or "Customer"  # FIX: Customer model uses customer_name not name
        msg = f"Hi {name}! You usually buy {favorite_item} from us, but we haven't seen you in a while. Reply to this message to order now and get a 5% discount on your next purchase!"
        
        opportunities.append(RemarketingOpportunity(
            customer_id=customer.id,
            name=name,
            phone=customer.phone,
            favorite_item=favorite_item,
            days_since_last_purchase=days_since,
            suggested_message=msg
        ))
        
    # Sort by days_since descending (most dormant first)
    opportunities.sort(key=lambda x: x.days_since_last_purchase, reverse=True)
    return opportunities
