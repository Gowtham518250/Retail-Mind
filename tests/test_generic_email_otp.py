import os
import re
import uuid

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/retail_mind_test",
)
os.environ.setdefault(
    "SECRET_KEY",
    "generic-email-otp-test-secret-key-123456789012",
)
os.environ.setdefault("SENDER_EMAIL", "test@example.com")
os.environ.setdefault("SENDER_PASSWORD", "test-password")

from fastapi.testclient import TestClient

from app import api
from db import Base, engine, sessionLocal
from email_notifications import EmailNotificationService
from models import EmailOtpChallenge

Base.metadata.create_all(bind=engine)
client = TestClient(api)


def _sent_otp(body: str) -> str:
    match = re.search(r"(?<!\d)\d{6}(?!\d)", body)
    assert match is not None, "Expected a six-digit OTP in the fake email body"
    return match.group(0)


def _send_otp(monkeypatch, email: str) -> tuple[str, dict]:
    sent = {}

    def fake_send_email(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(EmailNotificationService, "send_email", fake_send_email)
    response = client.post(
        "/auth/send-otp",
        json={"email": email, "purpose": "Verification"},
    )
    assert response.status_code == 200, response.text
    return _sent_otp(sent["body"]), sent


def test_generic_email_otp_is_database_backed_single_use(monkeypatch):
    email = f"generic-otp-{uuid.uuid4().hex}@example.com"
    otp, _ = _send_otp(monkeypatch, email)

    db = sessionLocal()
    try:
        challenge = (
            db.query(EmailOtpChallenge)
            .filter(EmailOtpChallenge.email == email)
            .order_by(EmailOtpChallenge.id.desc())
            .first()
        )
        assert challenge is not None
        assert challenge.otp_hash != otp
        assert challenge.attempts == 0
        assert challenge.used_at is None
    finally:
        db.close()

    verified = client.post(
        "/auth/verify-otp",
        json={"email": email, "otp": otp},
    )
    assert verified.status_code == 200, verified.text

    db = sessionLocal()
    try:
        challenge = (
            db.query(EmailOtpChallenge)
            .filter(EmailOtpChallenge.email == email)
            .order_by(EmailOtpChallenge.id.desc())
            .first()
        )
        assert challenge is not None
        assert challenge.used_at is not None
    finally:
        db.query(EmailOtpChallenge).filter(
            EmailOtpChallenge.email == email
        ).delete(synchronize_session=False)
        db.commit()
        db.close()

    reused = client.post(
        "/auth/verify-otp",
        json={"email": email, "otp": otp},
    )
    assert reused.status_code == 400


def test_generic_email_otp_invalid_attempts_are_bounded(monkeypatch):
    email = f"generic-otp-attempts-{uuid.uuid4().hex}@example.com"
    otp, _ = _send_otp(monkeypatch, email)
    wrong_otp = "000000" if otp != "000000" else "999999"

    for _ in range(5):
        response = client.post(
            "/auth/verify-otp",
            json={"email": email, "otp": wrong_otp},
        )
        assert response.status_code == 400

    db = sessionLocal()
    try:
        challenge = (
            db.query(EmailOtpChallenge)
            .filter(EmailOtpChallenge.email == email)
            .order_by(EmailOtpChallenge.id.desc())
            .first()
        )
        assert challenge is not None
        assert challenge.attempts == 5
        assert challenge.used_at is not None
    finally:
        db.query(EmailOtpChallenge).filter(
            EmailOtpChallenge.email == email
        ).delete(synchronize_session=False)
        db.commit()
        db.close()

    correct_after_lockout = client.post(
        "/auth/verify-otp",
        json={"email": email, "otp": otp},
    )
    assert correct_after_lockout.status_code == 400
