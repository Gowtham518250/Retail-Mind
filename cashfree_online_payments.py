"""Cashfree one-time Payment Gateway integration for Retail Mind online orders.

Order amounts and ownership are always read from PostgreSQL. The backend is the
only component allowed to create Cashfree orders or confirm successful payment.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db
from models import Invoice, OnlineCustomerAuth, OnlineOrder, UniversalTransaction
from security import check_rate_limit, customer_only
from durable_sync import append_sync_event
from realtime import publish_realtime_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/store", tags=["Cashfree Online Payments"])

CASHFREE_API_VERSION = os.getenv("CASHFREE_API_VERSION", "2025-01-01")


def _cashfree_webhook_secret() -> str:
    # Cashfree PG normally signs webhooks with the app secret. Dedicated
    # overrides are supported for deployments that intentionally separate it.
    return (
        os.getenv("CASHFREE_PG_WEBHOOK_SECRET")
        or os.getenv("CASHFREE_WEBHOOK_SECRET")
        or os.getenv("CASHFREE_SECRET_KEY")
        or ""
    ).strip()


def cashfree_pg_is_configured(*, require_webhook: bool = True) -> bool:
    """Return whether one-time PG collection is explicitly enabled and configured."""
    enabled = (os.getenv("CASHFREE_PG_ENABLED") or "").strip().lower() == "true"
    app_id = (os.getenv("CASHFREE_APP_ID") or "").strip()
    secret = (os.getenv("CASHFREE_SECRET_KEY") or "").strip()
    env = (os.getenv("CASHFREE_ENV") or "sandbox").strip().lower()
    webhook_secret = _cashfree_webhook_secret()
    return bool(
        enabled
        and app_id
        and secret
        and env in {"sandbox", "production"}
        and (not require_webhook or len(webhook_secret) >= 32)
    )


def _cashfree_config():
    if not cashfree_pg_is_configured(require_webhook=True):
        raise HTTPException(
            status_code=503,
            detail="Cashfree online payments are not enabled or are missing backend credentials/webhook configuration.",
        )
    app_id = os.getenv("CASHFREE_APP_ID", "").strip()
    secret = os.getenv("CASHFREE_SECRET_KEY", "").strip()
    env = (os.getenv("CASHFREE_ENV") or "sandbox").strip().lower()
    base_url = (
        "https://sandbox.cashfree.com/pg"
        if env == "sandbox"
        else "https://api.cashfree.com/pg"
    )
    return app_id, secret, env, base_url


def _cashfree_headers(app_id: str, secret: str, *, idempotency_key: Optional[str] = None):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-version": CASHFREE_API_VERSION,
        "x-client-id": app_id,
        "x-client-secret": secret,
    }
    if idempotency_key:
        headers["x-idempotency-key"] = idempotency_key
    return headers


def _money(value, *, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise InvalidOperation
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=502, detail=f"Cashfree returned an invalid {label}.") from None


def _verify_cashfree_signature(
    raw_body: bytes,
    timestamp: str,
    supplied_signature: str,
    *,
    secret: Optional[str] = None,
) -> None:
    """Verify Cashfree's Base64(HMAC-SHA256(timestamp + raw body)) signature."""
    signing_secret = secret if secret is not None else _cashfree_webhook_secret()
    if len(signing_secret) < 32:
        raise HTTPException(status_code=503, detail="Cashfree PG webhook secret is not configured.")
    if not timestamp or not supplied_signature:
        raise HTTPException(status_code=401, detail="Missing Cashfree webhook signature headers.")
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        timestamp.encode("utf-8") + raw_body,
        hashlib.sha256,
    ).digest()
    expected = base64.b64encode(digest).decode("ascii")
    if not hmac.compare_digest(expected, supplied_signature.strip()):
        raise HTTPException(status_code=401, detail="Invalid Cashfree webhook signature.")


