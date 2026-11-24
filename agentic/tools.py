"""Tenant-scoped, allowlisted Retail Mind agent tools.

Tools use the authenticated owner ID supplied by the API layer. The model never
supplies a shop/user ID and has no database, SQL, filesystem, shell, or HTTP tool.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models import (
    AgentPendingAction,
    AgentToolExecution,
    Attendance,
    Customer,
    FlashSale,
    Invoice,
    PaymentStatus,
    OnlineOrder,
    Payment,
    Product,
    Worker,
    InvoiceStatus,
)

IST = ZoneInfo("Asia/Kolkata")
MAX_TOOL_CALLS_PER_TURN = 5
MAX_DATE_RANGE_DAYS = 180


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InventorySearchArgs(ToolArgs):
    query: str = Field(default="", max_length=100)


class CustomerSearchArgs(ToolArgs):
    query: str = Field(min_length=2, max_length=100)


class SalesSummaryArgs(ToolArgs):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class AttendanceSummaryArgs(ToolArgs):
    attendance_date: Optional[date] = None


class OrderSummaryArgs(ToolArgs):
    status: Optional[str] = Field(default=None, max_length=24)


class KhataPaymentPreviewArgs(ToolArgs):
    invoice_id: int = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0, le=Decimal("100000000"))
    payment_method: Literal["CASH", "UPI", "CARD", "TRANSFER"] = "CASH"


class OrderTransitionPreviewArgs(ToolArgs):
    order_id: int = Field(..., gt=0)
    action: Literal["ACCEPT", "DISPATCH", "REJECT"]


class KhataLedgerMovementArgs(ToolArgs):
    operation: Literal["CREDIT", "REPAYMENT"]
    customer_phone: str = Field(..., pattern=r"^[6-9]\d{9}$")
    amount: Decimal = Field(..., gt=0, le=Decimal("100000000"))
    customer_name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=180)


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_inventory",
            "description": "Search active products and stock in the authenticated shop. An empty query returns low-stock products.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "maxLength": 100}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_customers",
            "description": "Find active CRM customers by name or Indian mobile number in the authenticated shop.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 100}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": "Summarize billed amount, received amount, outstanding balance and invoice count for an inclusive date range. Defaults to the last 7 days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "format": "date"},
                    "end_date": {"type": "string", "format": "date"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attendance_summary",
            "description": "Summarize employee attendance for one date in the authenticated shop. Defaults to today in India Standard Time.",
            "parameters": {
                "type": "object",
                "properties": {"attendance_date": {"type": "string", "format": "date"}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_khata_summary",
            "description": "Read outstanding Khata balances for the authenticated shop. This tool does not add credit or record repayments.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_online_order_summary",
            "description": "Read counts and recent order statuses for the authenticated shop. This tool does not accept, reject, dispatch or cancel orders.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string", "maxLength": 24}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_bill_from_current_message",
            "description": "Prepare a draft bill from the user's exact current message using Retail Mind's existing voice-billing parser and the authenticated shop catalog. It never creates an invoice or deducts stock. It takes no arguments.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_invoice_payment",
            "description": "Prepare an owner-confirmed payment entry for one specific unpaid/part-paid invoice. It never records the payment until the owner confirms the exact preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "integer", "minimum": 1},
                    "amount": {"type": "number", "exclusiveMinimum": 0, "maximum": 100000000},
                    "payment_method": {"type": "string", "enum": ["CASH", "UPI", "CARD", "TRANSFER"]},
                },
                "required": ["invoice_id", "amount"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_online_order_transition",
            "description": "Prepare an owner-confirmed preview to ACCEPT, DISPATCH or REJECT one online order. DELIVERY is excluded because it requires the customer's OTP; cancellation/refunds are not enabled.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "minimum": 1},
                    "action": {"type": "string", "enum": ["ACCEPT", "DISPATCH", "REJECT"]},
                },
                "required": ["order_id", "action"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_khata_ledger_movement",
            "description": "Prepare a preview to add customer Khata credit or record a repayment in the legacy Khata ledger. Requires exact 10-digit customer phone and amount. Never writes until owner confirms in Retail Mind.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["CREDIT", "REPAYMENT"]},
                    "customer_phone": {"type": "string", "pattern": "^[6-9]\\d{9}$"},
                    "amount": {"type": "number", "exclusiveMinimum": 0, "maximum": 100000000},
                    "customer_name": {"type": "string", "maxLength": 100},
                    "description": {"type": "string", "maxLength": 180}
                },
                "required": ["operation", "customer_phone", "amount"],
                "additionalProperties": False
            }
        }
    },
]


def _money(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid monetary value") from exc
    if not result.is_finite():
        raise ValueError("Invalid monetary value")
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _record_tool_execution(
    db: Session,
    *,
    shop_id: int,
    conversation_id: Optional[str],
    request_id: str,
    tool_name: str,
    started_at: float,
    success: bool,
    error_code: Optional[str] = None,
) -> None:
    """Persist metadata only; do not log user text, arguments, phone or tool output."""
    db.add(
        AgentToolExecution(
            user_id=shop_id,
            conversation_id=conversation_id,
            request_id=request_id,
            tool_name=tool_name[:80],
            success=bool(success),
            error_code=(error_code or None),
            duration_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
        )
    )


def _inventory_search(db: Session, shop_id: int, args: InventorySearchArgs) -> dict:
    query = db.query(Product).filter(
        Product.user_id == shop_id,
        Product.is_active.is_(True),
    )
    term = args.query.strip()
    if term:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.filter(
            or_(
                Product.product_name.ilike(pattern, escape="\\"),
                Product.sku.ilike(pattern, escape="\\"),
                Product.category.ilike(pattern, escape="\\"),
            )
        )
    else:
        query = query.filter(Product.current_stock <= Product.min_stock)
    rows = query.order_by(Product.product_name.asc()).limit(10).all()
    return {
        "count": len(rows),
        "products": [
            {
                "product_id": int(row.id),
                "name": str(row.product_name or ""),
                "sku": str(row.sku or ""),
                "category": str(row.category or ""),
                "stock": float(row.current_stock or 0),
                "unit": str(row.unit or "pcs"),
                "unit_price": float(row.unit_price or 0),
                "low_stock": float(row.current_stock or 0) <= float(row.min_stock or 0),
            }
            for row in rows
        ],
    }


def _customer_search(db: Session, shop_id: int, args: CustomerSearchArgs) -> dict:
    term = args.query.strip()
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    rows = (
        db.query(Customer)
        .filter(
            Customer.user_id == shop_id,
            Customer.is_active.is_(True),
            or_(
                Customer.customer_name.ilike(pattern, escape="\\"),
                Customer.phone.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(Customer.customer_name.asc())
        .limit(10)
        .all()
    )
    return {
        "count": len(rows),
        "customers": [
            {
                "customer_id": int(row.id),
                "name": str(row.customer_name or ""),
                "phone_last4": str(row.phone or "")[-4:],
            }
            for row in rows
        ],
    }


def _sales_summary(db: Session, shop_id: int, args: SalesSummaryArgs) -> dict:
    today = datetime.now(IST).date()
    end_day = args.end_date or today
    start_day = args.start_date or (end_day - timedelta(days=6))
    if end_day < start_day:
        raise ValueError("end_date must be on or after start_date")
    if (end_day - start_day).days > MAX_DATE_RANGE_DAYS:
        raise ValueError("Choose a date range of 180 days or less")
    row = (
        db.query(
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.total_amount), 0),
            func.coalesce(func.sum(Invoice.paid_amount), 0),
        )
        .filter(
            Invoice.user_id == shop_id,
            Invoice.invoice_date >= start_day,
            Invoice.invoice_date <= end_day,
            Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]),
        )
        .one()
    )
    invoice_count = int(row[0] or 0)
    billed = _money(row[1] or 0)
    received = _money(row[2] or 0)
    return {
        "period": {"start": start_day.isoformat(), "end": end_day.isoformat()},
        "invoice_count": invoice_count,
        "billed_amount": float(billed),
        "received_amount": float(received),
        "outstanding_amount": float(max(Decimal("0"), billed - received)),
        "definition": "Billed amount uses qualifying invoices; received amount is their paid_amount. Cancelled and draft invoices are excluded.",
    }


def _attendance_summary(db: Session, shop_id: int, args: AttendanceSummaryArgs) -> dict:
    target_date = args.attendance_date or datetime.now(IST).date()
    rows = (
        db.query(Attendance, Worker)
        .outerjoin(Worker, Attendance.worker_id == Worker.id)
        .filter(
            Attendance.employee_id == shop_id,
            Attendance.attendance_date == target_date,
            or_(Attendance.worker_id.is_(None), Worker.shopkeeper_id == shop_id),
        )
        .order_by(Attendance.id.asc())
        .limit(250)
        .all()
    )
    records = []
    for attendance, worker in rows:
        records.append(
            {
                "worker_id": int(worker.id) if worker else None,
                "name": str(worker.name if worker else "Owner"),
                "status": str(getattr(attendance.status, "value", attendance.status) or ""),
                "check_in": attendance.check_in_time.isoformat() if attendance.check_in_time else None,
                "check_out": attendance.check_out_time.isoformat() if attendance.check_out_time else None,
                "working_hours": float(attendance.working_hours or 0),
            }
        )
    counts: dict[str, int] = {}
    for item in records:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"date": target_date.isoformat(), "record_count": len(records), "status_counts": counts, "records": records}


def _khata_summary(db: Session, shop_id: int) -> dict:
    """Read pending receivables from the invoice-based /api/khata engine.

    The legacy KhataBalance ledger is a separate data store; it must not be
    blended into the newer invoice-derived pending-payments view.
    """
    today = datetime.now(IST).date()
    week_end = today + timedelta(days=7)
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.user_id == shop_id,
            Invoice.payment_status.in_([
                PaymentStatus.UNPAID,
                PaymentStatus.PARTIAL,
                PaymentStatus.OVERDUE,
            ]),
            Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]),
        )
        .order_by(Invoice.due_date.asc().nullslast(), Invoice.invoice_date.asc())
        .limit(500)
        .all()
    )
    total_outstanding = Decimal("0.00")
    total_overdue = Decimal("0.00")
    due_this_week = Decimal("0.00")
    customers: dict[str, dict[str, Any]] = {}

    for invoice in invoices:
        balance = max(
            Decimal("0.00"),
            _money(invoice.total_amount or 0) - _money(invoice.paid_amount or 0),
        )
        if balance <= Decimal("0.01"):
            continue
        total_outstanding += balance
        due_date = invoice.due_date
        if isinstance(due_date, str):
            try:
                due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
            except ValueError:
                due_date = None
        if due_date and due_date < today:
            total_overdue += balance
        elif due_date and today <= due_date <= week_end:
            due_this_week += balance

        phone = str(invoice.customer_phone or "").strip()
        name = " ".join(str(invoice.customer_name or "Walk-in Customer").split())[:100]
        key = phone or (f"id:{invoice.customer_id}" if invoice.customer_id else f"name:{name.casefold()}")
        customer = customers.setdefault(
            key,
            {"name": name, "phone_last4": phone[-4:] if phone else "", "outstanding": Decimal("0.00")},
        )
        customer["outstanding"] += balance

    top_customers = sorted(
        customers.values(),
        key=lambda customer: customer["outstanding"],
        reverse=True,
    )[:10]
    return {
        "period_as_of": today.isoformat(),
        "total_outstanding": float(_money(total_outstanding)),
        "total_overdue": float(_money(total_overdue)),
        "due_this_week": float(_money(due_this_week)),
        "pending_customers_count": len(customers),
        "top_customers": [
            {
                "name": row["name"],
                "phone_last4": row["phone_last4"],
                "outstanding": float(_money(row["outstanding"])),
            }
            for row in top_customers
        ],
        "source": "invoice_based_pending_payment_engine",
        "note": "Read-only receivables summary. No credit or repayment was recorded.",
    }


def _order_summary(db: Session, shop_id: int, args: OrderSummaryArgs) -> dict:
    query = db.query(OnlineOrder).filter(OnlineOrder.shop_id == shop_id)
    if args.status:
        query = query.filter(OnlineOrder.order_status == args.status.strip().upper())
    recent = query.order_by(OnlineOrder.created_at.desc()).limit(10).all()
    grouped = (
        db.query(OnlineOrder.order_status, func.count(OnlineOrder.id))
        .filter(OnlineOrder.shop_id == shop_id)
        .group_by(OnlineOrder.order_status)
        .all()
    )
    return {
        "status_counts": {str(row[0] or "UNKNOWN"): int(row[1] or 0) for row in grouped},
        "recent_orders": [
            {
                "order_id": int(row.id),
                "status": str(row.order_status or ""),
                "payment_status": str(row.payment_status or ""),
                "total_amount": float(row.total_amount or 0),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in recent
        ],
        "note": "Read-only. No order state was changed.",
    }


async def _prepare_bill(db: Session, context: dict) -> dict:
    """Use the existing parser; produce only a persisted, expiring preview."""
    user_text = str(context.get("user_text") or "").strip()
    if not user_text:
        return {"success": False, "needs_clarification": True, "message": "Please describe the items for the bill."}

    phone_match = re.search(r"(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{9})(?!\d)", user_text)
    customer_phone = phone_match.group(1) if phone_match else None
    parser_text = user_text
    if phone_match:
        parser_text = user_text[: phone_match.start()] + " " + user_text[phone_match.end() :]

    from inventory import VoiceBillingParseRequest, parse_voice_billing

    parsed = await parse_voice_billing(
        VoiceBillingParseRequest(
            transcript=parser_text[:1200],
            language_code=str(context.get("language_code") or "auto")[:16],
        ),
        user_id=int(context["shop_id"]),
        db=db,
    )
    if not isinstance(parsed, dict) or not parsed.get("success") or not parsed.get("items"):
        return {
            "success": False,
            "needs_clarification": True,
            "message": (parsed or {}).get("clarification_question") or "I could not identify bill items. Please say the product, quantity and price again.",
            "parser": parsed,
        }

    if parsed.get("needs_clarification"):
        return {
            "success": False,
            "needs_clarification": True,
            "message": parsed.get("clarification_question") or "Please clarify the highlighted bill details before I prepare a preview.",
            "parser": parsed,
        }

    shop_id = int(context["shop_id"])
    db_products: dict[int, Product] = {}
    output_lines = []
    total = Decimal("0.00")
    flash_sale = (
        db.query(FlashSale)
        .filter(
            FlashSale.user_id == shop_id,
            FlashSale.is_active.is_(True),
            FlashSale.end_time > datetime.utcnow(),
        )
        .order_by(FlashSale.start_time.desc())
        .first()
    )

    for item in parsed["items"][:30]:
        if item.get("needs_confirmation") or item.get("price_missing") or item.get("price_needs_confirmation"):
            return {
                "success": False,
                "needs_clarification": True,
                "message": item.get("price_warning") or f"Please confirm the quantity and price for {item.get('product_name') or 'this item'}.",
                "parser": parsed,
            }
        try:
            quantity = Decimal(str(item.get("quantity")))
            unit_price = _money(item.get("unit_price"))
        except (InvalidOperation, TypeError, ValueError):
            quantity = Decimal("0")
            unit_price = Decimal("0")
        if not quantity.is_finite() or quantity <= 0 or quantity > Decimal("100000"):
            return {"success": False, "needs_clarification": True, "message": f"Please confirm the quantity for {item.get('product_name') or 'this item'}."}
        if unit_price <= 0 or unit_price > Decimal("10000000"):
            return {"success": False, "needs_clarification": True, "message": f"Please enter a valid selling price for {item.get('product_name') or 'this item'}."}

        product_id = item.get("product_id")
        product = None
        if product_id is not None:
            try:
                product = db.query(Product).filter(
                    Product.id == int(product_id),
                    Product.user_id == shop_id,
                    Product.is_active.is_(True),
                ).first()
            except (TypeError, ValueError):
                product = None
            if product is None:
                return {"success": False, "needs_clarification": True, "message": "A catalog match could not be verified. Please select the product again."}
            db_products[int(product.id)] = product
            if Decimal(str(product.current_stock or 0)) < quantity:
                return {
                    "success": False,
                    "needs_clarification": True,
                    "message": f"Insufficient stock for {product.product_name}. Available {product.current_stock} {product.unit}; requested {quantity}. Adjust the quantity or update stock first.",
                }
        else:
            # The invoice route re-resolves by exact product name when product_id is
            # absent. Reject a name that exactly matches a catalog item to avoid a
            # surprise stock deduction after the preview.
            duplicate = db.query(Product.id).filter(
                Product.user_id == shop_id,
                Product.is_active.is_(True),
                func.lower(Product.product_name) == str(item.get("product_name") or "").strip().lower(),
            ).first()
            if duplicate:
                return {
                    "success": False,
                    "needs_clarification": True,
                    "message": "A product with that exact name exists in your catalog but was not confidently matched. Please select the catalog item first.",
                }

        base_line = quantity * unit_price
        discount = Decimal("0.00")
        discount_reason = None
        discount_source = None
        if flash_sale and product:
            sale_category = str(flash_sale.category or "").strip().lower()
            product_category = str(product.category or "").strip().lower()
            applies = sale_category in {"all", "*", "all products"} or bool(sale_category and sale_category == product_category)
            if applies:
                discount = (base_line * Decimal(str(flash_sale.discount_pct or 0)) / Decimal("100")).quantize(Decimal("0.01"))
                discount = min(base_line, max(Decimal("0"), discount))
                if discount > 0:
                    discount_reason = f"Flash Sale {float(flash_sale.discount_pct):g}%"
                    discount_source = "flash_sale"

        line_total = max(Decimal("0"), base_line - discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += line_total
        output_lines.append(
            {
                "product_id": int(product.id) if product else None,
                "product_name": str(item.get("product_name") or "").strip()[:255],
                "quantity": str(quantity.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)),
                "unit_price": str(unit_price),
                "discount_amount": str(discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                "discount_reason": discount_reason,
                "discount_source": discount_source,
                "line_total": float(line_total),
                "stock_before": float(product.current_stock) if product else None,
                "stock_after_preview": float(Decimal(str(product.current_stock)) - quantity) if product else None,
            }
        )

    total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if total <= 0:
        return {"success": False, "needs_clarification": True, "message": "The bill total must be greater than zero."}

    customer = None
    if customer_phone:
        customer = db.query(Customer).filter(
            Customer.user_id == shop_id,
            Customer.phone == customer_phone,
            Customer.is_active.is_(True),
        ).first()

    action_id = str(uuid.uuid4())
    conversation_id = str(context["conversation_id"])
    idempotency_key = hashlib.sha256(
        f"{shop_id}:{conversation_id}:{user_text}".encode("utf-8")
    ).hexdigest()
    prior = db.query(AgentPendingAction).filter(
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.idempotency_key == idempotency_key,
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
                "message": "I found the existing action for this repeated message; no new bill preview was created.",
            }
        return {"success": False, "needs_clarification": True, "message": "This exact request already expired or failed. Send it again as a new message to prepare a fresh bill."}

    invoice_number = f"AIM-{datetime.now(IST):%Y%m%d}-{action_id.replace('-', '')[:10].upper()}"
    customer_name = customer.customer_name if customer else ("Cash Customer" if not customer_phone else "Customer")
    preview = {
        "invoice_number": invoice_number,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "currency": "INR",
        "subtotal": float(total),
        "tax": 0.0,
        "total_amount": float(total),
        "paid_amount": 0.0,
        "payment_status": "UNPAID",
        "items": [
            {
                "product_id": row["product_id"],
                "product_name": row["product_name"],
                "quantity": float(row["quantity"]),
                "unit_price": float(row["unit_price"]),
                "discount_amount": float(row["discount_amount"]),
                "line_total": row["line_total"],
                "stock_after_preview": row["stock_after_preview"],
            }
            for row in output_lines
        ],
        "requires_owner_confirmation": True,
        "expires_in_seconds": 300,
    }
    payload = {
        "invoice_number": invoice_number,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "total_amount": str(total),
        "tax": "0.00",
        "paid_amount": "0.00",
        "invoice_date": datetime.now(IST).date().isoformat(),
        "due_date": datetime.now(IST).date().isoformat(),
        "notes": f"Created via Retail Mind AI assistant. Action {action_id}",
        "line_items": output_lines,
    }
    preview_hash = hashlib.sha256(
        _json_dump({"action_id": action_id, "shop_id": shop_id, "preview": preview, "payload": payload}).encode("utf-8")
    ).hexdigest()

    action = AgentPendingAction(
        id=action_id,
        user_id=shop_id,
        conversation_id=conversation_id,
        action_type="CREATE_INVOICE",
        status="PENDING",
        idempotency_key=idempotency_key,
        preview=preview,
        payload=payload,
        preview_hash=preview_hash,
        invoice_number=invoice_number,
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add(action)
    db.flush()
    return {
        "success": True,
        "action_id": action_id,
        "status": "PENDING",
        "preview_hash": preview_hash,
        "preview": preview,
        "message": "Bill draft prepared. No invoice has been created and no stock has changed. Ask the owner to review and explicitly confirm this exact preview.",
    }


def _prepare_khata_payment(db: Session, shop_id: int, conversation_id: str, request_text: str, args: KhataPaymentPreviewArgs) -> dict:
    payment_method = (args.payment_method or "CASH").strip().upper()
    if payment_method not in {"CASH", "UPI", "CARD", "TRANSFER"}:
        raise ValueError("Unsupported payment method")
    invoice = db.query(Invoice).filter(
        Invoice.id == args.invoice_id,
        Invoice.user_id == shop_id,
        Invoice.status.notin_([InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT]),
    ).with_for_update().first()
    if invoice is None:
        raise ValueError("Invoice not found in this shop")
    outstanding = max(Decimal("0.00"), _money(invoice.total_amount or 0) - _money(invoice.paid_amount or 0))
    amount = _money(args.amount)
    if outstanding <= Decimal("0.01"):
        raise ValueError("This invoice has no outstanding balance")
    if amount > outstanding:
        raise ValueError(f"Payment cannot exceed the invoice balance of ₹{outstanding:.2f}")

    idempotency_key = hashlib.sha256(
        f"{shop_id}:{conversation_id}:KHATA_PAYMENT:{request_text}:{invoice.id}:{amount}:{payment_method}".encode()
    ).hexdigest()
    prior = db.query(AgentPendingAction).filter(
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.idempotency_key == idempotency_key,
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
                "message": "This payment request already has a confirmation action. No second preview was created.",
            }
        return {"success": False, "needs_clarification": True, "message": "This payment request already expired or failed. Start a new request."}

    action_id = str(uuid.uuid4())
    preview = {
        "operation": "RECORD_INVOICE_PAYMENT",
        "invoice_id": int(invoice.id),
        "invoice_number": str(invoice.invoice_number),
        "customer_name": str(invoice.customer_name or "Customer"),
        "customer_phone_last4": str(invoice.customer_phone or "")[-4:],
        "outstanding_before": float(outstanding),
        "payment_amount": float(amount),
        "payment_method": payment_method,
        "currency": "INR",
        "requires_owner_confirmation": True,
        "expires_in_seconds": 300,
        "warning": "This records a payment entry; it does not independently verify a bank transfer or cash receipt.",
    }
    payload = {
        "invoice_id": int(invoice.id),
        "invoice_number": str(invoice.invoice_number),
        "amount": str(amount),
        "payment_method": payment_method,
        "idempotency_key": f"agent-khata-{action_id}",
        "notes": "Owner-confirmed payment recorded via Retail Mind assistant",
    }
    preview_hash = hashlib.sha256(
        _json_dump({"action_id": action_id, "shop_id": shop_id, "preview": preview, "payload": payload}).encode()
    ).hexdigest()
    db.add(AgentPendingAction(
        id=action_id,
        user_id=shop_id,
        conversation_id=conversation_id,
        action_type="KHATA_PAYMENT",
        status="PENDING",
        idempotency_key=idempotency_key,
        preview=preview,
        payload=payload,
        preview_hash=preview_hash,
        invoice_number=str(invoice.invoice_number),
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    ))
    db.flush()
    return {
        "success": True,
        "action_id": action_id,
        "status": "PENDING",
        "preview_hash": preview_hash,
        "preview": preview,
        "message": "Payment preview prepared. No payment has been recorded. Review and confirm this exact payment.",
    }


def _prepare_order_transition(db: Session, shop_id: int, conversation_id: str, args: OrderTransitionPreviewArgs) -> dict:
    action = args.action.strip().upper()
    expected = {"ACCEPT": ("PENDING", "ACCEPTED"), "DISPATCH": ("ACCEPTED", "DISPATCHED"), "REJECT": ({"PENDING", "ACCEPTED"}, "REJECTED")}
    if action not in expected:
        raise ValueError("Only ACCEPT, DISPATCH and REJECT can be prepared")
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == args.order_id,
        OnlineOrder.shop_id == shop_id,
    ).with_for_update().first()
    if order is None:
        raise ValueError("Online order not found in this shop")
    current_status = str(getattr(order.order_status, "value", order.order_status) or "").upper()
    allowed_previous, target_status = expected[action]
    allowed = {allowed_previous} if isinstance(allowed_previous, str) else allowed_previous
    if current_status not in allowed:
        raise ValueError(f"Cannot {action.lower()} an order currently in {current_status}")

    idempotency_key = hashlib.sha256(
        f"{shop_id}:{conversation_id}:ORDER:{order.id}:{action}".encode()
    ).hexdigest()
    prior = db.query(AgentPendingAction).filter(
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.idempotency_key == idempotency_key,
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
                "message": "This order transition already has a confirmation action. No second preview was created.",
            }
        return {"success": False, "needs_clarification": True, "message": "This order transition already expired or failed. Start a new request."}

    try:
        items = json.loads(order.items_json or "[]")
        if not isinstance(items, list):
            items = []
    except (TypeError, ValueError):
        items = []
    preview_items = [
        {
            "product_name": str(item.get("product_name") or "Item")[:120],
            "quantity": float(item.get("quantity") or 0),
            "line_total": float(item.get("line_total") or 0),
        }
        for item in items[:30] if isinstance(item, dict)
    ]
    action_id = str(uuid.uuid4())
    preview = {
        "operation": f"ONLINE_ORDER_{action}",
        "order_id": int(order.id),
        "current_status": current_status,
        "resulting_status": target_status,
        "payment_method": str(order.payment_method or "COD"),
        "payment_status": str(order.payment_status or "COD_DUE"),
        "total_amount": float(order.total_amount or 0),
        "currency": "INR",
        "items": preview_items,
        "requires_owner_confirmation": True,
        "expires_in_seconds": 300,
        "warning": (
            "REJECT reverses the accepted order's provisional invoice and restores reserved stock."
            if action == "REJECT" else
            "ACCEPT creates a provisional invoice/reservation; the sale is settled only at delivery."
            if action == "ACCEPT" else
            "DISPATCH changes fulfilment state only. Delivery still requires the customer's OTP."
        ),
    }
    payload = {
        "order_id": int(order.id),
        "action": action,
        "expected_current_status": current_status,
        "expected_status": target_status,
    }
    preview_hash = hashlib.sha256(
        _json_dump({"action_id": action_id, "shop_id": shop_id, "preview": preview, "payload": payload}).encode()
    ).hexdigest()
    db.add(AgentPendingAction(
        id=action_id,
        user_id=shop_id,
        conversation_id=conversation_id,
        action_type="ORDER_TRANSITION",
        status="PENDING",
        idempotency_key=idempotency_key,
        preview=preview,
        payload=payload,
        preview_hash=preview_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    ))
    db.flush()
    return {
        "success": True,
        "action_id": action_id,
        "status": "PENDING",
        "preview_hash": preview_hash,
        "preview": preview,
        "message": "Order transition preview prepared. The order has not been changed. Review and confirm this exact action.",
    }


async def dispatch_tool(tool_name: str, raw_arguments: str, context: dict) -> dict:
    """Validate and execute an allowlisted tool; audit commit must succeed before success is returned."""
    db: Session = context["db"]
    shop_id = int(context["shop_id"])
    started = time.perf_counter()
    request_id = str(context["request_id"])
    conversation_id = context.get("conversation_id")
    result: dict[str, Any]
    error_code = None

    try:
        try:
            args = json.loads(raw_arguments or "{}")
        except (TypeError, ValueError):
            raise ValueError("Tool arguments were not valid JSON")

        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be an object")

        if tool_name == "search_inventory":
            result = _inventory_search(db, shop_id, InventorySearchArgs.model_validate(args))
        elif tool_name == "search_customers":
            result = _customer_search(db, shop_id, CustomerSearchArgs.model_validate(args))
        elif tool_name == "get_sales_summary":
            result = _sales_summary(db, shop_id, SalesSummaryArgs.model_validate(args))
        elif tool_name == "get_attendance_summary":
            result = _attendance_summary(db, shop_id, AttendanceSummaryArgs.model_validate(args))
        elif tool_name == "get_khata_summary":
            ToolArgs.model_validate(args)
            result = _khata_summary(db, shop_id)
        elif tool_name == "get_online_order_summary":
            result = _order_summary(db, shop_id, OrderSummaryArgs.model_validate(args))
        elif tool_name == "prepare_bill_from_current_message":
            ToolArgs.model_validate(args)
            result = await _prepare_bill(db, context)
        elif tool_name == "prepare_invoice_payment":
            result = _prepare_khata_payment(
                db, shop_id, conversation_id, str(context.get("user_text") or ""), KhataPaymentPreviewArgs.model_validate(args)
            )
        elif tool_name == "prepare_online_order_transition":
            result = _prepare_order_transition(
                db, shop_id, conversation_id, OrderTransitionPreviewArgs.model_validate(args)
            )
        elif tool_name == "prepare_khata_ledger_movement":
            parsed = KhataLedgerMovementArgs.model_validate(args)
            from .khata_actions import prepare_khata_ledger_movement
            result = prepare_khata_ledger_movement(
                db,
                shop_id=shop_id,
                conversation_id=conversation_id,
                request_text=str(context.get("user_text") or ""),
                operation=parsed.operation,
                customer_phone=parsed.customer_phone,
                amount=parsed.amount,
                customer_name=parsed.customer_name,
                description=parsed.description,
            )
        else:
            raise ValueError("Tool is not in the server allowlist")
    except ValidationError:
        db.rollback()
        error_code = "INVALID_TOOL_ARGUMENTS"
        result = {"success": False, "error_code": error_code, "message": "The requested tool arguments were invalid."}
    except HTTPException as exc:
        db.rollback()
        error_code = f"BACKEND_{exc.status_code}"
        result = {"success": False, "error_code": error_code, "message": str(exc.detail)[:300]}
    except (ValueError, TypeError):
        db.rollback()
        error_code = "INVALID_REQUEST"
        result = {"success": False, "error_code": error_code, "message": "The requested tool input could not be processed safely."}
    except Exception:
        db.rollback()
        error_code = "TOOL_EXECUTION_FAILED"
        result = {"success": False, "error_code": error_code, "message": "This information is temporarily unavailable. Please try again."}

    audit_success = bool(result.get("success", error_code is None))
    try:
        _record_tool_execution(
            db,
            shop_id=shop_id,
            conversation_id=conversation_id,
            request_id=request_id,
            tool_name=tool_name,
            started_at=started,
            success=audit_success,
            error_code=error_code or result.get("error_code"),
        )
        # Commit the tool result (including a pending bill preview) and audit
        # record together before the graph performs another network call.
        db.commit()
    except Exception:
        db.rollback()
        import logging
        logging.getLogger(__name__).exception("Could not commit Retail Mind agent tool result and audit metadata")
        return {
            "success": False,
            "error_code": "TOOL_COMMIT_FAILED",
            "message": "The tool result could not be safely saved. Please retry after checking the relevant Retail Mind screen.",
        }
    return result
