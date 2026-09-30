import os

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/retail_mind_test")
os.environ["SECRET_KEY"] = "customer-otp-reset-test-secret-key-1234567890"
os.environ["SENDER_EMAIL"] = "test@example.com"
os.environ["SENDER_PASSWORD"] = "test-password"

from fastapi.testclient import TestClient

from app import api
from db import Base, engine, sessionLocal
from email_notifications import EmailNotificationService
from models import OnlineCustomerAuth
from security import hash_password, verify_password

Base.metadata.create_all(bind=engine)
client = TestClient(api)


def test_customer_otp_reset_end_to_end(monkeypatch):
    db = sessionLocal()
    db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.email == "customer-otp-reset@example.com"
    ).delete()
    db.commit()

    customer = OnlineCustomerAuth(
        user_name="OTP Reset Test",
        email="customer-otp-reset@example.com",
        phone="9876543211",
        password=hash_password("OldPassword123!"),
        is_active=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    db.close()

    sent = {}

    def fake_send_email(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(EmailNotificationService, "send_email", fake_send_email)

    request_response = client.post(
        "/store/customer/request-password-reset-otp",
        json={"email": "customer-otp-reset@example.com"},
    )
    assert request_response.status_code == 200
    assert "otp" in request_response.json()["message"].lower()

    body = sent["body"]
    otp = body.split("\n\n", 1)[1].split("\n", 1)[0].strip()
    assert len(otp) == 6 and otp.isdigit()

    verify_response = client.post(
        "/store/customer/verify-password-reset-otp",
        json={
            "email": "customer-otp-reset@example.com",
            "otp": otp,
        },
    )
    assert verify_response.status_code == 200
    reset_token = verify_response.json()["reset_token"]

    reset_response = client.post(
        "/store/customer/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": "NewPassword123!",
        },
    )
    assert reset_response.status_code == 200

    db = sessionLocal()
    customer = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.email == "customer-otp-reset@example.com"
    ).first()
    assert customer is not None
    assert verify_password("NewPassword123!", customer.password)
    assert not verify_password("OldPassword123!", customer.password)
    db.close()

    reuse_response = client.post(
        "/store/customer/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": "AnotherPassword123!",
        },
    )
    assert reuse_response.status_code == 400