async def _cashfree_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    app_id: str,
    secret: str,
    base_url: str,
    payload: Optional[dict] = None,
    idempotency_key: Optional[str] = None,
):
    try:
        response = await client.request(
            method,
            f"{base_url}{path}",
            headers=_cashfree_headers(
                app_id, secret, idempotency_key=idempotency_key
            ),
            json=payload,
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "Cashfree PG request failed method=%s path=%s error_type=%s",
            method,
            path,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Cashfree could not be reached. The order has not been marked paid; check its status before retrying.",
        ) from None

    if response.status_code not in (200, 201):
        logger.warning(
            "Cashfree PG returned an error method=%s path=%s status=%s response=%s",
            method,
            path,
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "CASHFREE_PG_REQUEST_FAILED",
                "provider_status": response.status_code,
                "message": "Cashfree did not confirm this payment operation. Check the order status before retrying.",
            },
        )
    try:
        data = response.json()
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="Cashfree returned an invalid response.") from None
    if not isinstance(data, (dict, list)):
        raise HTTPException(status_code=502, detail="Cashfree returned an unexpected response.")
    return data


async def _get_verified_successful_payment(
    client: httpx.AsyncClient,
    *,
    app_id: str,
    secret: str,
    base_url: str,
    provider_order_id: str,
    expected_amount: Decimal,
    expected_payment_id: Optional[str] = None,
):
    """Verify the order and exact successful payment using Cashfree server APIs."""
    provider_order = await _cashfree_request(
        client,
        "GET",
        f"/orders/{provider_order_id}",
        app_id=app_id,
        secret=secret,
        base_url=base_url,
    )
    if not isinstance(provider_order, dict):
        raise HTTPException(status_code=502, detail="Cashfree order response is invalid.")
    if str(provider_order.get("order_status") or "").upper() != "PAID":
        return None
    if str(provider_order.get("order_currency") or "").upper() != "INR":
        raise HTTPException(status_code=409, detail="Cashfree order currency does not match INR.")
    if _money(provider_order.get("order_amount"), label="order amount") != expected_amount:
        raise HTTPException(status_code=409, detail="Cashfree order amount does not match the Retail Mind order.")

    payments = await _cashfree_request(
        client,
        "GET",
        f"/orders/{provider_order_id}/payments",
        app_id=app_id,
        secret=secret,
        base_url=base_url,
    )
    if not isinstance(payments, list):
        raise HTTPException(status_code=502, detail="Cashfree payments response is invalid.")

    successful = []
    for payment in payments:
        if not isinstance(payment, dict):
            continue
        if str(payment.get("payment_status") or "").upper() != "SUCCESS":
            continue
        payment_id = str(payment.get("cf_payment_id") or "").strip()
        if not payment_id:
            continue
        if str(payment.get("order_id") or "") != provider_order_id:
            continue
        if str(payment.get("order_currency") or "").upper() != "INR":
            continue
        if str(payment.get("payment_currency") or "").upper() != "INR":
            continue
        if _money(payment.get("payment_amount"), label="payment amount") != expected_amount:
            continue
        if expected_payment_id and payment_id != str(expected_payment_id):
            continue
        successful.append(payment)

    if expected_payment_id:
        return successful[0] if len(successful) == 1 else None
    if len(successful) > 1:
        logger.error(
            "Multiple successful Cashfree payments found for one Retail Mind order cashfree_order_id=%s",
            provider_order_id,
        )
        raise HTTPException(
            status_code=409,
            detail="Multiple successful Cashfree transactions were found. Payment reconciliation requires manual review.",
        )
    return successful[0] if successful else None


def _refund_journal_entry(db: Session, *, order: OnlineOrder, payment_id: str, amount: Decimal):
    """Record a captured payment that cannot be applied to this order as a sale."""
    reference = f"CF-REFUND-{payment_id}"[:100]
    exists = db.query(UniversalTransaction.id).filter(
        UniversalTransaction.shop_id == order.shop_id,
        UniversalTransaction.reference_id == reference,
        UniversalTransaction.category == "REFUND_REQUIRED",
    ).first()
    if exists is None:
        db.add(UniversalTransaction(
            shop_id=order.shop_id,
            tx_type="INCOME",
            category="REFUND_REQUIRED",
            amount=float(amount),
            reference_id=reference,
            description=f"Cashfree payment requires refund/manual reconciliation for online order #{order.id}",
        ))


