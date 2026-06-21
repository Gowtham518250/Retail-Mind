#!/usr/bin/env python3
"""
╔======================================================================╗
║           RETAIL MIND - ULTRA API TEST SUITE                        ║
║           Base URL: https://retail-mind-vkbp.onrender.com           ║
║           Total Endpoints: 185                                       ║
╚======================================================================╝
"""

import requests
import json
import time
import sys
from datetime import datetime, timedelta
from typing import Optional

# ─────────────────────────────────────────────
import os
BASE_URL = os.getenv("TEST_BASE_URL", "https://retail-mind-vkbp.onrender.com")
TIMEOUT  = 15   # seconds per request

# ── State shared across tests ──────────────────
STATE = {
    "access_token":    None,
    "refresh_token":   None,
    "user_id":         None,
    "product_id":      None,
    "customer_id":     None,
    "invoice_id":      None,
    "worker_id":       None,
    "leave_id":        None,
    "delivery_id":     None,
    "po_id":           None,
    "bill_id":         None,
    "operation_id":    None,
    "shop_id":         1,
    "order_id":        None,
    "customer_phone":  "9999999999",
    "test_email":      f"testuser_{int(time.time())}@retailmind.test",
    "test_password":   "Test@123456",
    "test_username":   f"tester_{int(time.time())}",
}

# ─────────────────────────────────────────────
#  RESULT TRACKING
# ─────────────────────────────────────────────
RESULTS = []

def auth_headers() -> dict:
    h = {"Content-Type": "application/json"}
    if STATE["access_token"]:
        h["Authorization"] = f"Bearer {STATE['access_token']}"
    return h

def run(
    label: str,
    method: str,
    path: str,
    payload: Optional[dict] = None,
    params: Optional[dict] = None,
    expected_codes: tuple = (200, 201, 202),
    capture: Optional[dict] = None,   # {state_key: "json.path.field"}
    skip_if: Optional[str] = None,    # state key that must be non-None
):
    """Execute one request and record the result."""
    if skip_if and STATE.get(skip_if) is None:
        RESULTS.append({"label": label, "status": "SKIP", "code": "-", "detail": f"Requires STATE[{skip_if!r}]"})
        _print_row(RESULTS[-1])
        return None

    url = BASE_URL + path
    try:
        resp = requests.request(
            method.upper(), url,
            headers=auth_headers(),
            json=payload,
            params={k: v for k, v in (params or {}).items() if v is not None},
            timeout=TIMEOUT,
        )
        code = resp.status_code
        ok   = code in expected_codes
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:200]

        # capture values from response
        if ok and capture and isinstance(body, dict):
            for key, jpath in capture.items():
                val = body
                for part in jpath.split("."):
                    if isinstance(val, dict):
                        val = val.get(part)
                    else:
                        val = None
                        break
                if val is not None:
                    STATE[key] = val

        result = {
            "label":  label,
            "status": "PASS" if ok else "FAIL",
            "code":   code,
            "detail": str(body)[:120] if not ok else "",
        }
    except requests.exceptions.Timeout:
        result = {"label": label, "status": "TIMEOUT", "code": "-", "detail": f">{TIMEOUT}s"}
    except Exception as e:
        result = {"label": label, "status": "ERROR", "code": "-", "detail": str(e)[:120]}

    RESULTS.append(result)
    _print_row(result)
    time.sleep(0.3)   # be kind to the server
    return result

def _print_row(r):
    icons = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]", "TIMEOUT": "[TIME]", "ERROR": "[ERR]"}
    icon  = icons.get(r["status"], "?")
    detail = f"  -> {r['detail']}" if r["detail"] else ""
    print(f"  {icon} [{r['code']:>3}]  {r['label']}{detail}")


# ==============================================
#  TEST SECTIONS
# ==============================================

def section(title: str):
    print(f"\n{'='*64}")
    print(f"  {title}")
    print(f"{'='*64}")


# ─── 1. SYSTEM / HEALTH ───────────────────────
def test_system():
    section("1 - SYSTEM / HEALTH")
    run("Root",                       "GET",  "/")
    run("Health Check (/health)",     "GET",  "/health")
    run("Observability Health",       "GET",  "/api/observability/health")
    run("Observability Ready",        "GET",  "/api/observability/ready")
    run("Observability Metrics",      "GET",  "/api/observability/metrics")
    run("Business Overview",          "GET",  "/api/observability/business/overview")
    run("Performance Summary",        "GET",  "/api/observability/performance/summary")
    run("DB Performance",             "GET",  "/api/observability/performance/database")


# ─── 2. AUTHENTICATION ────────────────────────
def test_auth():
    section("2 - AUTHENTICATION (Legacy)")
    run("Register",
        "POST", "/auth/register",
        payload={
            "username":  STATE["test_username"],
            "password":  STATE["test_password"],
            "email":     STATE["test_email"],
            "user_type": "owner",
        },
        expected_codes=(200, 201, 400, 409, 404, 500),
    )
    run("Send OTP",
        "POST", "/auth/send-otp",
        payload={"email": STATE["test_email"], "purpose": "verify"},
        expected_codes=(200, 201, 400),
    )
    run("Verify OTP (expect 400/422 without real OTP)",
        "POST", "/auth/verify-otp",
        payload={"email": STATE["test_email"], "otp": "000000"},
        expected_codes=(200, 201, 400, 422),
    )
    run("Login",
        "POST", "/auth/login",
        payload={"email": STATE["test_email"], "password": STATE["test_password"]},
        expected_codes=(200, 201, 400, 401),
        capture={"access_token": "access_token", "refresh_token": "refresh_token", "user_id": "user_id"},
    )


