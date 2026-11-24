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
from typing import Any, Optional
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
    KhataBalance,
    OnlineOrder,
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
    conversation_id: str,
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
                "phone": str(row.phone or ""),
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
    rows = (
        db.query(KhataBalance)
        .filter(KhataBalance.shop_id == shop_id, KhataBalance.khata_balance > 0)
        .order_by(KhataBalance.khata_balance.desc())
        .limit(10)
        .all()
    )
    total = (
        db.query(func.coalesce(func.sum(KhataBalance.khata_balance), 0))
        .filter(KhataBalance.shop_id == shop_id, KhataBalance.khata_balance > 0)
        .scalar()
    )
    return {
        "total_outstanding": float(_money(total or 0)),
        "customers_returned": len(rows),
        "top_customers": [
            {
                "name": str(row.customer_name or "Customer"),
                "phone_last4": str(row.customer_phone or "")[-4:],
                "outstanding": float(_money(row.khata_balance or 0)),
            }
            for row in rows
        ],
        "note": "Read-only summary. Use the existing Khata screen to record credit or repayment.",
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


async def dispatch_tool(tool_name: str, raw_arguments: str, context: dict) -> dict:
    """Validate an LLM function call, execute only an allowlisted tool, and audit it."""
    db: Session = context["db"]
    shop_id = int(context["shop_id"])
    started = time.perf_counter()
    request_id = str(context["request_id"])
    conversation_id = str(context["conversation_id"])
    success = False
    error_code = None
    try:
        try:
            args = json.loads(raw_arguments or "{}")
        except (TypeError, ValueError):
            raise ValueError("Tool arguments were not valid JSON")

        if not isinstance(args, dict):
            raise ValueError("Tool arguments must be an object")

        if tool_name == "search_inventory":
            data = _inventory_search(db, shop_id, InventorySearchArgs.model_validate(args))
        elif tool_name == "search_customers":
            data = _customer_search(db, shop_id, CustomerSearchArgs.model_validate(args))
        elif tool_name == "get_sales_summary":
            data = _sales_summary(db, shop_id, SalesSummaryArgs.model_validate(args))
        elif tool_name == "get_attendance_summary":
            data = _attendance_summary(db, shop_id, AttendanceSummaryArgs.model_validate(args))
        elif tool_name == "get_khata_summary":
            ToolArgs.model_validate(args)
            data = _khata_summary(db, shop_id)
        elif tool_name == "get_online_order_summary":
            data = _order_summary(db, shop_id, OrderSummaryArgs.model_validate(args))
        elif tool_name == "prepare_bill_from_current_message":
            ToolArgs.model_validate(args)
            data = await _prepare_bill(db, context)
        else:
            raise ValueError("Tool is not in the server allowlist")

        success = True
        return data
    except ValidationError:
        error_code = "INVALID_TOOL_ARGUMENTS"
        return {"success": False, "error_code": error_code, "message": "The requested tool arguments were invalid."}
    except HTTPException as exc:
        error_code = f"BACKEND_{exc.status_code}"
        return {"success": False, "error_code": error_code, "message": str(exc.detail)[:300]}
    except (ValueError, TypeError):
        error_code = "INVALID_REQUEST"
        return {"success": False, "error_code": error_code, "message": "The requested tool input could not be processed safely."}
    except Exception:
        error_code = "TOOL_EXECUTION_FAILED"
        return {"success": False, "error_code": error_code, "message": "This information is temporarily unavailable. Please try again."}
    finally:
        _record_tool_execution(
            db,
            shop_id=shop_id,
            conversation_id=conversation_id,
            request_id=request_id,
            tool_name=tool_name,
            started_at=started,
            success=success,
            error_code=error_code,
        )