def _settle_verified_payment(
    db: Session,
    *,
    provider_order_id: str,
    payment: dict,
) -> dict:
    """Apply one verified Cashfree payment to the order and canonical invoice ledger."""
    payment_id = str(payment.get("cf_payment_id") or "").strip()
    if not payment_id:
        raise HTTPException(status_code=409, detail="Cashfree payment reference is missing.")
    amount = _money(payment.get("payment_amount"), label="payment amount")

    existing_payment_order = db.query(OnlineOrder.id).filter(
        OnlineOrder.cashfree_payment_id == payment_id,
    ).first()
    order = db.query(OnlineOrder).with_for_update().filter(
        OnlineOrder.cashfree_order_id == provider_order_id,
    ).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Retail Mind order for this Cashfree payment was not found.")
    if existing_payment_order and int(existing_payment_order[0]) != int(order.id):
        raise HTTPException(status_code=409, detail="Cashfree payment reference is already linked to another order.")
    if _money(order.total_amount, label="Retail Mind order amount") != amount:
        raise HTTPException(status_code=409, detail="Cashfree payment amount does not match the Retail Mind order.")
    if str(order.payment_method or "").upper() != "UPI":
        raise HTTPException(status_code=409, detail="This Retail Mind order was not created for online payment.")

    if str(order.payment_status or "").upper() in {"PAID", "REFUND_REQUIRED"}:
        if str(order.cashfree_payment_id or "") == payment_id:
            return {
                "success": True,
                "duplicate": True,
                "order_id": order.id,
                "payment_status": order.payment_status,
            }
        # A second successful charge must never be counted as another sale.
        _refund_journal_entry(db, order=order, payment_id=payment_id, amount=amount)
        if not order.cashfree_payment_id:
            order.cashfree_payment_id = payment_id
        event = append_sync_event(db, {
            "event_id": str(uuid.uuid4()),
            "type": "order.payment_refund_required",
            "shop_id": order.shop_id,
            "order_id": order.id,
            "amount": float(amount),
            "payment_reference": payment_id,
            "source": "CASHFREE_PG",
        })
        db.commit()
        publish_realtime_event(event)
        logger.error(
            "Additional Cashfree successful payment requires refund shop_id=%s order_id=%s cf_payment_id=%s",
            order.shop_id, order.id, payment_id,
        )
        return {
            "success": True,
            "duplicate": False,
            "refund_required": True,
            "order_id": order.id,
            "payment_status": order.payment_status,
        }

    order_status = str(getattr(order.order_status, "value", order.order_status) or "").upper()
    if order_status in {"CANCELLED", "REJECTED", "RETURNED"}:
        order.payment_status = "REFUND_REQUIRED"
        order.cashfree_payment_id = payment_id
        order.payment_reference = payment_id
        order.payment_confirmation_source = "CASHFREE_PG"
        order.payment_confirmed_at = datetime.utcnow()
        _refund_journal_entry(db, order=order, payment_id=payment_id, amount=amount)
        event = append_sync_event(db, {
            "event_id": str(uuid.uuid4()),
            "type": "order.payment_refund_required",
            "shop_id": order.shop_id,
            "order_id": order.id,
            "amount": float(amount),
            "payment_reference": payment_id,
            "source": "CASHFREE_PG",
        })
        db.commit()
        publish_realtime_event(event)
        return {
            "success": True,
            "refund_required": True,
            "order_id": order.id,
            "payment_status": order.payment_status,
        }

    order.cashfree_payment_id = payment_id
    order.payment_reference = payment_id
    order.payment_confirmation_source = "CASHFREE_PG"
    order.payment_confirmed_at = datetime.utcnow()
    order.payment_status = "PAID"

    events = []
    invoice = db.query(Invoice).filter(
        Invoice.user_id == order.shop_id,
        Invoice.source == "ONLINE_ORDER",
        Invoice.notes.like(f"%Online Order #{order.id}%"),
        Invoice.status != "CANCELLED",
    ).with_for_update().first()

    if invoice is not None:
        outstanding = max(
            Decimal("0"),
            _money(invoice.total_amount or 0, label="invoice total")
            - _money(invoice.paid_amount or 0, label="invoice paid amount"),
        )
        if abs(outstanding - amount) > Decimal("0.01"):
            # A non-zero previous invoice receipt means this Cashfree capture
            # cannot safely be applied as a second full collection.
            _refund_journal_entry(db, order=order, payment_id=payment_id, amount=amount)
            order.payment_status = "REFUND_REQUIRED"
            events.append(append_sync_event(db, {
                "event_id": str(uuid.uuid4()),
                "type": "order.payment_refund_required",
                "shop_id": order.shop_id,
                "order_id": order.id,
                "amount": float(amount),
                "payment_reference": payment_id,
                "source": "CASHFREE_PG",
            }))
            db.commit()
            for event in events:
                publish_realtime_event(event)
            return {
                "success": True,
                "refund_required": True,
                "order_id": order.id,
                "payment_status": order.payment_status,
            }

        if outstanding > Decimal("0.01"):
            from invoices_billing import PaymentWriteRequest, _apply_payment_write

            payment_key = hashlib.sha256(
                f"cashfree-online-order:{order.shop_id}:{order.id}:{payment_id}".encode("utf-8")
            ).hexdigest()
            payment_result = _apply_payment_write(
                data=PaymentWriteRequest(
                    invoice_number=invoice.invoice_number,
                    amount=float(outstanding),
                    payment_method="ONLINE",
                    reference_id=payment_id,
                    idempotency_key=payment_key,
                    source="CASHFREE_PG",
                    timestamp=str(payment.get("payment_completion_time") or payment.get("payment_time") or ""),
                    notes=f"Cashfree PG payment for online order #{order.id}",
                ),
                db=db,
                shop_id=order.shop_id,
                mode="delta",
                commit_transaction=False,
            )
            events.extend(payment_result.get("events", []))

    events.append(append_sync_event(db, {
        "event_id": str(uuid.uuid4()),
        "type": "order.payment_confirmed",
        "shop_id": order.shop_id,
        "order_id": order.id,
        "customer_id": order.customer_id,
        "amount": float(amount),
        "payment_method": "UPI",
        "payment_status": "PAID",
        "payment_confirmation_source": "CASHFREE_PG",
        "payment_reference": payment_id,
    }))
    db.commit()
    for event in events:
        publish_realtime_event(event)

    return {
        "success": True,
        "duplicate": False,
        "order_id": order.id,
        "payment_status": order.payment_status,
        "payment_reference": order.payment_reference,
        "invoice_number": invoice.invoice_number if invoice else None,
    }


