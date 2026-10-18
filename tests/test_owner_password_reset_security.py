"""Regression tests for owner password-reset security boundaries."""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/retail_mind_test",
)
os.environ.setdefault("SECRET_KEY", "owner-reset-test-secret-key-1234567890")
os.environ.setdefault("FRONTEND_URL", "https://shop.example.com")
os.environ.setdefault("SENDER_EMAIL", "test@example.com")
os.environ.setdefault("SENDER_PASSWORD", "test-password")

from fastapi.testclient import TestClient
from starlette.requests import Request

from app import api
from rate_limiter import rate_limit_endpoint


// Use an explicitly allowlisted Host. FastAPI's TestClient default `testserver`
// is intentionally rejected by TrustedHostMiddleware and returns HTTP 400.
client = TestClient(api, base_url="http://localhost")


def test_legacy_owner_reset_request_cannot_disclose_a_token_or_email_existence():
    known = client.post(
        "/auth/request-password-reset",
        json={"email": "registered-owner@example.com"},
    )
    unknown = client.post(
        "/auth/request-password-reset",
        json={"email": "not-registered-owner@example.com"},
    )

    assert known.status_code == 410
    assert unknown.status_code == 410
    assert known.json() == unknown.json()
    assert "token" not in known.json()


def test_legacy_owner_reset_endpoint_never_changes_password_from_caller_token():
    response = client.post(
        "/auth/reset-password",
        json={"token": "attacker-chosen-token", "password": "ChangedByAttacker123!"},
    )

    assert response.status_code == 410
    assert "disabled" in response.json()["detail"].lower()


def test_every_experimental_hardened_password_reset_route_is_disabled():
    responses = [
        client.post(
            "/api/auth-hardened/password-reset/start",
            json={"email": "owner@example.com"},
        ),
        client.post(
            "/api/auth-hardened/password-reset/register-otp",
            json={
                "challenge_id": "c" * 32,
                "registration_secret": "s" * 32,
                "otp_hash": "a" * 64,
            },
        ),
        client.get(
            "/api/auth-hardened/password-reset/confirm-email",
            params={"token": "email-proof-token"},
        ),
        client.post(
            "/api/auth-hardened/password-reset/authorize",
            json={
                "challenge_id": "c" * 32,
                "email": "owner@example.com",
                "otp": "123456",
            },
        ),
        client.get(
            "/api/auth-hardened/password-reset/status",
            params={"challenge_id": "c" * 32},
        ),
    ]

    assert [response.status_code for response in responses] == [410] * 5


def test_rate_limiter_finds_starlette_request_by_type_not_body_parameter_name():
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/unit-test-rate-limit-extractor",
        "raw_path": b"/unit-test-rate-limit-extractor",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    http_request = Request(scope)

    @rate_limit_endpoint(max_requests=1, window_seconds=60)
    def endpoint(request, http_request: Request):
        # "request" deliberately represents the parsed request body, not the
        # Starlette Request. This matches the hardened endpoints' old signature.
        return {"ok": True}

    response = endpoint(request={"email": "owner@example.com"}, http_request=http_request)
    assert response == {"ok": True}

def test_owner_otp_request_response_is_generic_for_known_and_unknown_emails(monkeypatch):
    import uuid

    from db import sessionLocal
    from email_notifications import EmailNotificationService
    from models import PasswordReset, User
    from security import hash_password

    email = f"owner-reset-{uuid.uuid4().hex}@example.com"
    db = sessionLocal()
    user = User(
        user_name="Owner reset test",
        email=email,
        password=hash_password("OriginalPassword123!"),
        user_type="OWNER",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()

    sent_messages = []

    def fake_send_email(**kwargs):
        sent_messages.append(kwargs)
        return True

    monkeypatch.setattr(EmailNotificationService, "send_email", fake_send_email)

    try:
        registered = client.post(
            "/auth/request-password-reset-otp",
            json={"email": email},
        )
        unknown = client.post(
            "/auth/request-password-reset-otp",
            json={"email": f"missing-{uuid.uuid4().hex}@example.com"},
        )

        assert registered.status_code == unknown.status_code == 200
        assert registered.json() == unknown.json() == {
            "msg": "If the email exists, a password-reset OTP has been sent"
        }
        assert "token" not in registered.json()
        assert len(sent_messages) == 1
        assert sent_messages[0]["recipient_email"] == email
    finally:
        cleanup = sessionLocal()
        cleanup.query(PasswordReset).filter(
            PasswordReset.user_id == user_id
        ).delete(synchronize_session=False)
        cleanup.query(User).filter(User.id == user_id).delete(
            synchronize_session=False
        )
        cleanup.commit()
        cleanup.close()
