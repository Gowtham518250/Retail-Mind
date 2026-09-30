import os
from urllib.parse import parse_qs, urlparse

os.environ["DATABASE_URL"] = "sqlite:///./customer_password_reset_test.db"
os.environ["FRONTEND_URL"] = "https://shop.example.com"
os.environ["SECRET_KEY"] = "test-secret-key"
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


def test_customer_password_reset_end_to_end(monkeypatch):
    db = sessionLocal()
    db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.email == "reset-test@example.com"
    ).delete()
    db.commit()

    customer = OnlineCustomerAuth(
        user_name="Reset Test",
        email="reset-test@example.com",
        phone="9876543210",
        password=hash_password("OldPassword123!"),
        is_active=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    customer_id = customer.id
    db.close()

    sent = {}

    def fake_send_email(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(EmailNotificationService, "send_email", fake_send_email)

    response = client.post(
        "/store/customer/forgot-password",
        json={
            "email": "reset-test@example.com",
            "shop_id": 7,
        },
    )
    assert response.status_code == 200
    assert "reset link" in response.json()["message"].lower()
    assert "reset-test@example.com" in sent["recipient_email"]

    reset_link = sent["body"].split("Reset your password here:\n", 1)[1].split("\n", 1)[0]
    params = parse_qs(urlparse(reset_link).query)
    token = params["resetToken"][0]
    assert params["shop_id"][0] == "7"

    reset_response = client.post(
        "/store/customer/reset-password",
        json={
            "token": token,
            "new_password": "NewPassword123!",
        },
    )
    assert reset_response.status_code == 200
    assert "successfully" in reset_response.json()["message"].lower()

    db = sessionLocal()
    customer = db.query(OnlineCustomerAuth).filter(
        OnlineCustomerAuth.id == customer_id
    ).first()
    assert customer is not None
    assert verify_password("NewPassword123!", customer.password)
    assert not verify_password("OldPassword123!", customer.password)
    db.close()

    reuse_response = client.post(
        "/store/customer/reset-password",
        json={
            "token": token,
            "new_password": "AnotherPassword123!",
        },
    )
    assert reuse_response.status_code == 400
    assert "invalid or expired" in reuse_response.json()["detail"].lower()