@router.post("/order/{order_id}/cashfree/session")
async def create_cashfree_order_session(
    order_id: int,
    db: Session = Depends(get_db),
    current_customer: dict = Depends(customer_only),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Create or reuse a Cashfree checkout session for a signed-in customer's UPI order."""
    app_id, secret, env, base_url = _cashfree_config()
    customer_id = int(current_customer["user_id"])
    order = (
        db.query(OnlineOrder)
        .with_for_update()
        .filter(
            OnlineOrder.id == order_id,
            OnlineOrder.customer_id == customer_id,
        )
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if str(order.payment_method or "").upper() != "UPI":
        raise HTTPException(status_code=409, detail="This order is not configured for online payment.")

    order_status = str(getattr(order.order_status, "value", order.order_status) or "").upper()
    if order_status in {"CANCELLED", "REJECTED", "RETURNED", "DELIVERED"}:
        raise HTTPException(status_code=409, detail="This order can no longer be paid.")
    if str(order.payment_status or "").upper() == "PAID":
        return {
            "success": True,
            "already_paid": True,
            "order_id": order.id,
            "payment_status": "PAID",
        }

    amount = _money(order.total_amount, label="Retail Mind order amount")
    if amount <= Decimal("0"):
        raise HTTPException(status_code=400, detail="Order amount must be greater than zero.")

    customer = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.id == customer_id,
        OnlineCustomerAuth.is_active.is_(True),
    ).first()
    if customer is None:
        raise HTTPException(status_code=401, detail="Customer account is not active.")

    provider_order_id = str(order.cashfree_order_id or f"rm_order_{order.id}")
    idempotency_key = str(uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"retail-mind:cashfree:online-order:{order.id}:{provider_order_id}",
    ))

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        if order.cashfree_order_id:
            provider_order = await _cashfree_request(
                client,
                "GET",
                f"/orders/{provider_order_id}",
                app_id=app_id,
                secret=secret,
                base_url=base_url,
            )
            if not isinstance(provider_order, dict):
                raise HTTPException(status_code=502, detail="Cashfree order response is invalid.")

            provider_status = str(provider_order.get("order_status") or "").upper()
            if provider_status == "PAID":
                payment = await _get_verified_successful_payment(
                    client,
                    app_id=app_id,
                    secret=secret,
                    base_url=base_url,
                    provider_order_id=provider_order_id,
                    expected_amount=amount,
                )
                if payment is None:
                    raise HTTPException(
                        status_code=502,
                        detail="Cashfree reports a paid order but no matching successful payment is available yet.",
                    )
                result = _settle_verified_payment(
                    db,
                    provider_order_id=provider_order_id,
                    payment=payment,
                )
                return {
                    "success": True,
                    "already_paid": True,
                    "order_id": order.id,
                    "payment_status": result.get("payment_status", "PAID"),
                    "refund_required": bool(result.get("refund_required", False)),
                }

            if provider_status == "ACTIVE":
                session_id = str(
                    provider_order.get("payment_session_id")
                    or order.cashfree_payment_session_id
                    or ""
                ).strip()
                if session_id:
                    return {
                        "success": True,
                        "order_id": order.id,
                        "cashfree_order_id": provider_order_id,
                        "payment_session_id": session_id,
                        "environment": env,
                        "currency": "INR",
                        "amount": float(amount),
                    }

            # Cashfree order IDs cannot be reused after an expired/failed
            # checkout. A new provider order ID keeps payment retries safe.
            provider_order_id = f"rm_order_{order.id}_{uuid.uuid4().hex[:8]}"
            idempotency_key = str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"retail-mind:cashfree:online-order:{order.id}:{provider_order_id}",
            ))

        customer_phone = re.sub(r"\D", "", str(customer.phone or ""))
        if len(customer_phone) == 12 and customer_phone.startswith("91"):
            customer_phone = customer_phone[2:]
        if len(customer_phone) != 10:
            raise HTTPException(
                status_code=422,
                detail="The customer account must have a valid 10-digit Indian mobile number for Cashfree checkout.",
            )

        payload = {
            "order_id": provider_order_id,
            "order_amount": float(amount),
            "order_currency": "INR",
            "customer_details": {
                "customer_id": f"retailmind_customer_{customer.id}",
                "customer_name": (customer.user_name or "Retail Mind Customer")[:100],
                "customer_phone": customer_phone,
            },
            "order_note": f"Retail Mind online order #{order.id}"[:250],
        }
        if customer.email and "@" in customer.email and not customer.email.startswith("guest_"):
            payload["customer_details"]["customer_email"] = customer.email[:100]

        return_url = (os.getenv("CASHFREE_PG_RETURN_URL") or "").strip()
        if return_url:
            payload["order_meta"] = {
                "return_url": return_url.replace("{order_id}", provider_order_id)
            }
        notify_url = (os.getenv("CASHFREE_PG_NOTIFY_URL") or "").strip()
        if notify_url:
            payload.setdefault("order_meta", {})["notify_url"] = notify_url

        provider_order = await _cashfree_request(
            client,
            "POST",
            "/orders",
            app_id=app_id,
            secret=secret,
            base_url=base_url,
            payload=payload,
            idempotency_key=idempotency_key,
        )

    if not isinstance(provider_order, dict):
        raise HTTPException(status_code=502, detail="Cashfree order creation response is invalid.")
    if str(provider_order.get("order_id") or "") != provider_order_id:
        raise HTTPException(status_code=502, detail="Cashfree returned an unexpected order ID.")
    if str(provider_order.get("order_currency") or "").upper() != "INR":
        raise HTTPException(status_code=502, detail="Cashfree returned an unexpected currency.")
    if _money(provider_order.get("order_amount"), label="created order amount") != amount:
        raise HTTPException(status_code=502, detail="Cashfree returned an unexpected order amount.")
    payment_session_id = str(provider_order.get("payment_session_id") or "").strip()
    if not payment_session_id:
        raise HTTPException(status_code=502, detail="Cashfree did not return a payment session.")

    order.cashfree_order_id = provider_order_id
    order.cashfree_payment_session_id = payment_session_id
    db.commit()

    return {
        "success": True,
        "order_id": order.id,
        "cashfree_order_id": provider_order_id,
        "payment_session_id": payment_session_id,
        "environment": env,
        "currency": "INR",
        "amount": float(amount),
    }


