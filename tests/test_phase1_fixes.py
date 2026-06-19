"""
Phase 1 critical bug-fix regression tests.

Covers:
  - Registration email uniqueness (case-insensitive, clear 409)
  - Role-based login (customer is NOT given OWNER role)
  - Offline invoice sync does not crash when creating a new customer
  - Invoice creation is idempotent (no duplicate invoices)
"""

import os
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import api
from db import get_db
from models import Base, User, Product

TEST_DATABASE_URL = "sqlite:///./test_phase1.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


api.dependency_overrides[get_db] = override_get_db
client = TestClient(api)


def _unique_email():
    return f"user_{uuid.uuid4().hex[:10]}@example.com"


def test_first_registration_succeeds():
    email = _unique_email()
    r = client.post("/auth/register", json={"username": "Owner A", "password": "Passw0rd!", "email": email})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "OWNER"
    assert "user_id" in body


def test_duplicate_email_is_case_insensitive_and_clear():
    email = _unique_email()
    r1 = client.post("/auth/register", json={"username": "Owner B", "password": "Passw0rd!", "email": email})
    assert r1.status_code == 200, r1.text

    # Same email different case must be rejected with a clear 409.
    r2 = client.post("/auth/register", json={"username": "Owner B2", "password": "Passw0rd!", "email": email.upper()})
    assert r2.status_code == 409
    assert "already has an account" in r2.json()["detail"].lower()


def test_customer_login_is_not_owner_role():
    """A customer account must log in as CUSTOMER, not OWNER (routing bug)."""
    email = _unique_email()
    reg = client.post(
        "/store/customer/register",
        json={"name": "Cust One", "email": email, "phone": "9876543210", "password": "secret1"},
    )
    assert reg.status_code == 200, reg.text
    assert reg.json()["role"] == "CUSTOMER"

    # Logging in through the generic /auth/login must still resolve CUSTOMER role
    login = client.post("/auth/login", json={"email": email.upper(), "password": "secret1"})
    assert login.status_code == 200, login.text
    assert login.json()["role"] == "CUSTOMER"


def _owner_token(email):
    client.post("/auth/register", json={"username": "ShopO", "password": "Passw0rd!", "email": email})
    login = client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    return login.json()["access_token"], login.json()["user_id"]


def test_offline_sync_creates_new_customer_without_crash():
    token, _ = _owner_token(_unique_email())
    payload = {
        "invoice_number": f"INV-{uuid.uuid4().hex[:8]}",
        "customer_phone": "9123456780",
        "customer_name": "Walk In",
        "total_amount": 100.0,
        "paid_amount": 100.0,
        "payment_status": "PAID",
        "invoice_date": "2026-06-19",
        "line_items": [{"product_name": "Milk", "quantity": 2, "unit_price": 50.0}],
    }
    r = client.post("/api/invoices/sync", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert "invoice_id" in r.json()


def test_invoice_create_is_idempotent():
    token, _ = _owner_token(_unique_email())
    inv_no = f"INV-{uuid.uuid4().hex[:8]}"
    payload = {
        "invoice_number": inv_no,
        "total_amount": 60.0,
        "paid_amount": 60.0,
        "payment_status": "PAID",
        "invoice_date": "2026-06-19",
        "line_items": [{"product_name": "Bread", "quantity": 1, "unit_price": 60.0}],
    }
    headers = {"Authorization": f"Bearer {token}"}
    r1 = client.post("/api/invoices/create", json=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    first_id = r1.json()["invoice_id"]

    # Double-tap / retry must return the same invoice, not create a new one.
    r2 = client.post("/api/invoices/create", json=payload, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["invoice_id"] == first_id
    assert r2.json().get("duplicate") is True
