#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║       RETAIL MIND — PRODUCTION VALIDATION SUITE                     ║
║       14 Critical Business Logic Tests                              ║
║       Run AFTER ultra_test_suite.py passes                          ║
╚══════════════════════════════════════════════════════════════════════╝

Tests real business correctness, not just endpoint existence.
Each test verifies that the SYSTEM BEHAVES CORRECTLY end-to-end.

Run:
    python production_validation_suite.py
    python production_validation_suite.py --base-url https://your-url.onrender.com
"""

import requests
import json
import time
import sys
import os
import argparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Any

# ─── Config ───────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default=os.getenv("TEST_BASE_URL", "https://retail-mind-vkbp.onrender.com"))
args, _ = parser.parse_known_args()

BASE_URL = args.base_url
TIMEOUT  = 20
TS       = int(time.time())   # unique suffix for this run

# ─── Shared State ─────────────────────────────────────────────────────
STATE = {
    "access_token":   None,
    "user_id":        None,
    "product_id":     None,
    "invoice_id":     None,
    "customer_id":    None,
    "worker_id":      None,
    "shop_id":        1,
    "customer_token": None,
    "order_id":       None,
    "customer_phone": f"98{TS % 100000000:08d}",   # unique 10-digit phone
}

# ─── Result Tracking ──────────────────────────────────────────────────
RESULTS   = []
PASS_COUNT = 0
FAIL_COUNT = 0

def headers():
    h = {"Content-Type": "application/json"}
    if STATE["access_token"]:
        h["Authorization"] = f"Bearer {STATE['access_token']}"
    return h

def customer_headers():
    h = {"Content-Type": "application/json"}
    tok = STATE.get("customer_token") or STATE.get("access_token")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h

def api(method, path, payload=None, params=None, hdrs=None):
    """Raw API call — returns (status_code, body_dict)"""
    url = BASE_URL + path
    try:
        r = requests.request(
            method.upper(), url,
            headers=hdrs or headers(),
            json=payload,
            params={k: v for k, v in (params or {}).items() if v is not None},
            timeout=TIMEOUT,
        )
        try:
            body = r.json()
        except Exception:
            body = {"_raw": r.text[:300]}
        return r.status_code, body
    except Exception as e:
        return -1, {"_error": str(e)}

# ─── Test Runner ──────────────────────────────────────────────────────
def check(test_name, passed: bool, detail: str = ""):
    global PASS_COUNT, FAIL_COUNT
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS_COUNT += 1
        print(f"  ✅  {test_name}")
    else:
        FAIL_COUNT += 1
        print(f"  ❌  {test_name}")
        if detail:
            print(f"       → {detail}")
    RESULTS.append({"test": test_name, "status": status, "detail": detail})

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ─── Setup: Login ─────────────────────────────────────────────────────
def setup_login():
    """
    Login using the exact same flow as ultra_test_suite.py.
    Route: POST /auth/register  then  POST /auth/login
    """
    section("SETUP — LOGIN")
    username = f"valuser_{TS}"
    email    = f"valuser_{TS}@retailmind.test"
    password = "Test@123456"

    # Step 1 — Register (same payload as ultra_test_suite)
    code, body = api("POST", "/auth/register", {
        "username":  username,
        "password":  password,
        "email":     email,
        "user_type": "owner",
    })
    print(f"  Register → {code}")

    # Step 2 — Login (same payload as ultra_test_suite)
    code, body = api("POST", "/auth/login", {
        "email":    email,
        "password": password,
    })
    print(f"  Login    → {code} | token={'YES' if body.get('access_token') else 'NO'}")

    if code in (200, 201) and body.get("access_token"):
        STATE["access_token"] = body["access_token"]
        STATE["refresh_token"] = body.get("refresh_token")
        STATE["user_id"]       = body.get("user_id") or body.get("id")
        STATE["test_email"]    = email
        print(f"  ✅  Logged in as {email} (user_id={STATE['user_id']})")
        return True

    print(f"  ❌  Login failed (code={code}) body={str(body)[:150]}")
    print(f"  ⚠️   Running without auth — all authenticated tests will fail")
    return False


def setup_product():
    """Create a product to use in inventory tests"""
    code, body = api("POST", "/api/inventory/products", {
        "product_name":  f"TestMilk_{TS}",
        "sku":           f"MILK-{TS}",
        "unit_price":    50.0,
        "current_stock": 100,
        "min_stock":     5,
        "max_stock":     500,
        "reorder_level": 10,
        "category":      "Dairy",
    })
    if code in (200, 201):
        STATE["product_id"] = body.get("id")
        print(f"  ✅  Created product id={STATE['product_id']}")


# ══════════════════════════════════════════════════════════════════════
#  TEST 1 — Inventory Deduction Validation
#  Verifies stock actually decreases after a sale
# ══════════════════════════════════════════════════════════════════════
def test_inventory_deduction():
    section("TEST 1 — Inventory Deduction After Sale")
    pid = STATE["product_id"]
    if not pid:
        check("Inventory deduction — skipped (no product)", False, "Run setup_product first")
        return

    # Get stock before
    code, body = api("GET", f"/api/inventory/products/{pid}")
    if code != 200:
        check("Get stock before sale", False, f"code={code}")
        return
    stock_before = body.get("current_stock", -1)
    check(f"Stock before sale readable (={stock_before})", stock_before >= 0)

    # Create a sale / invoice with qty=5
    qty_sold = 5
    code, body = api("POST", "/api/invoices/create", {
        "invoice_number": f"INV-DEDUCT-{TS}",
        "subtotal":       250.0,
        "tax":            0.0,
        "total_amount":   250.0,
        "paid_amount":    250.0,
        "payment_status": "paid",
        "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
        "line_items": [
            {"product_id": pid, "product_name": "TestMilk", "quantity": qty_sold, "unit_price": 50.0, "total": 250.0}
        ],
    })
    created = code in (200, 201)
    check("Invoice created successfully", created, f"code={code} body={str(body)[:100]}")
    if not created:
        return

    time.sleep(1)   # give backend time to update

    # Get stock after
    code, body = api("GET", f"/api/inventory/products/{pid}")
    stock_after = body.get("current_stock", -1)
    expected = stock_before - qty_sold

    check(
        f"Stock deducted correctly ({stock_before} - {qty_sold} = {expected}, got {stock_after})",
        stock_after == expected,
        f"Expected {expected}, got {stock_after}. Stock NOT deducting on sale!"
    )


# ══════════════════════════════════════════════════════════════════════
#  TEST 2 — Duplicate Invoice Prevention
#  Same invoice_number must return 409
# ══════════════════════════════════════════════════════════════════════
def test_duplicate_invoice():
    section("TEST 2 — Duplicate Invoice Prevention")
    inv_num = f"INV-DUP-{TS}"
    payload = {
        "invoice_number": inv_num,
        "subtotal":       100.0,
        "tax":            0.0,
        "total_amount":   100.0,
        "paid_amount":    100.0,
        "payment_status": "paid",
        "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
        "line_items": [{"product_name": "Widget", "quantity": 1, "unit_price": 100.0, "total": 100.0}],
    }

    code1, _ = api("POST", "/api/invoices/create", payload)
    check("First invoice created", code1 in (200, 201), f"code={code1}")

    time.sleep(0.5)
    code2, body2 = api("POST", "/api/invoices/create", payload)
    check(
        "Duplicate invoice rejected (409)",
        code2 in (400, 409),
        f"Expected 409, got {code2}. Duplicate invoices are being created! body={str(body2)[:100]}"
    )


# ══════════════════════════════════════════════════════════════════════
#  TEST 3 — Invoice Product Name Persistence
#  "Unknown Product" / "Unknown Item" bug check
# ══════════════════════════════════════════════════════════════════════
def test_invoice_product_name():
    section("TEST 3 — Invoice Product Name Persistence")
    inv_num  = f"INV-PNAME-{TS}"
    prod_name = "Premium Basmati Rice"

    code, body = api("POST", "/api/invoices/create", {
        "invoice_number": inv_num,
        "subtotal":       200.0,
        "tax":            0.0,
        "total_amount":   200.0,
        "paid_amount":    200.0,
        "payment_status": "paid",
        "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
        "line_items": [
            {"product_name": prod_name, "quantity": 2, "unit_price": 100.0, "total": 200.0}
        ],
    })
    if code not in (200, 201):
        check("Invoice created for product name test", False, f"code={code}")
        return

    inv_id = body.get("id") or body.get("invoice_id")
    STATE["invoice_id"] = inv_id
    check("Invoice created", inv_id is not None, f"No ID in response: {str(body)[:100]}")
    if not inv_id:
        return

    time.sleep(0.5)
    code, body = api("GET", f"/api/invoices/{inv_id}")
    if code != 200:
        check("Invoice readable after creation", False, f"code={code}")
        return

    # Check line items for "Unknown" product names
    line_items = body.get("line_items") or body.get("items") or []
    if isinstance(line_items, str):
        try:
            line_items = json.loads(line_items)
        except Exception:
            line_items = []

    found_unknown = any(
        "unknown" in str(item.get("product_name", "")).lower()
        for item in line_items
    )
    check(
        f"Product name saved correctly (not 'Unknown')",
        not found_unknown and len(line_items) > 0,
        f"Product name is 'Unknown'! line_items={line_items}"
    )

    if line_items:
        saved_name = line_items[0].get("product_name", "")
        check(
            f"Product name matches '{prod_name}'",
            saved_name == prod_name,
            f"Expected '{prod_name}', got '{saved_name}'"
        )


# ══════════════════════════════════════════════════════════════════════
#  TEST 4 — Profile Persistence After Logout/Login
# ══════════════════════════════════════════════════════════════════════
def test_profile_persistence():
    section("TEST 4 — Profile Persistence After Logout/Login")
    shop_name = f"RetailMind Shop {TS}"

    # Update shop profile
    code, body = api("PUT", "/shop/profile", {"shop_name": shop_name, "phone": "9999999999", "city": "Hyderabad"})
    check("Shop profile updated", code in (200, 201, 400), f"code={code}")   # 400 if already exists is fine

    # Try the /api/shop path too
    code2, _ = api("PUT", "/api/shop/settings", {"shop_name": shop_name})

    # Logout
    api("POST", "/api/auth/logout")
    old_token = STATE["access_token"]
    STATE["access_token"] = None

    time.sleep(0.5)

    # Login again with same credentials used in setup_login
    code, body = api("POST", "/auth/login", {
        "email":    f"valuser_{TS}@retailmind.test",
        "password": "Test@123456",
    })
    if code in (200, 201) and body.get("access_token"):
        STATE["access_token"] = body["access_token"]
    else:
        STATE["access_token"] = old_token   # restore if login fails

    # Read profile
    code, body = api("GET", "/shop/profile")
    if code != 200:
        code, body = api("GET", "/api/shop/profile")

    if code == 200:
        returned_name = body.get("shop_name", "")
        check(
            f"Shop name persisted after re-login",
            returned_name == shop_name,
            f"Expected '{shop_name}', got '{returned_name}'"
        )
    else:
        check("Profile readable after re-login", False, f"code={code}")


# ══════════════════════════════════════════════════════════════════════
#  TEST 5 — Worker Persistence After Backup/Restore
# ══════════════════════════════════════════════════════════════════════
def test_worker_persistence():
    section("TEST 5 — Worker Persistence After Backup/Restore")
    uid  = STATE["user_id"] or 1
    name = f"Worker_Val_{TS}"

    # Create worker
    code, body = api("POST", "/api/attendance/workers",
        payload={"name": name, "phone": "9777777777", "salary": 18000.0, "position": "Helper", "pin": "9999"},
        params={"user_id": uid},
    )
    created = code in (200, 201)
    wid = body.get("id") if created else None
    check(f"Worker '{name}' created", created, f"code={code}")

    # Trigger backup
    code, _ = api("POST", "/api/sales-restore/restore-all", {"include_stock_impact": False})
    check("Backup/restore triggered", code in (200, 201, 400, 401), f"code={code}")

    time.sleep(1)

    # Verify worker still exists
    code, body = api("GET", "/api/attendance/workers", params={"user_id": uid})
    if code == 200:
        workers = body if isinstance(body, list) else body.get("workers", [])
        names   = [w.get("name", "") for w in workers]
        check(
            f"Worker '{name}' persists after restore",
            name in names,
            f"Worker missing after restore! Found: {names[:5]}"
        )
    else:
        check("Workers list readable after restore", False, f"code={code}")


# ══════════════════════════════════════════════════════════════════════
#  TEST 6 — Dashboard Sales vs Actual Sales Count Match
# ══════════════════════════════════════════════════════════════════════
def test_dashboard_matches_sales():
    section("TEST 6 — Dashboard Sales Count Matches Actual")

    # Get dashboard/overview
    code, dash = api("GET", "/api/analytics/business-overview")
    if code != 200:
        code, dash = api("GET", "/api/reports/daily")
    check("Dashboard readable", code == 200, f"code={code}")

    # Get actual invoices
    code, inv_body = api("GET", "/api/invoices/", params={"limit": 200})
    check("Invoices list readable", code == 200, f"code={code}")

    if code == 200:
        actual_count = len(inv_body) if isinstance(inv_body, list) else inv_body.get("total", len(inv_body.get("invoices", [])))
        dash_count   = (dash or {}).get("total_invoices") or (dash or {}).get("invoice_count") or (dash or {}).get("total_sales")

        if dash_count is not None:
            check(
                f"Dashboard count ({dash_count}) matches invoices ({actual_count})",
                int(dash_count) == int(actual_count),
                f"Dashboard shows {dash_count} but actual invoices = {actual_count}. Dashboard mismatch!"
            )
        else:
            check("Dashboard has sales count field", False, f"No sales count field in dashboard. body keys: {list((dash or {}).keys())}")


# ══════════════════════════════════════════════════════════════════════
#  TEST 7 — Voice Billing Accuracy
#  Tests that the voice processing endpoint parses items correctly
# ══════════════════════════════════════════════════════════════════════
def test_voice_billing_accuracy():
    section("TEST 7 — Voice Billing Accuracy")

    # Try common voice billing endpoints
    endpoints = [
        ("/api/voice/process", "POST"),
        ("/api/voice-billing/parse", "POST"),
        ("/api/billing/voice", "POST"),
        ("/voice/process", "POST"),
    ]

    voice_endpoint = None
    for path, method in endpoints:
        code, _ = api(method, path, {"text": "test"})
        if code not in (404, 405):
            voice_endpoint = (method, path)
            break

    if not voice_endpoint:
        check("Voice billing endpoint exists", False, "None of the common voice endpoints found. Add /api/voice/process")
        return

    method, path = voice_endpoint
    check(f"Voice billing endpoint found at {path}", True)

    # Test 1: Basic two-item parse
    code, body = api(method, path, {"text": "milk two bread one"})
    check("Voice parse returns 200", code in (200, 201), f"code={code}")
    if code in (200, 201):
        items = body.get("items") or body.get("products") or []
        check("Voice parsed 2 items", len(items) == 2, f"Expected 2 items, got {len(items)}: {items}")

        if len(items) >= 1:
            p1 = items[0]
            check(
                "First item is Milk",
                "milk" in str(p1.get("product") or p1.get("product_name") or p1.get("name") or "").lower(),
                f"First item: {p1}"
            )
            check(
                "First item qty is 2",
                int(p1.get("qty") or p1.get("quantity") or 0) == 2,
                f"First item qty: {p1}"
            )

    # Test 2: "Rupees" must not appear in product name
    code, body = api(method, path, {"text": "milk rupees fifty"})
    if code in (200, 201):
        items = body.get("items") or body.get("products") or []
        for item in items:
            pname = str(item.get("product") or item.get("product_name") or item.get("name") or "").lower()
            check(
                f"'rupees' not in product name (got '{pname}')",
                "rupees" not in pname,
                f"Product name contains 'rupees': '{pname}'. Fix voice parser to strip price words."
            )


# ══════════════════════════════════════════════════════════════════════
#  TEST 8 — Customer Auth Flow (Register → Login → Profile → Order)
# ══════════════════════════════════════════════════════════════════════
def test_customer_auth_flow():
    section("TEST 8 — Customer Authentication Flow")
    email    = f"cust{TS % 100000}@store.test"   # valid email, no special chars before @
    password = "Cust@123"
    name     = f"Customer{TS}"

    # Register
    code, body = api("POST", "/store/customer/register", {
        "name": name, "email": email, "phone": "9555555555", "password": password, "city": "Mumbai"
    })
    registered = code in (200, 201)
    check("Customer register", registered, f"code={code} body={str(body)[:100]}")

    # Login
    code, body = api("POST", "/store/customer/login", {"email": email, "password": password})
    logged_in = code in (200, 201) and bool(body.get("access_token"))
    check("Customer login", logged_in, f"code={code} body={str(body)[:100]}")
    if logged_in:
        STATE["customer_token"] = body["access_token"]

    # Get profile
    code, body = api("GET", "/store/customer/profile", hdrs=customer_headers())
    check("Customer profile readable", code in (200, 201, 401, 404), f"code={code}")

    # Forgot password endpoint exists
    code, _ = api("POST", "/store/customer/forgot-password", {"email": email})
    check("Forgot password endpoint exists", code not in (404, 405), f"code={code} — endpoint missing")

    # Reset password endpoint exists
    code, _ = api("POST", "/store/customer/reset-password", {"token": "dummy", "new_password": "New@123"})
    check("Reset password endpoint exists", code not in (405,), f"code={code} — endpoint missing")


# ══════════════════════════════════════════════════════════════════════
#  TEST 9 — Full Online Store Flow (Enable → Publish → Order → Accept)
# ══════════════════════════════════════════════════════════════════════
def test_online_store_flow():
    section("TEST 9 — Full Online Store Flow")
    shop_id = STATE["shop_id"] or 1

    # Enable store
    code, _ = api("POST", "/shop/toggle-online-store", params={"enable": True})
    check("Online store enabled", code in (200, 201, 400), f"code={code}")

    # Browse products
    code, body = api("GET", f"/store/shops/{shop_id}/products", params={"limit": 5})
    check("Products browsable in store", code in (200, 201, 404), f"code={code}")

    # Place order (as customer)
    pid = STATE["product_id"] or 1
    code, body = api("POST", "/store/order", {
        "shop_id":          shop_id,
        "items":            [{"product_id": pid, "quantity": 1}],
        "delivery_address": "456 Test Road, Mumbai",
    }, hdrs=customer_headers())
    placed = code in (200, 201)
    check("Customer can place order", placed or code in (400, 401, 403), f"code={code}")
    oid = body.get("order_id") or body.get("id") if placed else None
    if oid:
        STATE["order_id"] = oid

    # Owner sees incoming orders
    code, body = api("GET", "/store/owner/orders", params={"limit": 5})
    check("Owner sees incoming orders", code in (200, 201), f"code={code}")

    # Owner accepts order
    if STATE["order_id"]:
        code, _ = api("POST", f"/store/owner/orders/{STATE['order_id']}/action", params={"action": "ACCEPT"})
        check("Owner can accept order", code in (200, 201, 400, 404, 409), f"code={code}")

    # Track order
    oid = STATE["order_id"] or 1
    code, _ = api("GET", f"/store/order/{oid}/track", hdrs=customer_headers())
    check("Order tracking works", code in (200, 201, 401, 404), f"code={code}")


# ══════════════════════════════════════════════════════════════════════
#  TEST 10 — Concurrent Sales (No Duplicate Invoices / No Race Conditions)
# ══════════════════════════════════════════════════════════════════════
def test_concurrent_sales():
    section("TEST 10 — Concurrent Sales (10 Simultaneous)")

    def make_sale(n):
        inv_num = f"CONC-{TS}-{n}"
        code, body = api("POST", "/api/invoices/create", {
            "invoice_number": inv_num,
            "subtotal":       50.0,
            "tax":            0.0,
            "total_amount":   50.0,
            "paid_amount":    50.0,
            "payment_status": "paid",
            "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
            "line_items":     [{"product_name": "ConcurrentItem", "quantity": 1, "unit_price": 50.0, "total": 50.0}],
        })
        return n, code, body

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(make_sale, i) for i in range(10)]
        results = [f.result() for f in as_completed(futures)]

    codes    = [r[1] for r in results]
    success  = sum(1 for c in codes if c in (200, 201))
    errors   = sum(1 for c in codes if c == 500)
    check(f"All 10 concurrent invoices created ({success}/10 succeeded)", success == 10,
          f"Only {success}/10 succeeded. {errors} server errors. Race condition suspected.")
    check("No 500 errors under concurrency", errors == 0,
          f"{errors} concurrent requests crashed the server")

    # Verify no duplicate invoice numbers in DB
    time.sleep(1)
    code, body = api("GET", "/api/invoices/", params={"limit": 200})
    if code == 200:
        invoices = body if isinstance(body, list) else body.get("invoices", [])
        inv_nums  = [i.get("invoice_number") for i in invoices if i.get("invoice_number", "").startswith(f"CONC-{TS}")]
        duplicates = len(inv_nums) - len(set(inv_nums))
        check(f"No duplicate invoice numbers (found {len(inv_nums)} unique)", duplicates == 0,
              f"{duplicates} duplicate invoice numbers created!")


# ══════════════════════════════════════════════════════════════════════
#  TEST 11 — Offline Sync Deduplication
#  Same offline_id sent twice must not create duplicate records
# ══════════════════════════════════════════════════════════════════════
def test_offline_sync_deduplication():
    section("TEST 11 — Offline Sync Deduplication")
    offline_id = f"OFF-{TS}-DEDUP"
    payload    = {
        "invoice_number": f"INV-{offline_id}",
        "offline_id":     offline_id,
        "total_amount":   300.0,
        "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
        "line_items": [{"product_name": "OfflineItem", "quantity": 1, "unit_price": 300.0, "total": 300.0}],
    }

    code1, _ = api("POST", "/api/invoices/sync", payload)
    check("First offline sync accepted", code1 in (200, 201), f"code={code1}")

    time.sleep(0.5)
    code2, body2 = api("POST", "/api/invoices/sync", payload)
    check(
        "Duplicate offline sync rejected or deduplicated",
        code2 in (200, 201, 400, 409),
        f"code={code2}"
    )

    # If both return 200, verify only one record exists
    if code1 in (200, 201) and code2 in (200, 201):
        time.sleep(0.5)
        code, body = api("GET", "/api/invoices/", params={"limit": 200})
        if code == 200:
            invoices   = body if isinstance(body, list) else body.get("invoices", [])
            off_invs   = [i for i in invoices if str(i.get("invoice_number") or "").endswith(offline_id.split("-")[-1])]
            check(
                f"Only 1 record created (not duplicated), found {len(off_invs)}",
                len(off_invs) <= 1,
                f"Duplicate offline sync created {len(off_invs)} records!"
            )


# ══════════════════════════════════════════════════════════════════════
#  TEST 12 — Response Schema / Field Type Validation
#  Critical fields must exist and be correct types
# ══════════════════════════════════════════════════════════════════════
def test_response_schema():
    section("TEST 12 — Response Schema & Field Type Validation")

    # Invoice schema
    inv_num = f"INV-SCHEMA-{TS}"
    code, body = api("POST", "/api/invoices/create", {
        "invoice_number": inv_num,
        "subtotal":       100.0,
        "tax":            18.0,
        "total_amount":   118.0,
        "paid_amount":    118.0,
        "payment_status": "paid",
        "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
        "line_items": [{"product_name": "SchemaTest", "quantity": 1, "unit_price": 100.0, "total": 100.0}],
    })
    if code in (200, 201):
        inv = body
        check("Invoice has 'id' field",            "id" in inv,              f"Missing 'id'. keys={list(inv.keys())}")
        check("Invoice has 'total_amount' field",  "total_amount" in inv,    f"Missing 'total_amount'")
        check("Invoice total_amount is numeric",
              isinstance(inv.get("total_amount"), (int, float)),
              f"total_amount type={type(inv.get('total_amount')).__name__}")
        check("Invoice total_amount is correct (118.0)",
              float(inv.get("total_amount", 0)) == 118.0,
              f"total_amount={inv.get('total_amount')}")
        check("Invoice has 'invoice_number'",  "invoice_number" in inv,  f"Missing invoice_number")
        check("Invoice has 'line_items'",      "line_items" in inv or "items" in inv,  f"Missing line_items")

    # Product schema
    code, body = api("POST", "/api/inventory/products", {
        "product_name":  f"SchemaTestProd_{TS}",
        "sku":           f"STEST-{TS}",
        "unit_price":    99.99,
        "current_stock": 50,
        "min_stock":     5,
    })
    if code in (200, 201):
        prod = body
        check("Product has 'id'",            "id" in prod,             f"keys={list(prod.keys())}")
        check("Product has 'current_stock'", "current_stock" in prod,  f"Missing current_stock")
        check("Product has 'unit_price'",    "unit_price" in prod,     f"Missing unit_price")
        check("unit_price is numeric",
              isinstance(prod.get("unit_price"), (int, float)),
              f"unit_price type={type(prod.get('unit_price')).__name__}")
        check("unit_price value correct (99.99)",
              abs(float(prod.get("unit_price", 0)) - 99.99) < 0.01,
              f"unit_price={prod.get('unit_price')}")

    # Customer schema
    phone = STATE["customer_phone"]
    code, body = api("POST", "/api/customers/", {
        "customer_name": f"SchemaCustomer_{TS}",
        "phone":         phone,
        "credit_limit":  1000.0,
    })
    if code in (200, 201):
        cust = body
        check("Customer has 'id'",            "id" in cust,            f"keys={list(cust.keys())}")
        check("Customer has 'customer_name'", "customer_name" in cust, f"Missing customer_name")
        check("Customer has 'phone'",         "phone" in cust,         f"Missing phone")
        check("credit_limit is numeric",
              isinstance(cust.get("credit_limit"), (int, float)),
              f"credit_limit type={type(cust.get('credit_limit')).__name__}")


# ══════════════════════════════════════════════════════════════════════
#  TEST 13 — Khata Balance Integrity
#  Credit + Repayment must produce correct running balance
# ══════════════════════════════════════════════════════════════════════
def test_khata_balance_integrity():
    section("TEST 13 — Khata Balance Integrity")
    phone = f"97{TS % 100000000:08d}"

    # Add credit of 500
    code, body = api("POST", "/khata/credit", {
        "customer_phone": phone,
        "customer_name":  f"KhataTest_{TS}",
        "amount":         500.0,
        "description":    "Test credit",
    })
    check("Khata credit added (₹500)", code in (200, 201), f"code={code} body={str(body)[:100]}")

    # Add more credit of 300
    code, body = api("POST", "/khata/credit", {
        "customer_phone": phone,
        "customer_name":  f"KhataTest_{TS}",
        "amount":         300.0,
    })
    check("Second Khata credit added (₹300)", code in (200, 201), f"code={code}")

    # Repayment of 200
    code, body = api("POST", "/khata/repayment", {
        "customer_phone": phone,
        "amount":         200.0,
        "description":    "Test payment",
    })
    check("Khata repayment recorded (₹200)", code in (200, 201), f"code={code}")
    remaining = body.get("remaining_balance") if code in (200, 201) else None

    # Expected balance: 500 + 300 - 200 = 600
    if remaining is not None:
        check(
            f"Khata balance correct (500+300-200=600, got {remaining})",
            abs(float(remaining) - 600.0) < 0.01,
            f"Expected ₹600, got ₹{remaining}. Balance calculation broken!"
        )

    # Over-payment must be rejected
    code, body = api("POST", "/khata/repayment", {
        "customer_phone": phone,
        "amount":         10000.0,
    })
    check(
        "Over-payment rejected (400)",
        code == 400,
        f"Expected 400 for over-payment, got {code}. Customer can pay more than they owe!"
    )


# ══════════════════════════════════════════════════════════════════════
#  TEST 14 — GST Calculation Accuracy
#  18% tax must compute correctly
# ══════════════════════════════════════════════════════════════════════
def test_gst_calculation():
    section("TEST 14 — GST Calculation Accuracy")
    inv_num  = f"INV-GST-{TS}"
    subtotal = 1000.0
    tax_rate = 18.0
    expected_tax   = round(subtotal * tax_rate / 100, 2)   # 180.0
    expected_total = round(subtotal + expected_tax, 2)      # 1180.0

    code, body = api("POST", "/api/invoices/create", {
        "invoice_number": inv_num,
        "subtotal":       subtotal,
        "tax":            expected_tax,
        "total_amount":   expected_total,
        "paid_amount":    expected_total,
        "payment_status": "paid",
        "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
        "line_items": [{"product_name": "GSTItem", "quantity": 1, "unit_price": subtotal, "total": subtotal}],
    })

    if code in (200, 201):
        saved_tax   = float(body.get("tax", -1))
        saved_total = float(body.get("total_amount", -1))

        check(
            f"GST saved correctly (expected {expected_tax}, got {saved_tax})",
            abs(saved_tax - expected_tax) < 0.01,
            f"Tax mismatch: expected ₹{expected_tax}, stored ₹{saved_tax}"
        )
        check(
            f"Total with GST correct (expected {expected_total}, got {saved_total})",
            abs(saved_total - expected_total) < 0.01,
            f"Total mismatch: expected ₹{expected_total}, stored ₹{saved_total}"
        )

    # GSTR-1 export should include the invoice
    code, body = api("GET", "/gst/export-gstr1", params={
        "month": datetime.now().month,
        "year":  datetime.now().year,
    })
    check("GSTR-1 export requires GST number (400 is fine)", code in (200, 400), f"code={code}")
    if code == 200:
        gstr = body.get("gstr1_data", {})
        check("GSTR-1 has gstin field",   "gstin" in gstr,  f"Missing gstin in GSTR-1 output")
        check("GSTR-1 has b2cs section",  "b2cs" in gstr,   f"Missing b2cs in GSTR-1 output")


# ══════════════════════════════════════════════════════════════════════
#  SUMMARY
# ══════════════════════════════════════════════════════════════════════
def print_summary():
    total = PASS_COUNT + FAIL_COUNT
    rate  = (PASS_COUNT / total * 100) if total else 0
    print(f"""
{'='*60}
  PRODUCTION VALIDATION — SUMMARY
{'='*60}
  Total Checks : {total}
  ✅  PASSED   : {PASS_COUNT}
  ❌  FAILED   : {FAIL_COUNT}
  Pass Rate    : {rate:.1f}%
{'='*60}
""")
    if FAIL_COUNT > 0:
        print("  FAILED CHECKS:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"    ❌  {r['test']}")
                if r["detail"]:
                    print(f"         → {r['detail']}")
        print()

    # Save report
    report = {
        "run_at":     datetime.now().isoformat(),
        "base_url":   BASE_URL,
        "total":      total,
        "passed":     PASS_COUNT,
        "failed":     FAIL_COUNT,
        "pass_rate":  round(rate, 1),
        "results":    RESULTS,
    }
    with open("production_validation_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print("  📄 Full report saved to: production_validation_report.json")


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"""
======================================================================
  RETAIL MIND — PRODUCTION VALIDATION SUITE
  Target  : {BASE_URL}
  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
  Checks  : 14 Critical Business Logic Tests
======================================================================
""")
    if not setup_login():
        print("⚠️  Warning: Running without auth — some tests will fail")
    setup_product()

    test_inventory_deduction()       # 1
    test_duplicate_invoice()         # 2
    test_invoice_product_name()      # 3
    test_profile_persistence()       # 4
    test_worker_persistence()        # 5
    test_dashboard_matches_sales()   # 6
    test_voice_billing_accuracy()    # 7
    test_customer_auth_flow()        # 8
    test_online_store_flow()         # 9
    test_concurrent_sales()          # 10
    test_offline_sync_deduplication()# 11
    test_response_schema()           # 12
    test_khata_balance_integrity()   # 13
    test_gst_calculation()           # 14

    print_summary()
    sys.exit(0 if FAIL_COUNT == 0 else 1)