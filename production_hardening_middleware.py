"""Production-only request hardening for the online storefront.

This module is loaded by the Render entrypoint after the FastAPI app is created.
It deliberately wraps existing endpoints instead of duplicating business logic.
"""

import hashlib
import hmac
import json
import re
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from db import sessionLocal
from models import OnlineOrder
from security import SECRET_KEY, decode_token

_GUEST_ORDER_PATH = "/store/guest-order"
_GUEST_TRACK_RE = re.compile(r"^/store/order/(\d+)/guest-track$")
_OWNER_ACTION_RE = re.compile(r"^/store/owner/orders/(\d+)/action$")


def _tracking_token(order_id: int, phone: str) -> str:
    message = f"guest-order:{order_id}:{phone.strip()}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _authorized_owner(request: Request) -> bool:
    """Return True only when the request carries a valid owner JWT."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return False
    try:
        payload = decode_token(header.split(" ", 1)[1].strip())
        return payload.get("role") == "OWNER" and bool(payload.get("sub"))
    except Exception:
        return False


def _json_response_like(response: Response, payload: dict) -> JSONResponse:
    headers = dict(response.headers)
    headers.pop("content-length", None)
    headers.pop("content-encoding", None)
    return JSONResponse(
        status_code=response.status_code,
        content=payload,
        headers=headers,
    )


def install(app) -> None:
    """Install production request guards on the already-created FastAPI app."""

    @app.middleware("http")
    async def production_hardening(request: Request, call_next):
        path = request.url.path

        # ------------------------------------------------------------------
        # Guest checkout: enforce the only payment mode actually implemented
        # by the backend. This prevents the UI from claiming an online payment
        # succeeded when no payment gateway transaction exists.
        # ------------------------------------------------------------------
        guest_order = path == _GUEST_ORDER_PATH and request.method == "POST"
        guest_payload: Optional[dict] = None
        if guest_order:
            try:
                raw = await request.body()
                guest_payload = json.loads(raw or b"{}")
            except Exception:
                return JSONResponse(status_code=400, content={"detail": "Invalid JSON request body."})

            requested_payment = str(guest_payload.get("payment_method", "COD")).upper()
            if requested_payment != "COD":
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Online payments are not enabled yet. Please use Cash on Delivery."},
                )

            # If Firebase verification is supplied, a mismatched verified phone
            # must fail closed. The legacy handler logged the mismatch and then
            # continued with an unverified guest order.
            firebase_token = guest_payload.get("firebase_id_token")
            phone = str(guest_payload.get("phone", "")).strip()
            if firebase_token:
                try:
                    import firebase_admin
                    from firebase_admin import auth

                    if not firebase_admin._apps:
                        return JSONResponse(status_code=503, content={"detail": "Firebase authentication is not configured."})
                    decoded = auth.verify_id_token(firebase_token)
                    verified_phone = str(decoded.get("phone_number") or "")
                    normalized_verified = "".join(ch for ch in verified_phone if ch.isdigit())
                    normalized_phone = "".join(ch for ch in phone if ch.isdigit())
                    if not normalized_verified.endswith(normalized_phone):
                        return JSONResponse(status_code=403, content={"detail": "Verified phone number does not match checkout phone number."})
                except JSONResponse:
                    raise
                except Exception:
                    return JSONResponse(status_code=401, content={"detail": "Invalid or expired Firebase verification token."})

        # ------------------------------------------------------------------
        # Guest order tracking: phone number alone is not a sufficient secret.
        # Require a server-derived tracking token returned at checkout.
        # ------------------------------------------------------------------
        track_match = _GUEST_TRACK_RE.match(path) if request.method == "GET" else None
        if track_match:
            order_id = int(track_match.group(1))
            phone = request.query_params.get("phone", "").strip()
            token = request.headers.get("X-Guest-Tracking-Token", "").strip()
            expected = _tracking_token(order_id, phone) if phone else ""
            if not token or not expected or not hmac.compare_digest(token, expected):
                return JSONResponse(status_code=403, content={"detail": "Valid guest tracking credentials are required."})

        # ------------------------------------------------------------------
        # Owner order state machine: prevent impossible transitions that would
        # otherwise create duplicate sales/invoices or restore already-sold
        # stock. The existing endpoint remains responsible for RBAC and the
        # actual mutation.
        # ------------------------------------------------------------------
        owner_action_match = _OWNER_ACTION_RE.match(path) if request.method == "POST" else None
        if owner_action_match and _authorized_owner(request):
            order_id = int(owner_action_match.group(1))
            action = request.query_params.get("action", "").upper()
            db = sessionLocal()
            try:
                order = db.query(OnlineOrder).filter(OnlineOrder.id == order_id).first()
                if order:
                    allowed = {
                        "PENDING": {"ACCEPT", "REJECT"},
                        "ACCEPTED": {"DISPATCH"},
                        "DISPATCHED": {"DELIVER"},
                        "DELIVERED": set(),
                        "REJECTED": set(),
                    }
                    if action not in allowed.get(order.order_status, set()):
                        return JSONResponse(
                            status_code=409,
                            content={
                                "detail": f"Invalid order transition: {order.order_status} -> {action or 'UNKNOWN'}."
                            },
                        )
            finally:
                db.close()

        response = await call_next(request)

        # Add a non-guessable tracking credential to successful guest orders.
        if guest_order and response.status_code < 300 and guest_payload:
            try:
                body = b"".join([chunk async for chunk in response.body_iterator])
                payload = json.loads(body.decode("utf-8"))
                order_id = int(payload["order_id"])
                phone = str(guest_payload["phone"]).strip()
                payload["tracking_token"] = _tracking_token(order_id, phone)
                return _json_response_like(response, payload)
            except Exception:
                # Never turn a successful order into a false client failure just
                # because the optional response enrichment failed.
                return response

        return response
