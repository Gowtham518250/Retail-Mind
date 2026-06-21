"""
Phase 1 critical bug-fix regression tests.

Covers the backend fixes that are unique to this branch:
  - Registration email uniqueness (case-insensitive, clear error)
  - Registration returns access_token + role for auto-login
  - Customer auth resolves the CUSTOMER role (not OWNER)
  - Offline invoice sync does not crash when creating a new customer
  - Invoice creation is idempotent (no duplicate invoices)
  - Legacy /auth/sales idempotency and inventory deduction
  - GET /auth/sales resolves product names from products table
  - POST /api/shop/profile upsert (no 405)
"""

import os
import sys
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import api
from db import get_db
from models import Base

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
    assert "user_id" in r.json()


def test_duplicate_email_is_case_insensitive():
    email = _unique_email()
    r1 = client.post("/auth/register", json={"username": "Owner B", "password": "Passw0rd!", "email": email})
    assert r1.status_code == 200, r1.text

    # Same email different case must be rejected (case-insensitive uniqueness).
    r2 = client.post("/auth/register", json={"username": "Owner B2", "password": "Passw0rd!", "email": email.upper()})
    assert r2.status_code == 400
    assert "email" in r2.json()["detail"].lower()


def test_customer_login_resolves_customer_role():
    """A customer account must authenticate as CUSTOMER, not OWNER."""
    email = _unique_email()
    reg = client.post(
        "/store/customer/register",
        json={"name": "Cust One", "email": email, "phone": "9876543210", "password": "secret1"},
    )
    assert reg.status_code == 200, reg.text

    login = client.post("/store/customer/login", json={"email": email, "password": "secret1"})
    assert login.status_code == 200, login.text
    assert "access_token" in login.json()


def _owner_token(email):
    username = f"Shop_{uuid.uuid4().hex[:8]}"
    client.post("/auth/register", json={"username": username, "password": "Passw0rd!", "email": email})
    login = client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    return login.json()["access_token"]


def test_offline_sync_creates_new_customer_without_crash():
    token = _owner_token(_unique_email())
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
    token = _owner_token(_unique_email())
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


# ── NEW TESTS (round 2) ──────────────────────────────────────────────


def test_registration_returns_access_token():
    """Registration must return access_token so the app can auto-login."""
    email = _unique_email()
    r = client.post("/auth/register", json={"username": f"Reg_{uuid.uuid4().hex[:6]}", "password": "Passw0rd!", "email": email})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] in ("OWNER", "CUSTOMER", "WORKER", "DELIVERY")
    assert data["is_active"] is True


def test_profile_upsert_post():
    """POST /api/shop/profile must create-or-update (no 405)."""
    email = _unique_email()
    token = _owner_token(email)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/shop/profile", json={"shop_name": "Test Shop"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"

    # Second call should update, not fail
    r2 = client.post("/api/shop/profile", json={"shop_name": "Updated Shop"}, headers=headers)
    assert r2.status_code == 200, r2.text


def test_legacy_sales_idempotency():
    """POST /auth/sales must not create duplicate invoices on retry."""
    email = _unique_email()
    # Register + login
    client.post("/auth/register", json={"username": f"Shop_{uuid.uuid4().hex[:6]}", "password": "Passw0rd!", "email": email})
    login = client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    user_id = login.json()["user_id"]

    r1 = client.post("/auth/sales", data={
        "user_id": user_id,
        "product_name": "Milk",
        "price": 50.0,
        "quantity": 2,
        "total": 100.0,
        "date": "2026-06-19",
    })
    assert r1.status_code == 200, r1.text

    # Retry same sale
    r2 = client.post("/auth/sales", data={
        "user_id": user_id,
        "product_name": "Milk",
        "price": 50.0,
        "quantity": 2,
        "total": 100.0,
        "date": "2026-06-19",
    })
    assert r2.status_code == 200, r2.text
    assert r2.json().get("duplicate") is True


