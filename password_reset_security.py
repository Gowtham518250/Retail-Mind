"""
High-assurance password reset challenge flow.

OTP generation, Gmail delivery, and the user's first OTP comparison remain in
Flutter. This service supplies the backend authorization boundary:

1) start challenge
2) register the frontend OTP hash
3) confirm mailbox ownership through a one-time email link
4) authorize a short-lived PasswordReset token after OTP verification

The existing /auth/reset-password endpoint remains the final password-change
endpoint and consumes the one-time PasswordReset token.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import engine, get_db
from models import PasswordReset, User
from rate_limiter import rate_limit_endpoint

logger = logging.getLogger(__name__)
TABLE_NAME = "password_reset_challenges"
CHALLENGE_TTL_SECONDS = 10 * 60
RESET_TOKEN_TTL_SECONDS = 5 * 60
MAX_OTP_ATTEMPTS = 5


class StartResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class RegisterOtpRequest(BaseModel):
    challenge_id: str = Field(min_length=20, max_length=200)
    registration_secret: str = Field(min_length=20, max_length=200)
    otp_hash: str = Field(min_length=64, max_length=64)


class AuthorizeResetRequest(BaseModel):
    challenge_id: str = Field(min_length=20, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    otp: str = Field(min_length=6, max_length=6)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ensure_table() -> None:
    sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        challenge_id VARCHAR(128) PRIMARY KEY,
        user_id INTEGER NULL,
        email VARCHAR(255) NOT NULL,
        otp_hash VARCHAR(64) NULL,
        registration_secret_hash VARCHAR(64) NOT NULL,
        email_proof_hash VARCHAR(64) NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        email_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
        used BOOLEAN NOT NULL DEFAULT FALSE,
        otp_attempts INTEGER NOT NULL DEFAULT 0
    )
    """
    with engine.begin() as conn:
        conn.execute(text(sql))


def _invalidate_existing(email: str, db: Session) -> None:
    db.execute(
        text(
            f"UPDATE {TABLE_NAME} SET used = TRUE "
            "WHERE lower(email) = :email AND used = FALSE"
        ),
        {"email": email},
    )


def _confirmation_url(email_proof_token: str) -> str:
    base = os.getenv(
        "PASSWORD_RESET_CONFIRM_BASE_URL",
        "https://retail-mind-vkbp.onrender.com/api/auth-hardened/password-reset/confirm-email",
    ).strip()
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{urlencode({'token': email_proof_token})}"