@router.get("/order/{order_id}/cashfree/status")
async def get_cashfree_order_payment_status(
    order_id: int,
    db: Session = Depends(get_db),
    current_customer: dict = Depends(customer_only),
    _rate_limit: None = Depends(check_rate_limit),
):
    """Reconcile the payment after a mobile/web checkout callback; never trust the callback itself."""
    app_id, secret, _env, base_url = _cashfree_config()
    customer_id = int(current_customer["user_id"])
    order = db.query(OnlineOrder).filter(
        OnlineOrder.id == order_id,
        OnlineOrder.customer_id == customer_id,
    ).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if str(order.payment_method or "").upper() != "UPI" or not order.cashfree_order_id:
        return {
            "order_id": order.id,
            "payment_status": order.payment_status,
            "paid": str(order.payment_status or "").upper() == "PAID",
        }
    if str(order.payment_status or "").upper() == "PAID":
        return {
            "order_id": order.id,
            "payment_status": "PAID",
            "paid": True,
        }

    amount = _money(order.total_amount, label="Retail Mind order amount")
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        payment = await _get_verified_successful_payment(
            client,
            app_id=app_id,
            secret=secret,
            base_url=base_url,
            provider_order_id=order.cashfree_order_id,
            expected_amount=amount,
        )

    if payment is None:
        return {
            "order_id": order.id,
            "payment_status": order.payment_status or "PENDING",
            "paid": False,
        }
    result = _settle_verified_payment(
        db,
        provider_order_id=order.cashfree_order_id,
        payment=payment,
    )
    return {
        "order_id": order.id,
        "payment_status": result.get("payment_status", "PAID"),
        "paid": result.get("payment_status") == "PAID" and not result.get("refund_required", False),
        "refund_required": bool(result.get("refund_required", False)),
    }