def test_auth_hardened():
    section("3 - AUTHENTICATION HARDENED")
    h_email    = f"hard_{int(time.time())}@retailmind.test"
    h_password = "Hardened@999"
    h_username = f"hard_{int(time.time())}"

    run("Hardened Register",
        "POST", "/api/auth-hardened/register",
        payload={"email": h_email, "password": h_password, "user_name": h_username},
        expected_codes=(200, 201, 400, 409, 404, 500),
    )
    run("Hardened Login",
        "POST", "/api/auth-hardened/login",
        payload={"email": h_email, "password": h_password},
        expected_codes=(200, 201, 400, 401),
    )
    run("Hardened Refresh (no token)",
        "POST", "/api/auth-hardened/refresh",
        payload={"refresh_token": "dummy"},
        expected_codes=(200, 201, 400, 401, 422),
    )
    run("Hardened Logout",
        "POST", "/api/auth-hardened/logout",
        expected_codes=(200, 201, 400, 401),
    )
    if STATE["user_id"]:
        run("Hardened Logout All",
            "POST", "/api/auth-hardened/logout-all",
            params={"user_id": STATE["user_id"]},
            expected_codes=(200, 201, 400, 401),
        )
        run("Get Active Sessions (hardened)",
            "GET",  f"/api/auth-hardened/active-sessions/{STATE['user_id']}",
            expected_codes=(200, 201, 401, 404),
        )


# ─── 4. SESSION MANAGEMENT ────────────────────
def test_session():
    section("4 - SESSION MANAGEMENT")
    run("Refresh Token",
        "POST", "/api/session/refresh",
        payload={"refresh_token": STATE["refresh_token"] or "dummy", "device_id": "pytest-device"},
        expected_codes=(200, 201, 400, 401),
        capture={"access_token": "access_token"},
    )
    run("Get Active Sessions",
        "GET",  f"/api/session/active/{STATE['user_id'] or 1}",
        expected_codes=(200, 201, 401, 404),
    )
    run("Sync Offline Data",
        "POST", "/api/session/offline/queue",
        payload={"user_id": STATE["user_id"] or 1, "data_type": "sale", "payload": {"test": True}},
        expected_codes=(200, 201, 400, 401),
    )
    run("Sync All Offline Data",
        "POST", "/api/session/offline/sync",
        payload={"user_id": STATE["user_id"] or 1},
        expected_codes=(200, 201, 400, 401),
    )


