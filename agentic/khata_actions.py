"""Preview and confirmation helpers for the legacy Khata credit ledger.

All writes are performed in the owner's existing Khata ledger, history and
universal transaction tables in one database transaction. The model only
prepares a preview; the authenticated app confirms it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .preview_policy import preview_expires_at, preview_ttl_seconds

from .preview_policy import expired_preview_detail

from models import (
    AgentPendingAction,
    Customer,
    KhataBalance,
    KhataHistory,
    KhataTransactionType,
    UniversalTransaction,
    UniversalTransactionType,
    User,
)

_ACTION_TYPE = "KHATA_LEDGER_MOVEMENT"
_MAX_AMOUNT = Decimal("100000000.00")


def _money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid Khata amount") from exc
    if not amount.is_finite():
        raise ValueError("Invalid Khata amount")
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= 0 or amount > _MAX_AMOUNT:
        raise ValueError("Khata amount must be greater than zero and within the supported limit")
    return amount


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _preview_hash(action_id: str, shop_id: int, preview: dict, payload: dict) -> str:
    material = {
        "action_id": action_id,
        "shop_id": int(shop_id),
        "preview": preview,
        "payload": payload,
    }
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()


def prepare_khata_ledger_movement(
    db: Session,
    *,
    shop_id: int,
    conversation_id: str,
    request_text: str,
    operation: str,
    customer_phone: str | None,
    amount: Any,
    customer_name: str | None = None,
    description: str | None = None,
) -> dict:
    operation = str(operation or "").strip().upper()
    if operation not in {"CREDIT", "REPAYMENT"}:
        raise ValueError("Choose CREDIT or REPAYMENT")
    if not conversation_id:
        raise ValueError("A saved conversation is required to prepare a Khata action")

    phone = str(customer_phone or "").strip() or None
    name = " ".join(str(customer_name or "").split())[:100] or None
    if not phone and not name:
        raise ValueError("Provide the customer name or phone number")
    if phone and (
        len(phone) != 10 or not phone.isdigit() or phone[0] not in "6789"
    ):
        raise ValueError("Enter a valid 10-digit Indian mobile number")

    # Resolve names only inside this authenticated shop. Prefer an existing
    # Khata ledger identity, then a unique active CRM customer. A new name-only
    # identity is allowed only for a CREDIT; repayments must match an account.
    account = None
    if phone:
        account = db.query(KhataBalance).filter(
            KhataBalance.shop_id == shop_id,
            KhataBalance.customer_phone == phone,
        ).with_for_update().first()
        if not name:
            if account and account.customer_name:
                name = " ".join(str(account.customer_name).split())[:100]
            else:
                crm = db.query(Customer).filter(
                    Customer.user_id == shop_id,
                    Customer.phone == phone,
                    Customer.is_active.is_(True),
                ).first()
                if crm:
                    name = " ".join(str(crm.customer_name or "").split())[:100] or None
        elif account and account.customer_name:
            if str(account.customer_name).strip().casefold() != name.casefold():
                raise ValueError("The supplied customer name does not match this Khata phone number")
    else:
        matches = db.query(KhataBalance).filter(
            KhataBalance.shop_id == shop_id,
            func.lower(func.trim(KhataBalance.customer_name)) == name.casefold(),
        ).with_for_update().all()
        if len(matches) > 1:
            raise ValueError("More than one Khata customer has that name. Provide the customer's phone number")
        if len(matches) == 1:
            account = matches[0]
            phone = str(account.customer_phone or "").strip() or None
            name = " ".join(str(account.customer_name or name).split())[:100]
        else:
            customers = db.query(Customer).filter(
                Customer.user_id == shop_id,
                Customer.is_active.is_(True),
                func.lower(func.trim(Customer.customer_name)) == name.casefold(),
            ).all()
            if len(customers) > 1:
                raise ValueError("More than one customer has that name. Provide the customer's phone number")
            if len(customers) == 1:
                matched_customer = customers[0]
                phone = str(matched_customer.phone or "").strip() or None
                if not phone:
                    raise ValueError("The matching CRM customer has no phone number. Use a different unique customer identity")
                if (
                    len(phone) != 10
                    or not phone.isdigit()
                    or phone[0] not in "6789"
                ):
                    raise ValueError("The matching CRM customer has an invalid phone number. Verify the customer record")
                account = db.query(KhataBalance).filter(
                    KhataBalance.shop_id == shop_id,
                    KhataBalance.customer_phone == phone,
                ).with_for_update().first()
            elif operation == "REPAYMENT":
                raise ValueError("No existing Khata account matches that customer name")

    if operation == "REPAYMENT" and account is None:
        raise ValueError("No existing Khata account matches this customer")

    value = _money(amount)
    note = " ".join(str(description or "").split())[:180]
    note = note or (
        "Owner-confirmed Khata credit"
        if operation == "CREDIT"
        else "Owner-confirmed Khata repayment"
    )

    normalized_request = " ".join(str(request_text or "").split()).casefold()[:1000]
    identity = phone or f"name:{(name or '').casefold()}"
    key_material = (
        f"{shop_id}:{conversation_id}:{operation}:{identity}:{value}:{note}:{normalized_request}"
    )
    idempotency_key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
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
                "message": "This Khata request already has a confirmation action. No second preview was created.",
            }
        return {
            "success": False,
            "needs_clarification": True,
            "message": "This Khata request already expired or failed. Start a new request.",
        }

    current_balance = Decimal(str((account.khata_balance if account else 0) or 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if operation == "REPAYMENT" and value > current_balance:
        raise ValueError(
            f"Repayment cannot exceed the current Khata balance of ₹{current_balance:.2f}"
        )

    resulting_balance = (
        current_balance + value
        if operation == "CREDIT"
        else current_balance - value
    )
    action_id = str(uuid.uuid4())
    resolved_name = name or (
        str(account.customer_name or "Customer") if account else "New Khata customer"
    )
    preview = {
        "operation": "ADD_KHATA_CREDIT" if operation == "CREDIT" else "RECORD_KHATA_REPAYMENT",
        "customer_name": resolved_name,
        "customer_phone_last4": phone[-4:] if phone else None,
        "amount": float(value),
        "balance_before": float(current_balance),
        "balance_after": float(resulting_balance),
        "currency": "INR",
        "requires_owner_confirmation": True,
        "expires_in_seconds": preview_ttl_seconds(),
        "warning": (
            "This adds a credit balance to the legacy Khata ledger; it does not create an invoice."
            if operation == "CREDIT"
            else "This records an owner-reported repayment; it does not independently verify a bank transfer or cash receipt."
        ),
    }
    payload = {
        "operation": operation,
        "customer_phone": phone,
        "customer_name": resolved_name,
        "amount": str(value),
        "expected_balance": str(current_balance),
        "description": note,
        "ledger_idempotency_key": f"agent-khata-{action_id}",
    }
    digest = _preview_hash(action_id, shop_id, preview, payload)
    db.add(AgentPendingAction(
        id=action_id,
        user_id=shop_id,
        conversation_id=conversation_id,
        action_type=_ACTION_TYPE,
        status="PENDING",
        idempotency_key=idempotency_key,
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
        "message": "Khata preview prepared. No ledger balance has changed. Review and confirm this exact action in Retail Mind.",
    }

def confirm_khata_ledger_movement(
    db: Session,
    *,
    shop_id: int,
    action_id: str,
    supplied_preview_hash: str,
) -> dict:
    action = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
        AgentPendingAction.action_type == _ACTION_TYPE,
    ).with_for_update().first()
    if action is None:
        raise HTTPException(status_code=404, detail="Khata preview not found.")

    expected_hash = _preview_hash(action.id, shop_id, action.preview, action.payload)
    if (
        not supplied_preview_hash
        or not hmac.compare_digest(action.preview_hash, supplied_preview_hash)
        or not hmac.compare_digest(action.preview_hash, expected_hash)
    ):
        raise HTTPException(status_code=409, detail="The Khata preview changed. Prepare and review it again.")

    history_query = (
        db.query(KhataHistory)
        .join(KhataBalance, KhataBalance.id == KhataHistory.khata_id)
        .filter(
            KhataBalance.shop_id == shop_id,
            KhataHistory.idempotency_key == action.payload.get("ledger_idempotency_key"),
        )
    )
    if action.status == "COMPLETED":
        history = history_query.first()
        if history is None:
            raise HTTPException(status_code=503, detail="The previous Khata action needs manual verification.")
        return {**(action.result or {}), "duplicate_confirmation": True}
    if action.status == "EXPIRED":
        raise HTTPException(status_code=410, detail=expired_preview_detail(action_id, "Khata"))
    if action.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"This Khata preview cannot be confirmed in state {action.status}.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if action.expires_at <= now:
        action.status = "EXPIRED"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=410, detail=expired_preview_detail(action_id, "Khata"))

    payload = action.payload
    operation = str(payload.get("operation") or "").upper()
    if operation not in {"CREDIT", "REPAYMENT"}:
        raise HTTPException(status_code=409, detail="The Khata action type is invalid.")

    # Lock the owner row to serialize even first-credit operations where no
    # KhataBalance row exists yet. Per-account row locks then protect the
    # customer's balance against other app/API updates.
    owner = db.query(User).filter(User.id == shop_id).with_for_update().first()
    if owner is None:
        raise HTTPException(status_code=404, detail="Shop owner not found.")

    phone = str(payload.get("customer_phone") or "").strip() or None
    customer_name = str(payload.get("customer_name") or "Customer").strip()[:100]
    if phone:
        account = db.query(KhataBalance).filter(
            KhataBalance.shop_id == shop_id,
            KhataBalance.customer_phone == phone,
        ).with_for_update().first()
    else:
        account = db.query(KhataBalance).filter(
            KhataBalance.shop_id == shop_id,
            KhataBalance.customer_phone.is_(None),
            func.lower(func.trim(KhataBalance.customer_name)) == customer_name.casefold(),
        ).with_for_update().first()
    current_balance = Decimal(str((account.khata_balance if account else 0) or 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    expected_balance = Decimal(str(payload["expected_balance"]))
    amount = _money(payload["amount"])
    if current_balance != expected_balance:
        action.status = "FAILED"
        action.error_code = "KHATA_BALANCE_CHANGED"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=409, detail="The customer's Khata balance changed after preview. Refresh and prepare a new action.")

    if operation == "REPAYMENT" and (account is None or amount > current_balance):
        action.status = "FAILED"
        action.error_code = "KHATA_REPAYMENT_BALANCE_CHANGED"
        action.updated_at = now
        db.commit()
        raise HTTPException(status_code=409, detail="The customer's outstanding Khata balance is no longer sufficient. Prepare a new action.")

    if account is None:
        if operation == "REPAYMENT":
            action.status = "FAILED"
            action.error_code = "KHATA_ACCOUNT_NOT_FOUND"
            action.updated_at = now
            db.commit()
            raise HTTPException(status_code=409, detail="The customer's Khata account no longer exists. Prepare a new action.")
        account = KhataBalance(
            shop_id=shop_id,
            customer_phone=phone,
            customer_name=customer_name or "Customer",
            khata_balance=Decimal("0.00"),
        )
        db.add(account)
        db.flush()
    elif payload.get("customer_name") and not account.customer_name:
        account.customer_name = str(payload["customer_name"])[:100]

    new_balance = current_balance + amount if operation == "CREDIT" else current_balance - amount
    account.khata_balance = new_balance
    account.last_transaction = now

    reference_id = f"AGENT-KHATA-{action.id}"
    db.add(KhataHistory(
        khata_id=account.id,
        transaction_type=(
            KhataTransactionType.INVOICE if operation == "CREDIT" else KhataTransactionType.PAYMENT
        ),
        amount=amount,
        reference_id=reference_id,
        description=str(payload.get("description") or "")[:200],
        transaction_date=now,
        idempotency_key=str(payload["ledger_idempotency_key"]),
    ))
    db.add(UniversalTransaction(
        shop_id=shop_id,
        tx_type=UniversalTransactionType.INCOME,
        category="KHATA_CREDIT" if operation == "CREDIT" else "KHATA_REPAY",
        amount=amount,
        reference_id=reference_id,
        description=(
            f"{'Khata credit' if operation == 'CREDIT' else 'Khata repayment'} for "
            + (f"customer ending {phone[-4:]}" if phone else customer_name)
        ),
        tx_date=now,
    ))

    result = {
        "success": True,
        "verified": True,
        "action_id": action.id,
        "operation": operation,
        "khata_id": int(account.id),
        "customer_name": str(account.customer_name or "Customer"),
        "customer_phone_last4": phone[-4:] if phone else None,
        "amount": float(amount),
        "balance_before": float(current_balance),
        "balance_after": float(new_balance),
        "currency": "INR",
        "message": "Khata credit recorded successfully." if operation == "CREDIT" else "Khata repayment recorded successfully.",
    }
    action.status = "COMPLETED"
    action.result = result
    action.completed_at = now
    action.updated_at = now
    try:
        # Balance, history, journal and completed action commit atomically.
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=503, detail="The Khata action could not be safely saved. Check the Khata screen before retrying.")

    # Confirm that the idempotent history record really persisted before
    # returning success to the caller.
    persisted = history_query.filter(
        KhataHistory.idempotency_key == str(payload["ledger_idempotency_key"])
    ).first()
    if persisted is None:
        raise HTTPException(status_code=503, detail="The Khata action was saved but could not be verified. Refresh the Khata screen.")
    return result