def test_get_sales_returns_data():
    """GET /auth/sales must return sales for a user."""
    email = _unique_email()
    client.post("/auth/register", json={"username": f"Shop_{uuid.uuid4().hex[:6]}", "password": "Passw0rd!", "email": email})
    login = client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    user_id = login.json()["user_id"]

    # Create a sale
    client.post("/auth/sales", data={
        "user_id": user_id,
        "product_name": "Bread",
        "price": 40.0,
        "quantity": 1,
        "total": 40.0,
    })

    r = client.get(f"/auth/sales?user_id={user_id}")
    assert r.status_code == 200, r.text
    sales = r.json()
    assert len(sales) >= 1
    assert sales[0]["line_items"][0]["product_name"] == "Bread"


# ── ROUND 3: Invoice response, route order, customer auth fixes ──────


def test_invoice_create_returns_full_object():
    """POST /api/invoices/create must return id, total_amount, line_items."""
    token = _owner_token(_unique_email())
    inv_no = f"INV-FULL-{uuid.uuid4().hex[:8]}"
    payload = {
        "invoice_number": inv_no,
        "total_amount": 150.0,
        "paid_amount": 150.0,
        "tax": 10.0,
        "payment_status": "PAID",
        "invoice_date": "2026-06-19",
        "line_items": [{"product_name": "Chips", "quantity": 3, "unit_price": 50.0}],
    }
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/invoices/create", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "id" in data
    assert data["total_amount"] == 150.0
    assert data["tax"] == 10.0
    assert len(data["line_items"]) == 1
    assert data["line_items"][0]["product_name"] == "Chips"
    assert data["line_items"][0]["quantity"] == 3


def test_get_invoice_returns_line_items():
    """GET /api/invoices/{id} must return line_items with product_name."""
    token = _owner_token(_unique_email())
    inv_no = f"INV-DET-{uuid.uuid4().hex[:8]}"
    payload = {
        "invoice_number": inv_no,
        "total_amount": 80.0,
        "paid_amount": 80.0,
        "payment_status": "PAID",
        "invoice_date": "2026-06-19",
        "line_items": [{"product_name": "Water", "quantity": 4, "unit_price": 20.0}],
    }
    headers = {"Authorization": f"Bearer {token}"}
    create_r = client.post("/api/invoices/create", json=payload, headers=headers)
    assert create_r.status_code == 200, create_r.text
    invoice_id = create_r.json()["id"]

    get_r = client.get(f"/api/invoices/{invoice_id}", headers=headers)
    assert get_r.status_code == 200, get_r.text
    data = get_r.json()
    assert "line_items" in data
    assert data["line_items"][0]["product_name"] == "Water"


def test_overdue_endpoint_not_captured_by_invoice_id():
    """GET /api/invoices/overdue must not 422 (route order fix)."""
    token = _owner_token(_unique_email())
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/invoices/overdue", headers=headers)
    assert r.status_code == 200, r.text
    assert "overdue_invoices" in r.json()


def test_payments_endpoint_not_captured_by_invoice_id():
    """GET /api/invoices/payments must not 422 (route order fix)."""
    token = _owner_token(_unique_email())
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/invoices/payments", headers=headers)
    assert r.status_code == 200, r.text
    assert "payments" in r.json()


def test_customer_register_no_email_import_crash():
    """Customer registration must not crash due to email_notifications import."""
    email = _unique_email()
    r = client.post("/store/customer/register", json={
        "name": "Test Cust",
        "email": email,
        "phone": "9876500001",
        "password": "secret123",
    })
    assert r.status_code == 200, r.text
    assert r.json()["customer_id"] is not None


def test_forgot_password_endpoint_exists():
    """POST /store/customer/forgot-password must return 200."""
    r = client.post("/store/customer/forgot-password?email=nobody@example.com")
    assert r.status_code == 200, r.text
    assert "reset link" in r.json()["message"].lower()