def attach_password_reset_security_routes(router) -> None:
    _ensure_table()

    @router.post("/password-reset/start")
    @rate_limit_endpoint(max_requests=5, window_seconds=60)
    def start_password_reset(
        request: StartResetRequest,
        http_request: Request,
        db: Session = Depends(get_db),
    ):
        email = request.email.strip().lower()
        _invalidate_existing(email, db)

        user = db.query(User).filter(User.email.ilike(email)).first()
        challenge_id = secrets.token_urlsafe(32)
        registration_secret = secrets.token_urlsafe(32)
        email_proof_token = secrets.token_urlsafe(48)
        now = _utcnow()
        expires = now + timedelta(seconds=CHALLENGE_TTL_SECONDS)

        db.execute(
            text(
                f"""
                INSERT INTO {TABLE_NAME} (
                    challenge_id, user_id, email, otp_hash,
                    registration_secret_hash, email_proof_hash,
                    created_at, expires_at, email_confirmed, used, otp_attempts
                ) VALUES (
                    :challenge_id, :user_id, :email, NULL,
                    :registration_secret_hash, :email_proof_hash,
                    :created_at, :expires_at, FALSE, FALSE, 0
                )
                """
            ),
            {
                "challenge_id": challenge_id,
                "user_id": user.id if user else None,
                "email": email,
                "registration_secret_hash": _sha256(registration_secret),
                "email_proof_hash": _sha256(email_proof_token),
                "created_at": now,
                "expires_at": expires,
            },
        )
        db.commit()

        logger.info(
            "Password-reset challenge created from %s",
            http_request.client.host if http_request.client else "unknown",
        )
        return {
            "success": True,
            "challenge_id": challenge_id,
            "registration_secret": registration_secret,
            "confirmation_url": _confirmation_url(email_proof_token),
            "expires_in": CHALLENGE_TTL_SECONDS,
        }

    @router.post("/password-reset/register-otp")
    @rate_limit_endpoint(max_requests=8, window_seconds=60)
    def register_frontend_otp(
        request: RegisterOtpRequest,
        db: Session = Depends(get_db),
    ):
        _ensure_table()
        if any(c not in "0123456789abcdefABCDEF" for c in request.otp_hash):
            raise HTTPException(status_code=400, detail="Invalid OTP proof")

        row = db.execute(
            text(
                f"SELECT registration_secret_hash, expires_at, used "
                f"FROM {TABLE_NAME} WHERE challenge_id = :challenge_id"
            ),
            {"challenge_id": request.challenge_id},
        ).mappings().first()

        if not row or row["used"]:
            raise HTTPException(status_code=400, detail="Reset challenge is invalid")
        if _utcnow() > row["expires_at"]:
            raise HTTPException(status_code=400, detail="Reset challenge expired")
        if not secrets.compare_digest(
            row["registration_secret_hash"], _sha256(request.registration_secret)
        ):
            raise HTTPException(status_code=401, detail="Invalid reset challenge")

        db.execute(
            text(
                f"UPDATE {TABLE_NAME} SET otp_hash = :otp_hash "
                "WHERE challenge_id = :challenge_id"
            ),
            {"otp_hash": request.otp_hash.lower(), "challenge_id": request.challenge_id},
        )
        db.commit()
        return {"success": True, "message": "OTP proof registered"}

    @router.get("/password-reset/confirm-email", response_class=HTMLResponse)
    def confirm_password_reset_email(token: str):
        _ensure_table()
        token_hash = _sha256(token.strip())
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    f"SELECT challenge_id, expires_at, used FROM {TABLE_NAME} "
                    "WHERE email_proof_hash = :proof_hash"
                ),
                {"proof_hash": token_hash},
            ).mappings().first()

            if not row or row["used"] or _utcnow() > row["expires_at"]:
                return HTMLResponse(
                    "<html><body style='font-family:Arial;padding:40px'>"
                    "<h2>Link expired</h2><p>Please request a new password reset code.</p>"
                    "</body></html>",
                    status_code=400,
                )

            conn.execute(
                text(
                    f"UPDATE {TABLE_NAME} SET email_confirmed = TRUE "
                    "WHERE challenge_id = :challenge_id"
                ),
                {"challenge_id": row["challenge_id"]},
            )

        return HTMLResponse(
            "<html><body style='font-family:Arial;background:#f5f7fb;padding:40px'>"
            "<div style='max-width:520px;margin:auto;background:white;padding:32px;border-radius:16px'>"
            "<h2 style='color:#10B981'>✅ Email confirmed</h2>"
            "<p>Your Retail Mind password-reset email has been verified.</p>"
            "<p>Return to the Retail Mind app and enter the OTP from this email.</p>"
            "<p style='color:#6B7280;font-size:13px'>You can close this page now.</p>"
            "</div></body></html>",
            status_code=200,
        )

    @router.post("/password-reset/authorize")
    @rate_limit_endpoint(max_requests=10, window_seconds=60)
    def authorize_password_reset(
        request: AuthorizeResetRequest,
        db: Session = Depends(get_db),
    ):
        _ensure_table()
        email = request.email.strip().lower()
        otp = request.otp.strip()
        if not otp.isdigit() or len(otp) != 6:
            raise HTTPException(status_code=400, detail="OTP must be 6 digits")

        row = db.execute(
            text(
                f"SELECT user_id, email, otp_hash, expires_at, email_confirmed, "
                f"used, otp_attempts FROM {TABLE_NAME} "
                "WHERE challenge_id = :challenge_id"
            ),
            {"challenge_id": request.challenge_id},
        ).mappings().first()

        if not row or row["used"]:
            raise HTTPException(status_code=400, detail="Reset challenge is invalid")
        if _utcnow() > row["expires_at"]:
            raise HTTPException(status_code=400, detail="Reset challenge expired")
        if row["email"].lower() != email:
            raise HTTPException(status_code=403, detail="Reset challenge does not match this email")
        if not row["email_confirmed"]:
            raise HTTPException(
                status_code=409,
                detail="Open the confirmation link sent to your email first, then verify the OTP again.",
            )
        if not row["otp_hash"]:
            raise HTTPException(status_code=400, detail="OTP is not registered")
        if int(row["otp_attempts"] or 0) >= MAX_OTP_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many OTP attempts. Request a new reset code.")

        request_hash = _sha256(otp)
        if not secrets.compare_digest(row["otp_hash"], request_hash):
            db.execute(
                text(
                    f"UPDATE {TABLE_NAME} SET otp_attempts = otp_attempts + 1 "
                    "WHERE challenge_id = :challenge_id"
                ),
                {"challenge_id": request.challenge_id},
            )
            db.commit()
            raise HTTPException(status_code=400, detail="Invalid OTP")

        user = db.query(User).filter(User.email.ilike(email)).first()
        if not user or row["user_id"] is None or int(row["user_id"]) != int(user.id):
            raise HTTPException(status_code=400, detail="Unable to authorize password reset")

        reset_token = secrets.token_urlsafe(32)
        reset_token_hash = _sha256(reset_token)
        expires_at = _utcnow() + timedelta(seconds=RESET_TOKEN_TTL_SECONDS)

        db.query(PasswordReset).filter(PasswordReset.user_id == user.id).delete(synchronize_session=False)
        db.add(
            PasswordReset(
                user_id=user.id,
                token_hash=reset_token_hash,
                expires_at=expires_at,
            )
        )
        db.execute(
            text(
                f"UPDATE {TABLE_NAME} SET used = TRUE "
                "WHERE challenge_id = :challenge_id"
            ),
            {"challenge_id": request.challenge_id},
        )
        db.commit()

        logger.info("Password-reset authorization issued for user_id=%s", user.id)
        return {
            "success": True,
            "reset_token": reset_token,
            "expires_in": RESET_TOKEN_TTL_SECONDS,
        }

    @router.get("/password-reset/status")
    def password_reset_status(challenge_id: str, db: Session = Depends(get_db)):
        _ensure_table()
        row = db.execute(
            text(
                f"SELECT expires_at, email_confirmed, used, otp_hash, otp_attempts "
                f"FROM {TABLE_NAME} WHERE challenge_id = :challenge_id"
            ),
            {"challenge_id": challenge_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Reset challenge not found")
        return {
            "email_confirmed": bool(row["email_confirmed"]),
            "otp_registered": bool(row["otp_hash"]),
            "used": bool(row["used"]),
            "expired": _utcnow() > row["expires_at"],
            "remaining_attempts": max(0, MAX_OTP_ATTEMPTS - int(row["otp_attempts"] or 0)),
        }