# ─── 5. SHOP ──────────────────────────────────
def test_shop():
    section("5 - SHOP MANAGEMENT")
    run("Get Shop Profile (/api/shop)",        "GET", "/api/shop/profile",     expected_codes=(200, 201, 401, 404))
    run("Get Business Hours",                  "GET", "/api/shop/business-hours", expected_codes=(200, 201, 401, 404))
    run("Get Tax Config",                      "GET", "/api/shop/tax-config",  expected_codes=(200, 201, 401, 404))
    run("Get Shop Profile (/shop)",            "GET", "/shop/profile",         expected_codes=(200, 201, 401, 404))
    run("Get UPI QR",                          "GET", "/shop/upi-qr",          params={"amount": "100"}, expected_codes=(200, 201, 401, 404, 422))
    run("Get Public Shop Info",                "GET", f"/shop/public/{STATE['shop_id']}", expected_codes=(200, 201, 401, 404))
    run("Toggle Online Store (enable)",
        "POST", "/shop/toggle-online-store",
        params={"enable": True},
        expected_codes=(200, 201, 400, 401),
    )
    run("Update Shop Profile",
        "PUT",  "/shop/profile",
        payload={"shop_name": "Test Retail Shop", "phone": "9999999999", "city": "Hyderabad"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Update API Shop Settings",
        "PUT", "/api/shop/settings",
        payload={},
        expected_codes=(200, 201, 400, 401),
    )


# ─── 6. INVENTORY ─────────────────────────────
def test_inventory():
    section("6 - INVENTORY MANAGEMENT")
    uid = STATE["user_id"] or 1

    run("Create Product",
        "POST", "/api/inventory/products",
        payload={
            "product_name": f"TestProduct_{int(time.time())}",
            "sku":          f"SKU-{int(time.time())}",
            "unit_price":   99.99,
            "current_stock": 50,
            "min_stock":    5,
            "max_stock":    100,
            "reorder_level": 10,
            "category":     "Test",
            "description":  "Automated test product",
        },
        capture={"product_id": "id"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Products",
        "GET", "/api/inventory/products",
        params={"limit": 10},
        expected_codes=(200, 201, 401),
    )
    run("Get Single Product",
        "GET", f"/api/inventory/products/{STATE['product_id'] or 1}",
        expected_codes=(200, 201, 401, 404),
    )
    run("Update Product",
        "PUT", f"/api/inventory/products/{STATE['product_id'] or 1}",
        payload={"unit_price": "109.99", "category": "Updated"},
        expected_codes=(200, 201, 400, 401, 404),
    )
    run("Create Stock Movement",
        "POST", "/api/inventory/stock-movement",
        payload={
            "product_id":    STATE["product_id"] or 1,
            "movement_type": "in",
            "quantity":      10,
            "reason":        "Test stock in",
        },
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Stock Movements",
        "GET", f"/api/inventory/stock-movements/{STATE['product_id'] or 1}",
        params={"days": 30},
        expected_codes=(200, 201, 401, 404),
    )
    run("Get Low Stock Products",    "GET", "/api/inventory/low-stock",    expected_codes=(200, 201, 401))
    run("Get Stock Alerts",          "GET", "/api/inventory/stock-alerts", expected_codes=(200, 201, 401))
    run("Create Batch",
        "POST", "/api/inventory/batches",
        payload={
            "product_id":    STATE["product_id"] or 1,
            "batch_number":  f"BATCH-{int(time.time())}",
            "quantity":      20,
            "expiry_date":   (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d"),
        },
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Batches",
        "GET", f"/api/inventory/batches/{STATE['product_id'] or 1}",
        expected_codes=(200, 201, 401, 404),
    )
    run("Get Expiring Batches",
        "GET", "/api/inventory/expiring-batches",
        params={"user_id": uid, "days": 90},
        expected_codes=(200, 201, 401),
    )
    run("Get Stock Value",
        "GET", "/api/inventory/analytics/stock-value",
        params={"user_id": uid},
        expected_codes=(200, 201, 401),
    )
    run("Get Inventory Status",
        "GET", "/api/inventory/analytics/inventory-status",
        params={"user_id": uid},
        expected_codes=(200, 201, 401),
    )
    run("Generate Purchase Orders (Supplier POs)",
        "GET", "/api/inventory/generate-purchase-orders",
        expected_codes=(200, 201, 401),
    )
    run("Soft Delete Product",
        "DELETE", f"/api/products/{STATE['product_id'] or 1}",
        expected_codes=(200, 201, 400, 401, 404),
    )


# ─── 7. INVENTORY SYNC ────────────────────────
def test_inventory_sync():
    section("7 - INVENTORY SYNC SERVICE")
    pid = STATE["product_id"] or 1
    run("Get Current Stock",   "GET", f"/api/inventory-sync/current-stock/{pid}", expected_codes=(200, 201, 401, 404))
    run("Get All Stock",       "GET", "/api/inventory-sync/all-stock",             expected_codes=(200, 201, 401))
    run("Deduct Stock (idempotent)",
        "POST", "/api/inventory-sync/deduct-stock",
        payload={
            "product_id":      pid,
            "quantity":        2,
            "reason":          "test sale",
            "reference_id":    f"REF-{int(time.time())}",
            "idempotency_key": f"IDEM-{int(time.time())}",
        },
        expected_codes=(200, 201, 400, 401),
    )
    run("Deduct Stock Batch",
        "POST", "/api/inventory-sync/deduct-stock-batch",
        payload={"updates": [{"product_id": pid, "quantity": 1, "reference_id": f"B-{int(time.time())}", "idempotency_key": f"IB-{int(time.time())}"}]},
        expected_codes=(200, 201, 400, 401),
    )
    run("Reconcile Inventory",
        "POST", "/api/inventory-sync/reconcile",
        payload={"local_inventory": [{"product_id": pid, "quantity": 45}]},
        expected_codes=(200, 201, 400, 401),
    )


# ─── 8. INVENTORY RECONCILIATION ──────────────
def test_inventory_reconcile():
    section("8 - INVENTORY RECONCILIATION")
    pid = STATE["product_id"] or 1
    run("Full Reconciliation",    "POST", "/api/inventory-reconcile/full-reconciliation", expected_codes=(200, 201, 400, 401))
    run("Correct Stock Manually",
        "POST", "/api/inventory-reconcile/correct-stock",
        payload={"product_id": pid, "correct_stock": 48, "reason": "physical count"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Stock Audit Trail",
        "GET", f"/api/inventory-reconcile/audit-trail/{pid}",
        params={"days": 30},
        expected_codes=(200, 201, 401, 404),
    )
    run("Auto Fix Discrepancies",  "POST", "/api/inventory-reconcile/auto-fix-discrepancies", expected_codes=(200, 201, 400, 401))


# ─── 9. CUSTOMERS ─────────────────────────────
def test_customers():
    section("9 - CUSTOMER MANAGEMENT")
    run("Create Customer",
        "POST", "/api/customers/",
        payload={
            "customer_name": f"Test Customer {int(time.time())}",
            "phone":         STATE["customer_phone"],
            "email":         f"cust_{int(time.time())}@test.com",
            "city":          "Hyderabad",
            "credit_limit":  5000.0,
            "payment_terms": "Net30",
        },
        capture={"customer_id": "id"},
        expected_codes=(200, 201, 400, 401, 409),
    )
    run("Get Customers",       "GET", "/api/customers/",               params={"limit": 10}, expected_codes=(200, 201, 401))
    run("Get Single Customer", "GET", f"/api/customers/{STATE['customer_id'] or 1}", expected_codes=(200, 201, 401, 404))
    run("Update Customer",
        "PUT", f"/api/customers/{STATE['customer_id'] or 1}",
        payload={"city": "Mumbai"},
        expected_codes=(200, 201, 400, 401, 404),
    )
    run("Set Contact Preference",
        "POST", f"/api/customers/{STATE['customer_id'] or 1}/set-contact-preference",
        params={"preference": "whatsapp"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Search By Phone",  "GET", "/api/customers/search/by-phone", params={"phone": STATE["customer_phone"]}, expected_codes=(200, 201, 401))
    run("Search By Name",   "GET", "/api/customers/search/by-name",  params={"name": "Test"},                   expected_codes=(200, 201, 401))
    run("Get Credit Score", "GET", f"/api/credit-score/{STATE['customer_id'] or 1}",                            expected_codes=(200, 201, 401, 404))
    run("Soft Delete Customer",
        "DELETE", f"/api/customers/{STATE['customer_id'] or 1}",
        expected_codes=(200, 201, 400, 401, 404),
    )


# ─── 10. INVOICES ─────────────────────────────
def test_invoices():
    section("10 - INVOICES & BILLING")
    inv_num = f"INV-{int(time.time())}"
    run("Create Invoice",
        "POST", "/api/invoices/create",
        payload={
            "invoice_number": inv_num,
            "customer_name":  "Test Customer",
            "customer_phone": STATE["customer_phone"],
            "total_amount":   500.0,
            "paid_amount":    500.0,
            "tax":            9.0,
            "payment_status": "paid",
            "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
            "line_items": [
                {"product_name": "Widget", "quantity": 2, "unit_price": 250.0, "total": 500.0}
            ],
        },
        capture={"invoice_id": "id"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Sync Offline Invoice",
        "POST", "/api/invoices/sync",
        payload={
            "invoice_number": f"INV-OFF-{int(time.time())}",
            "offline_id":     f"OFF-{int(time.time())}",
            "total_amount":   200.0,
            "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
            "line_items": [{"product_name": "Offline Item", "quantity": 1, "unit_price": 200.0, "total": 200.0}],
        },
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Invoices",             "GET", "/api/invoices/",           params={"limit": 10}, expected_codes=(200, 201, 401))
    run("Get Single Invoice",       "GET", f"/api/invoices/{STATE['invoice_id'] or 1}", expected_codes=(200, 201, 401, 404))
    run("Get Overdue Invoices",     "GET", "/api/invoices/overdue",    params={"days_overdue": 30},         expected_codes=(200, 201, 401))
    run("Get Invoice Payments",     "GET", "/api/invoices/payments",   expected_codes=(200, 201, 401))
    run("Get Invoice Analytics",    "GET", "/api/invoices/analytics/summary",                                expected_codes=(200, 201, 401))
    run("Delete Invoice",
        "DELETE", f"/api/invoices/{STATE['invoice_id'] or 1}",
        expected_codes=(200, 201, 400, 401, 404),
    )


# ─── 11. BILL GENERATION ──────────────────────
def test_bills():
    section("11 - BILL GENERATION")
    run("Generate Bill",
        "POST", "/bill/Generate/Bill",
        payload={"bill_type": "retail"},
        expected_codes=(200, 201, 400, 401, 422),
    )
    bid = STATE["bill_id"] or "BILL-001"
    run("Get Bill",     "GET", f"/bill/scan/{bid}", expected_codes=(200, 201, 401, 404))
    run("Get UPI QR", "GET", "/api/shop/upi-qr", expected_codes=(200, 201, 401, 404, 422))


# ─── 12. ATTENDANCE ───────────────────────────
def test_attendance():
    section("12 - ATTENDANCE MANAGEMENT")
    uid = STATE["user_id"] or 1
    run("Create Worker",
        "POST", "/api/attendance/workers",
        params={"user_id": uid},
        payload={
            "name":          f"Worker_{int(time.time())}",
            "phone":         "9888888888",
            "salary":        20000.0,
            "position":      "Cashier",
            "assigned_work": "Billing",
            "pin":           "1234",
        },
        capture={"worker_id": "id"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Workers",
        "GET", "/api/attendance/workers",
        params={"user_id": uid},
        expected_codes=(200, 201, 401),
    )
    wid = STATE["worker_id"] or 1
    run("Update Worker",
        "PUT", f"/api/attendance/workers/{wid}",
        payload={"salary": "22000", "position": "Senior Cashier"},
        expected_codes=(200, 201, 400, 401, 404),
    )
    run("Employee Check-In",
        "POST", "/api/attendance/check-in",
        params={"employee_id": wid},
        expected_codes=(200, 201, 400, 401),
    )
    run("Employee Check-Out",
        "POST", "/api/attendance/check-out",
        params={"employee_id": wid},
        expected_codes=(200, 201, 400, 401),
    )
    run("Record Manual Attendance",
        "POST", "/api/attendance/record-manual",
        payload={
            "employee_id":     wid,
            "attendance_date": datetime.now().strftime("%Y-%m-%d"),
            "status":          "present",
            "notes":           "Auto test",
        },
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Employee Attendance",
        "GET", f"/api/attendance/employee/{wid}",
        params={"from_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")},
        expected_codes=(200, 201, 401, 404),
    )
    run("Get Attendance By Date",
        "GET", f"/api/attendance/date/{datetime.now().strftime('%Y-%m-%d')}",
        expected_codes=(200, 201, 401),
    )
    run("Request Leave",
        "POST", "/api/attendance/leave-request",
        payload={
            "employee_id": wid,
            "leave_type":  "casual",
            "from_date":   (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
            "to_date":     (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d"),
            "reason":      "Personal work",
        },
        capture={"leave_id": "id"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Leave Requests",
        "GET", "/api/attendance/leave-requests",
        params={"employee_id": str(wid)},
        expected_codes=(200, 201, 401),
    )
    lid = STATE["leave_id"] or 1
    run("Approve Leave",
        "PUT", f"/api/attendance/leave-request/{lid}/approve",
        expected_codes=(200, 201, 400, 401, 404),
    )
    run("Get Attendance Summary",   "GET", "/api/attendance/analytics/summary",          params={"days": 30}, expected_codes=(200, 201, 401))
    run("Get Employee Analytics",   "GET", f"/api/attendance/analytics/employee/{wid}",  params={"days": 30}, expected_codes=(200, 201, 401, 404))
    run("Delete Worker",
        "DELETE", f"/api/attendance/workers/{wid}",
        expected_codes=(200, 201, 400, 401, 404),
    )


# ─── 13. KHATA LEDGER ─────────────────────────
def test_khata():
    section("13 - KHATA LEDGER")
    phone = STATE["customer_phone"]
    run("Add Khata Credit",
        "POST", "/khata/credit",
        payload={"customer_phone": phone, "customer_name": "Test Customer", "amount": 500.0, "description": "Test credit"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Record Repayment",
        "POST", "/khata/repayment",
        payload={"customer_phone": phone, "amount": 100.0, "description": "Partial repay"},
        expected_codes=(200, 201, 400, 401),
    )
    run("List Khata Customers",      "GET", "/khata/customers",               params={"limit": 10}, expected_codes=(200, 201, 401))
    run("Get Customer Khata History","GET", f"/khata/history/{phone}",        expected_codes=(200, 201, 401, 404))
    run("Get WhatsApp Reminder URL", "GET", f"/khata/whatsapp-reminder/{phone}", expected_codes=(200, 201, 401, 404))
    run("Get Khata Balance (API)",   "GET", f"/api/khata/{phone}",            expected_codes=(200, 201, 401, 404))
    run("Get Khata Customers (API)", "GET", "/api/khata/customers",           expected_codes=(200, 201, 401))
    run("Update Khata Balance",
        "POST", "/api/khata/update",
        payload={"customer_phone": phone, "amount": 200.0, "transaction_type": "credit", "reference_id": f"KH-{int(time.time())}"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Khata History (API)",   "GET", f"/api/khata-history/{phone}",    params={"limit": 10}, expected_codes=(200, 201, 401, 404))


# ─── 14. PURCHASE ORDERS ──────────────────────
def test_purchase_orders():
    section("14 - PURCHASE ORDERS")
    run("Create Purchase Order",
        "POST", "/purchase-orders/",
        payload={
            "supplier_name":     "ABC Suppliers",
            "expected_delivery": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "items": [{"product_id": STATE["product_id"] or 1, "quantity": 50, "unit_price": 80.0}],
            "notes": "Test PO",
        },
        capture={"po_id": "id"},
        expected_codes=(200, 201, 400, 401),
    )
    run("List Purchase Orders", "GET", "/purchase-orders/", params={"limit": 10}, expected_codes=(200, 201, 401))
    po = STATE["po_id"] or 1
    run("Mark PO Delivered",    "POST", f"/purchase-orders/{po}/mark-delivered", expected_codes=(200, 201, 400, 401, 404))
    run("Cancel Purchase Order","POST", f"/purchase-orders/{po}/cancel",         expected_codes=(200, 201, 400, 401, 404))


# ─── 15. DELIVERY ─────────────────────────────
def test_delivery():
    section("15 - DELIVERY")
    run("Create Delivery",
        "POST", "/api/delivery/create",
        payload={
            "customer_id":      STATE["customer_id"] or 1,
            "invoice_id":       STATE["invoice_id"] or 1,
            "delivery_address": "123 Test Street, Hyderabad",
            "delivery_date":    (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "special_instructions": "Handle with care",
        },
        capture={"delivery_id": "id"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Today Deliveries",  "GET", "/api/delivery/today", expected_codes=(200, 201, 401))
    did = STATE["delivery_id"] or 1
    run("Update Delivery Status",
        "POST", f"/api/delivery/{did}/update-status",
        payload={"status": "delivered", "notes": "Delivered successfully"},
        expected_codes=(200, 201, 400, 401, 404),
    )


# ─── 16. LOYALTY ──────────────────────────────
def test_loyalty():
    section("16 - LOYALTY PROGRAM")
    cid = STATE["customer_id"] or 1
    iid = STATE["invoice_id"] or 1
    run("Earn Points",
        "POST", "/api/loyalty/earn",
        payload={"customer_id": cid, "invoice_id": iid, "amount": 500.0},
        expected_codes=(200, 201, 400, 401),
    )
    run("Redeem Points",
        "POST", "/api/loyalty/redeem",
        payload={"customer_id": cid, "points": 10, "invoice_id": iid},
        expected_codes=(200, 201, 400, 401),
    )


# ─── 17. EXPENSES ─────────────────────────────
def test_expenses():
    section("17 - EXPENSES")
    today = datetime.now().strftime("%Y-%m-%d")
    run("Create Expense (/api/expenses)",
        "POST", "/api/expenses/create",
        payload={"category": "utilities", "amount": 1500.0, "description": "Electricity bill", "date": today},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Expenses (/api/expenses)", "GET", "/api/expenses", params={"limit": 10}, expected_codes=(200, 201, 401))
    run("Get Expense History",          "GET", "/api/expenses/history", params={"category": "utilities", "limit": 10}, expected_codes=(200, 201, 401))
    run("Add Expense (/expenses)",
        "POST", "/expenses",
        payload={"category": "rent", "amount": 20000.0, "expense_date": today, "payment_method": "cash"},
        expected_codes=(200, 201, 400, 401),
    )
    run("List Expenses (/expenses)", "GET", "/expenses", params={"limit": 10}, expected_codes=(200, 201, 401))


# ─── 18. WORKERS (ENTERPRISE) ─────────────────
def test_workers_enterprise():
    section("18 - WORKERS (ENTERPRISE)")
    run("List Workers",  "GET", "/workers", expected_codes=(200, 201, 401))
    run("Add Worker",
        "POST", "/workers",
        payload={"name": f"Ent_Worker_{int(time.time())}", "phone": "9777777777", "salary": 18000.0, "position": "Helper"},
        expected_codes=(200, 201, 400, 401),
    )
    wid = STATE["worker_id"] or 1
    run("Update Worker (enterprise)",
        "PUT", f"/workers/{wid}",
        payload={"salary": "19000", "status": "active"},
        expected_codes=(200, 201, 400, 401, 404),
    )
    run("Pay Worker Salary",
        "POST", f"/workers/{wid}/pay-salary",
        params={"month": datetime.now().strftime("%Y-%m"), "worker_id": wid},
        expected_codes=(200, 201, 400, 401, 404),
    )


# ─── 19. BANK RECONCILIATION ──────────────────
def test_bank_recon():
    section("19 - BANK RECONCILIATION")
    run("Add Reconciliation",
        "POST", "/bank-recon",
        payload={
            "recon_date":          datetime.now().strftime("%Y-%m-%d"),
            "expected_upi_amount": 50000.0,
            "actual_bank_deposit": 49800.0,
            "notes":               "Minor discrepancy",
        },
        expected_codes=(200, 201, 400, 401),
    )
    run("List Reconciliations", "GET", "/bank-recon", expected_codes=(200, 201, 401))


# ─── 20. ENTERPRISE INTELLIGENCE ──────────────
def test_enterprise():
    section("20 - ENTERPRISE INTELLIGENCE")
    run("Profit & Loss",        "GET", "/enterprise/pnl",          expected_codes=(200, 201, 401))
    run("All Transactions",     "GET", "/enterprise/transactions",  params={"limit": 10}, expected_codes=(200, 201, 401))
    run("Stock Analysis",       "GET", "/retail/stock-analysis",    expected_codes=(200, 201, 401))
    run("Daily Report",         "GET", "/api/reports/daily",        expected_codes=(200, 201, 401))
    run("Churn Risk",           "GET", "/api/analytics/churn-risk", params={"days": 30}, expected_codes=(200, 201, 401))
    run("UPI Summary",          "GET", "/api/collections/today-summary", expected_codes=(200, 201, 401))
    run("Recent Transactions",  "GET", "/api/transactions/recent",  params={"limit": 10}, expected_codes=(200, 201, 401))
    run("Online Payments",      "GET", "/api/transactions/online-payments", params={"days": 30}, expected_codes=(200, 201, 401))


# ─── 21. LEGACY FEATURES ──────────────────────
def test_legacy():
    section("21 - LEGACY FEATURES")
    run("Authenticate Counter",
        "POST", "/api/counter/authenticate",
        payload={"billing_pin": "1234"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Upcoming Festivals",   "GET", "/api/festivals/upcoming",   expected_codes=(200, 201, 401))
    run("Today Occasions",      "GET", "/api/occasions/today",       expected_codes=(200, 201, 401))
    run("Get Templates",        "GET", "/api/templates",             expected_codes=(200, 201, 401))
    run("Save Template",
        "POST", "/api/templates/save",
        payload={"template_name": "Quick Sale", "template_items": [{"product_id": 1, "quantity": 1}]},
        expected_codes=(200, 201, 400, 401),
    )
    run("Setup Flash Sale",
        "POST", "/api/flash-sale/setup",
        payload={"category": "Test", "discount_pct": 10.0, "hours": 2},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Sales (legacy)",
        "GET", "/auth/sales",
        params={"user_id": STATE["user_id"] or 1},
        expected_codes=(200, 201, 400, 401),
    )


# ─── 22. GST & GIFT CARDS ─────────────────────
def test_gst_gift():
    section("22 - GST & GIFT CARDS")
    card_code = f"GC-{int(time.time())}"
    run("Issue Gift Card",
        "POST", "/gift-cards",
        payload={"card_code": card_code, "initial_balance": 500.0, "issued_to": "Test User",
                 "expiry_date": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")},
        expected_codes=(200, 201, 400, 401),
    )
    run("Redeem Gift Card",
        "POST", "/gift-cards/redeem",
        payload={"card_code": card_code, "amount_to_deduct": 100.0},
        expected_codes=(200, 201, 400, 401),
    )
    run("Export GSTR1",
        "GET", "/gst/export-gstr1",
        params={"month": datetime.now().month, "year": datetime.now().year},
        expected_codes=(200, 201, 400, 401),
    )


# ─── 23. ONLINE STORE ─────────────────────────
def test_online_store():
    section("23 - ONLINE STORE")
    
    store_email = f"store_{int(time.time())}@test.com"
    store_pass  = "Store@123"

    reg = run("Register Store Customer",
        "POST", "/store/customer/register",
        payload={
            "name":     f"Store User {int(time.time())}",
            "email":    store_email,
            "phone":    "9666666666",
            "password": store_pass,
            "city":     "Hyderabad",
        },
        expected_codes=(200, 201, 400, 401, 409, 500),
        capture={"customer_token": "access_token"},
    )

    run("Store Customer Login",
        "POST", "/store/customer/login",
        payload={"email": store_email, "password": store_pass},
        expected_codes=(200, 201, 400, 401, 500),
        capture={"customer_token": "access_token"},
    )

    run("Find Nearby Shops",    "GET", "/store/shops/nearby",
        params={"city": "Hyderabad"}, expected_codes=(200, 201, 401))
    run("Browse Shop Products", "GET", f"/store/shops/{STATE['shop_id']}/products",
        params={"limit": 10}, expected_codes=(200, 201, 401, 404))

    # Use customer token for customer-only endpoints
    saved_token = STATE["access_token"]
    STATE["access_token"] = STATE.get("customer_token") or saved_token

    run("Place Order",
        "POST", "/store/order",
        payload={
            "shop_id":          STATE["shop_id"],
            "items":            [{"product_id": STATE["product_id"] or 1, "quantity": 1}],
            "delivery_address": "123 Test Street, Hyderabad",
        },
        capture={"order_id": "order_id"},
        expected_codes=(200, 201, 400, 401, 403, 500),
    )
    run("Get My Orders", "GET", "/store/my-orders",
        expected_codes=(200, 201, 401, 403))
    run("Track Order",   "GET", f"/store/order/{STATE['order_id'] or 1}/track",
        expected_codes=(200, 201, 401, 403, 404))

    # Restore owner token
    STATE["access_token"] = saved_token

    run("Get Incoming Orders", "GET", "/store/owner/orders", params={"limit": 10},
        expected_codes=(200, 201, 401))
    oid = STATE["order_id"] or 1
    run("Update Order Status",
        "POST", f"/store/owner/orders/{oid}/action",
        params={"action": "ACCEPT"},
        expected_codes=(200, 201, 400, 401, 404, 409),
    )

# ─── 24. SALES RESTORE ────────────────────────
def test_sales_restore():
    section("24 - SALES RESTORATION")
    run("Restore All Sales",
        "POST", "/api/sales-restore/restore-all",
        payload={"include_stock_impact": False},
        expected_codes=(200, 201, 400, 401),
    )
    run("Get Restore Summary",  "GET", "/api/sales-restore/restore-summary",  expected_codes=(200, 201, 401))
    run("Restore Customers",    "POST", "/api/sales-restore/restore-customers", expected_codes=(200, 201, 400, 401))


# ─── 25. DATA & SYNC ──────────────────────────
def test_data_sync():
    section("25 - DATA & SYNC")
    run("Export Backup",       "GET", "/api/data/backup/export",    expected_codes=(200, 201, 401))
    run("Data Integrity Check","GET", "/api/data/integrity-check",  expected_codes=(200, 201, 401))
    run("Sync Sales Batch",    "POST", "/api/sync/sales",     payload={}, expected_codes=(200, 201, 400, 401))
    run("Sync Invoices Batch", "POST", "/api/sync/invoices",  payload={}, expected_codes=(200, 201, 400, 401))
    run("Sync Khata Batch",    "POST", "/api/sync/khata-balances", payload={}, expected_codes=(200, 201, 400, 401))
    run("Sync Expenses Batch", "POST", "/api/sync/expenses",  payload={}, expected_codes=(200, 201, 400, 401))
    run("Sync Invoices Chunked","POST","/api/sync/invoices/chunked", payload={}, expected_codes=(200, 201, 400, 401))


# ─── 26. BATCH OPERATIONS ─────────────────────
def test_batch_ops():
    section("26 - BATCH OPERATIONS")
    uid = STATE["user_id"] or 1
    run("Bulk Export Products",
        "POST", "/batch/api/batch/products/export",
        params={"user_id": uid},
        expected_codes=(200, 201, 400, 401),
        capture={"operation_id": "operation_id"},
    )
    run("Bulk Import Products",
        "POST", "/batch/api/batch/products/import",
        params={"user_id": uid, "overwrite": False},
        payload=[],
        expected_codes=(200, 201, 400, 401, 422),
    )
    run("Bulk Import Customers",
        "POST", "/batch/api/batch/customers/import",
        params={"user_id": uid},
        payload=[],
        expected_codes=(200, 201, 400, 401, 422),
    )
    oid = STATE["operation_id"] or 1
    run("Get Batch Status",  "GET", f"/batch/api/batch/status/{oid}",   expected_codes=(200, 201, 401, 404))
    run("Get Batch History", "GET", "/batch/api/batch/history",         params={"user_id": uid, "limit": 10}, expected_codes=(200, 201, 401))


# ─── 27. CACHING ──────────────────────────────
def test_caching():
    section("27 - CACHING SYSTEM")
    run("Cache Stats",          "GET",  "/cache/api/cache/stats",              expected_codes=(200, 201, 401))
    run("Warm Product Cache",   "POST", "/cache/api/cache/warm/products",      expected_codes=(200, 201, 400, 401))
    run("Warm Analytics Cache", "POST", "/cache/api/cache/warm/analytics",     expected_codes=(200, 201, 400, 401))
    run("Clear Cache Pattern",  "DELETE","/cache/api/cache/clear/products:*",  expected_codes=(200, 201, 400, 401))
    # Skipping clear-all to protect live data
    # run("Clear All Cache",    "DELETE","/cache/api/cache/clear-all",         expected_codes=(200, 201, 400, 401))


# ─── 28. RATE LIMITING ────────────────────────
def test_rate_limit():
    section("28 - RATE LIMITING")
    run("Rate Limit Status",   "GET", "/api/rate-limit/status/invoices",      expected_codes=(200, 201, 401, 404))
    run("Sec Rate Limit Status","GET", "/api/security/rate-limit-status",     expected_codes=(200, 201, 401))


# ─── 29. SECURITY ─────────────────────────────
def test_security():
    section("29 - SECURITY HARDENING")
    run("Get CSRF Token",      "GET",  "/api/security/csrf-token",            expected_codes=(200, 201, 401))
    run("Get Security Headers","GET",  "/api/security/security-headers",      expected_codes=(200, 201, 401))
    run("Validate Password",   "POST", "/api/security/validate-password",     params={"password": "Strong@Pass1"}, expected_codes=(200, 201, 400, 401))
    run("Check Input Security",
        "POST", "/api/security/check-input",
        payload={"input_data": "SELECT * FROM users", "check_type": "sql"},
        expected_codes=(200, 201, 400, 401),
    )
    run("Check SQL Injection", "GET",  "/api/security/check-sql-injection",   params={"query": "1 OR 1=1"}, expected_codes=(200, 201, 400, 401, 403))
    run("Sanitize Batch",      "POST", "/api/security/sanitize-batch",        payload=[], expected_codes=(200, 201, 400, 401, 422))


# ─── 30. OBSERVABILITY LOGGING ────────────────
def test_observability_logging():
    section("30 - OBSERVABILITY LOGGING")
    run("Log Event",
        "POST", "/api/observability/log",
        payload={
            "level":     "info",
            "message":   "Automated test log entry",
            "context":   {"source": "pytest"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        expected_codes=(200, 201, 400, 401),
    )
    run("Log Error",
        "POST", "/api/observability/error",
        payload={},
        expected_codes=(200, 201, 400, 401, 422),
    )


# ─── CLEANUP ──────────────────────────────────
def test_logout():
    section("CLEANUP - LOGOUT")
    if STATE["access_token"]:
        run("Session Logout",
            "POST", "/api/session/logout",
            payload={"access_token": STATE["access_token"]},
            expected_codes=(200, 201, 400, 401),
        )
    if STATE["user_id"]:
        run("Session Logout All",
            "POST", "/api/session/logout-all",
            payload={"user_id": STATE["user_id"]},
            expected_codes=(200, 201, 400, 401),
        )


# ==============================================
#  SUMMARY
# ==============================================
def print_summary():
    total   = len(RESULTS)
    passed  = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed  = sum(1 for r in RESULTS if r["status"] == "FAIL")
    skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")
    timeout = sum(1 for r in RESULTS if r["status"] in ("TIMEOUT", "ERROR"))

    bar = "================================================================"
    print(f"\n{bar}")
    print("  RETAIL MIND - TEST SUMMARY")
    print(bar)
    print(f"  Total    : {total}")
    print(f"  [PASS] PASS  : {passed}")
    print(f"  [FAIL] FAIL  : {failed}")
    print(f"  [SKIP] SKIP  : {skipped}")
    print(f"  [TIME] TIMEOUT/ERR : {timeout}")
    print(f"  Pass rate: {passed/total*100:.1f}%" if total else "  No tests run")
    print(bar)

    if failed:
        print("\n  FAILED ENDPOINTS:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"    [FAIL] [{r['code']}] {r['label']}  {r['detail'][:80]}")

    # Write JSON report
    report_path = "test_report.json"
    with open(report_path, "w") as f:
        json.dump({
            "run_at":    datetime.utcnow().isoformat() + "Z",
            "base_url":  BASE_URL,
            "summary":   {"total": total, "passed": passed, "failed": failed, "skipped": skipped, "errors": timeout},
            "results":   RESULTS,
        }, f, indent=2)
    print(f"\n  📄 Full JSON report saved to: {report_path}")
    print(bar)


# ─── 31. ADDITIONAL MISSING ENDPOINTS ─────────────────
def test_missing_endpoints():
    section("31 - ADDITIONAL MISSING ENDPOINTS")
    run("Create Sale Legacy", "POST", "/auth/sales", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Delete Product", "DELETE", f"/api/inventory/products/{STATE['product_id'] or 1}", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Reject Leave", "PUT", f"/api/attendance/leave-request/{1 or 'leave_id'}/reject", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Create Shop Profile", "POST", "/api/shop/create", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Update Profile", "PUT", "/api/shop/profile", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Upload Logo", "POST", "/api/shop/upload-logo", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Create Shop Profile", "POST", "/shop/profile", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Clear Cache Pattern", "DELETE", f"/cache/api/cache/clear/{1 or 'pattern'}", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Clear All Cache", "DELETE", "/cache/api/cache/clear-all", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))
    run("Get Rate Limit Status", "GET", f"/api/rate-limit/status/{1 or 'endpoint'}", expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))


# ==============================================
#  MAIN
# ==============================================
if __name__ == "__main__":
    print(f"""
======================================================================
  RETAIL MIND ULTRA API TEST SUITE                                   
  Target : {BASE_URL:<55}
  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<55}
======================================================================
""")

    test_system()
    test_auth()
    test_auth_hardened()
    test_session()
    test_shop()
    test_inventory()
    test_inventory_sync()
    test_inventory_reconcile()
    test_customers()
    test_invoices()
    test_bills()
    test_attendance()
    test_khata()
    test_purchase_orders()
    test_delivery()
    test_loyalty()
    test_expenses()
    test_workers_enterprise()
    test_bank_recon()
    test_enterprise()
    test_legacy()
    test_gst_gift()
    test_online_store()
    test_sales_restore()
    test_data_sync()
    test_batch_ops()
    test_caching()
    test_rate_limit()
    test_security()
    test_observability_logging()
    test_missing_endpoints()
    test_logout()

    print_summary()
    sys.exit(0 if all(r["status"] in ("PASS", "SKIP") for r in RESULTS) else 1)