@router.post("/cashfree/webhook")
async def cashfree_online_order_webhook(request: Request, db: Session = Depends(get_db)):
    """Verify Cashfree PG webhook and reconcile the provider-side payment before settling."""
    _app_id, _secret, _env, _base_url = _cashfree_config()
    raw_body = await request.body()
    _verify_cashfree_signature(
        raw_body,
        request.headers.get("x-webhook-timestamp", ""),
        request.headers.get("x-webhook-signature", ""),
    )
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid Cashfree webhook JSON.") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Cashfree webhook payload.")

    event_type = str(payload.get("type") or "").upper()
    if event_type != "PAYMENT_SUCCESS_WEBHOOK":
        # Failed, pending and user-dropped events must never settle an order.
        return {"success": True, "ignored": True, "event_type": event_type or "UNKNOWN"}

    data = payload.get("data") or {}
    provider_order_id = str((data.get("order") or {}).get("order_id") or "").strip()
    payment_data = data.get("payment") or {}
    payment_id = str(payment_data.get("cf_payment_id") or "").strip()
    if not provider_order_id or not payment_id:
        raise HTTPException(status_code=400, detail="Cashfree success webhook is missing the order/payment reference.")
    order = db.query(OnlineOrder).filter(
        OnlineOrder.cashfree_order_id == provider_order_id,
    ).first()
    if order is None:
        logger.warning("Cashfree webhook refers to an unknown Retail Mind order cashfree_order_id=%s", provider_order_id)
        return {"success": True, "ignored": True, "reason": "unknown_order"}

    app_id, secret, _env, base_url = _cashfree_config()
    expected_amount = _money(order.total_amount, label="Retail Mind order amount")
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        payment = await _get_verified_successful_payment(
            client,
            app_id=app_id,
            secret=secret,
            base_url=base_url,
            provider_order_id=provider_order_id,
            expected_amount=expected_amount,
            expected_payment_id=payment_id,
        )
    if payment is None:
        # Non-2xx asks Cashfree to retry after its order/payment read models catch up.
        raise HTTPException(status_code=502, detail="Cashfree success event is not yet confirmed by the payment APIs.")

    return _settle_verified_payment(
        db,
        provider_order_id=provider_order_id,
        payment=payment,
    )
