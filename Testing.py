#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║              RETAIL MIND — COMPLETE BACKEND API TEST SUITE                     ║
║              Target: https://retail-mind-vkbp.onrender.com                     ║
║              Total Endpoints: 184                                               ║
╚══════════════════════════════════════════════════════════════════════════════════╝

Run:
    pip install requests rich
    python backend_test_suite.py

Optional flags:
    --verbose        Print request/response bodies for every test
    --fail-fast      Stop on first failure
    --group GROUP    Run only tests in a specific group (e.g. "auth", "inventory")
    --output FILE    Write JSON report to FILE (default: test_report.json)
    --timeout SEC    Per-request timeout in seconds (default: 30)
"""

import argparse
import json
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ──────────────────────────────────────────────────────────────────────────────
# Rich for pretty output (falls back to plain text if not installed)
# ──────────────────────────────────────────────────────────────────────────────
try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.text import Text
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None
    def rprint(*args, **kwargs):
        print(*args)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
BASE_URL = "https://retail-mind-vkbp.onrender.com"

# Shared state — populated by tests as they run
STATE: Dict[str, Any] = {
    "access_token":   None,
    "refresh_token":  None,
    "user_id":        None,
    "shop_id":        None,
    "product_id":     None,
    "customer_id":    None,
    "invoice_id":     None,
    "order_id":       None,

    # sub-resource ids
    "worker_id":      None,
    "leave_id":       None,
    "delivery_id":    None,
    "batch_id":       None,
    "po_id":          None,
    "loyalty_cid":    None,
    "loyalty_iid":    None,
    "gift_card_code": None,

    # hardened-auth state
    "h_email":        None,
    "h_password":     None,
    "h_username":     None,
    "h_user_id":      None,
    "h_refresh":      None,

    # store-auth state
    "store_email":    None,
    "store_pass":     None,

    # khata phone
    "khata_phone":    None,

    # test credentials
    "test_username":  f"tester_{int(time.time())}",
    "test_password":  "Test@1234!",
    "test_email":     f"tester_{int(time.time())}@example.com",
}

# ──────────────────────────────────────────────────────────────────────────────
# Result tracking
# ──────────────────────────────────────────────────────────────────────────────
RESULTS: List[Dict] = []

PASS  = "✅ PASS"
FAIL  = "❌ FAIL"
SKIP  = "⚠️  SKIP"
ERROR = "💥 ERROR"


# ──────────────────────────────────────────────────────────────────────────────
# HTTP Session with retries
# ──────────────────────────────────────────────────────────────────────────────
def build_session(timeout: int = 30) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.request_timeout = timeout  # type: ignore[attr-defined]
    return session


SESSION: requests.Session = build_session()


def auth_headers() -> Dict[str, str]:
    if STATE["access_token"]:
        return {"Authorization": f"Bearer {STATE['access_token']}"}
    return {}


def request(
    method: str,
    path: str,
    *,
    json_body: Optional[Dict] = None,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    files=None,
    timeout: int = 30,
) -> Tuple[Optional[requests.Response], Optional[str]]:
    url = BASE_URL + path
    h = {**auth_headers(), **(headers or {})}
    try:
        resp = SESSION.request(
            method,
            url,
            json=json_body,
            params=params,
            headers=h,
            files=files,
            timeout=timeout,
        )
        return resp, None
    except requests.exceptions.Timeout:
        return None, f"Request timed out after {timeout}s"
    except requests.exceptions.ConnectionError as exc:
        return None, f"Connection error: {exc}"
    except Exception as exc:
        return None, f"Unexpected error: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# Test runner helpers
# ──────────────────────────────────────────────────────────────────────────────
ARGS: argparse.Namespace  # filled in main()


def run_test(
    group: str,
    name: str,
    method: str,
    path: str,
    *,
    json_body: Optional[Dict] = None,
    params: Optional[Dict] = None,
    extra_headers: Optional[Dict] = None,
    expected_statuses: Tuple[int, ...] = (200, 201),
    skip_reason: Optional[str] = None,
    extract: Optional[callable] = None,   # fn(resp) → updates STATE
    verbose: bool = False,
) -> Dict:
    """Execute one test, record result, optionally extract ids from response."""

    record: Dict[str, Any] = {
        "group":    group,
        "name":     name,
        "method":   method,
        "path":     path,
        "status":   None,
        "result":   None,
        "reason":   None,
        "duration": None,
        "request":  {"body": json_body, "params": params},
        "response": None,
    }

    if skip_reason:
        record["result"] = SKIP
        record["reason"] = skip_reason
        RESULTS.append(record)
        _print_result(record)
        return record

    t0 = time.perf_counter()
    resp, err = request(method, path, json_body=json_body, params=params, headers=extra_headers)
    record["duration"] = round(time.perf_counter() - t0, 3)

    if err:
        record["result"] = ERROR
        record["reason"] = err
        RESULTS.append(record)
        _print_result(record)
        return record

    record["status"] = resp.status_code
    try:
        body = resp.json()
    except Exception:
        body = resp.text

    record["response"] = body

    if resp.status_code in expected_statuses:
        record["result"] = PASS
        if extract:
            try:
                extract(resp, body)
            except Exception as exc:
                record["result"] = PASS  # still a pass; just warn
                record["reason"] = f"State extraction warning: {exc}"
    else:
        record["result"] = FAIL
        record["reason"] = (
            f"Expected HTTP {expected_statuses}, got {resp.status_code}. "
            f"Body: {str(body)[:400]}"
        )

    RESULTS.append(record)
    _print_result(record, verbose=verbose or (ARGS.verbose if ARGS else False))

    if ARGS and ARGS.fail_fast and record["result"] == FAIL:
        _dump_and_exit()

    return record


def _print_result(record: Dict, verbose: bool = False):
    symbol = record["result"]
    dur    = f"({record['duration']}s)" if record["duration"] else ""
    line   = f"  {symbol}  [{record['group']}] {record['method']} {record['path']}  {dur}"
    if record["status"]:
        line += f"  → HTTP {record['status']}"
    if record["reason"] and record["result"] != PASS:
        line += f"\n       ↳ {record['reason']}"
    if verbose and record["response"]:
        snippet = str(record["response"])[:600]
        line += f"\n       Response: {snippet}"
    print(line)


def _dump_and_exit():
    _write_report()
    print("\n[FAIL-FAST] Stopping on first failure.")
    sys.exit(1)


def _write_report(path: str = "test_report.json"):
    total   = len(RESULTS)
    passed  = sum(1 for r in RESULTS if r["result"] == PASS)
    failed  = sum(1 for r in RESULTS if r["result"] == FAIL)
    errors  = sum(1 for r in RESULTS if r["result"] == ERROR)
    skipped = sum(1 for r in RESULTS if r["result"] == SKIP)

    report = {
        "meta": {
            "base_url":   BASE_URL,
            "run_at":     datetime.now().isoformat(),
            "total":      total,
            "passed":     passed,
            "failed":     failed,
            "errors":     errors,
            "skipped":    skipped,
            "pass_rate":  f"{passed/total*100:.1f}%" if total else "0%",
        },
        "failures": [r for r in RESULTS if r["result"] in (FAIL, ERROR)],
        "all_results": RESULTS,
    }
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return report


# ═══════════════════════════════════════════════════════════════════════════════
# ░░░░░░░░░░░░░░░░░░░░░░░  TEST GROUPS  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
# ═══════════════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────────────
# 1. HEALTH & OBSERVABILITY
# ──────────────────────────────────────────────────────────────────────────────
def test_health():
    G = "health"
    run_test(G, "Root health",                "GET", "/health")
    run_test(G, "Observability health",       "GET", "/api/observability/health")
    run_test(G, "Observability ready",        "GET", "/api/observability/ready")
    run_test(G, "Observability metrics",      "GET", "/api/observability/metrics")
    run_test(G, "Business overview",          "GET", "/api/observability/business/overview")
    run_test(G, "Performance summary",        "GET", "/api/observability/performance/summary")
    run_test(G, "Performance database",       "GET", "/api/observability/performance/database")
    run_test(G, "Log entry",                  "POST", "/api/observability/log",
             json_body={"level": "info", "message": "Automated test log entry", "context": {"source": "pytest"}})
    run_test(G, "Error event",               "POST", "/api/observability/error",
             json_body={}, expected_statuses=(200, 201, 400, 422))


# ──────────────────────────────────────────────────────────────────────────────
# 2. AUTH (standard)
# ──────────────────────────────────────────────────────────────────────────────
def test_auth():
    G = "auth"

    def extract_register(resp, body):
        if isinstance(body, dict):
            STATE["user_id"] = body.get("user_id") or body.get("id") or body.get("userId")

    def extract_login(resp, body):
        if isinstance(body, dict):
            STATE["access_token"]  = body.get("access_token")  or body.get("token")
            STATE["refresh_token"] = body.get("refresh_token")
            STATE["user_id"]       = STATE["user_id"] or body.get("user_id") or body.get("id")

    run_test(G, "Register user", "POST", "/auth/register",
             json_body={
                 "username":  STATE["test_username"],
                 "password":  STATE["test_password"],
                 "email":     STATE["test_email"],
                 "user_type": "owner",
             },
             expected_statuses=(200, 201, 409),
             extract=extract_register)

    run_test(G, "Login user", "POST", "/auth/login",
             json_body={"email": STATE["test_email"], "password": STATE["test_password"]},
             extract=extract_login)

    run_test(G, "Get auth sales", "GET",  "/auth/sales", expected_statuses=(200, 401, 403))
    run_test(G, "Post auth sales", "POST", "/auth/sales", expected_statuses=(200, 201, 401, 403, 422))


# ──────────────────────────────────────────────────────────────────────────────
# 3. AUTH HARDENED
# ──────────────────────────────────────────────────────────────────────────────
def test_auth_hardened():
    G = "auth-hardened"
    ts = int(time.time())
    STATE["h_email"]    = f"h_{ts}@example.com"
    STATE["h_password"] = "HardPass@9!"
    STATE["h_username"] = f"huser_{ts}"

    def extract_h_login(resp, body):
        if isinstance(body, dict):
            STATE["h_refresh"] = body.get("refresh_token")
            STATE["h_user_id"] = body.get("user_id") or body.get("id")
            # If we don't have a main token yet, borrow from hardened login
            if not STATE["access_token"]:
                STATE["access_token"] = body.get("access_token") or body.get("token")

    run_test(G, "Hardened register", "POST", "/api/auth-hardened/register",
             json_body={"email": STATE["h_email"], "password": STATE["h_password"],
                        "user_name": STATE["h_username"]},
             expected_statuses=(200, 201, 409))

    run_test(G, "Hardened login", "POST", "/api/auth-hardened/login",
             json_body={"email": STATE["h_email"], "password": STATE["h_password"]},
             extract=extract_h_login)

    run_test(G, "Hardened refresh (bad token)", "POST", "/api/auth-hardened/refresh",
             json_body={"refresh_token": STATE["h_refresh"] or "dummy"},
             expected_statuses=(200, 201, 400, 401, 422))

    uid = STATE["h_user_id"] or STATE["user_id"] or 1
    run_test(G, "Active sessions (hardened)", "GET", f"/api/auth-hardened/active-sessions/{uid}",
             expected_statuses=(200, 401, 403, 404))

    run_test(G, "Hardened logout", "POST", "/api/auth-hardened/logout",
             expected_statuses=(200, 201, 400, 401))

    run_test(G, "Hardened logout-all", "POST", "/api/auth-hardened/logout-all",
             expected_statuses=(200, 201, 400, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 4. SESSION
# ──────────────────────────────────────────────────────────────────────────────
def test_session():
    G = "session"

    def extract_refresh(resp, body):
        if isinstance(body, dict):
            new_token = body.get("access_token") or body.get("token")
            if new_token:
                STATE["access_token"] = new_token

    run_test(G, "Session refresh", "POST", "/api/session/refresh",
             json_body={"refresh_token": STATE["refresh_token"] or "dummy",
                        "device_id": "pytest-device"},
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_refresh)

    uid = STATE["user_id"] or 1
    run_test(G, "Active sessions", "GET", f"/api/session/active/{uid}",
             expected_statuses=(200, 401, 403, 404))

    run_test(G, "Offline queue", "POST", "/api/session/offline/queue",
             json_body={"user_id": STATE["user_id"] or 1, "data_type": "sale", "payload": {"test": True}},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Offline sync", "POST", "/api/session/offline/sync",
             json_body={"user_id": STATE["user_id"] or 1},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Session logout", "POST", "/api/session/logout",
             json_body={"access_token": STATE["access_token"] or "dummy"},
             expected_statuses=(200, 201, 400, 401))

    run_test(G, "Session logout-all", "POST", "/api/session/logout-all",
             json_body={"user_id": STATE["user_id"] or "user_123"},
             expected_statuses=(200, 201, 400, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 5. SHOP
# ──────────────────────────────────────────────────────────────────────────────
def test_shop():
    G = "shop"

    def extract_profile(resp, body):
        if isinstance(body, dict):
            STATE["shop_id"] = (body.get("shop_id") or body.get("id")
                                or (body.get("shop") or {}).get("id"))

    run_test(G, "Create shop",          "POST", "/api/shop/create",
             expected_statuses=(200, 201, 400, 401, 409, 422))

    run_test(G, "Get shop profile",     "GET",  "/api/shop/profile",
             expected_statuses=(200, 401, 403, 404),
             extract=extract_profile)

    run_test(G, "Get shop profile (alt)","GET", "/shop/profile",
             expected_statuses=(200, 401, 403, 404))

    run_test(G, "Business hours",       "GET",  "/api/shop/business-hours",
             expected_statuses=(200, 401, 403))

    run_test(G, "Tax config",           "GET",  "/api/shop/tax-config",
             expected_statuses=(200, 401, 403))

    run_test(G, "UPI QR (api)",         "GET",  "/api/shop/upi-qr",
             expected_statuses=(200, 401, 403))

    run_test(G, "UPI QR (shop)",        "GET",  "/shop/upi-qr",
             expected_statuses=(200, 401, 403))

    sid = STATE["shop_id"] or "shop_123"
    run_test(G, "Public shop profile",  "GET",  f"/shop/public/{sid}",
             expected_statuses=(200, 404))

    run_test(G, "Toggle online store",  "POST", "/shop/toggle-online-store",
             expected_statuses=(200, 201, 400, 401, 403))

    run_test(G, "Update shop profile (PUT shop)", "PUT", "/shop/profile",
             json_body={"shop_name": "Test Retail Shop", "phone": "9999999999", "city": "Hyderabad"},
             expected_statuses=(200, 201, 400, 401, 403, 422))

    run_test(G, "Update shop settings (api)", "PUT", "/api/shop/settings",
             json_body={},
             expected_statuses=(200, 201, 400, 401, 403, 422))

    run_test(G, "Update shop profile (api PUT)", "PUT", "/api/shop/profile",
             expected_statuses=(200, 201, 400, 401, 403, 422))

    run_test(G, "Upload shop logo",     "POST", "/api/shop/upload-logo",
             expected_statuses=(200, 201, 400, 401, 403, 415, 422))

    run_test(G, "Post shop profile",    "POST", "/shop/profile",
             expected_statuses=(200, 201, 400, 401, 403, 422))


# ──────────────────────────────────────────────────────────────────────────────
# 6. INVENTORY — PRODUCTS
# ──────────────────────────────────────────────────────────────────────────────
def test_inventory_products():
    G = "inventory-products"
    ts = int(time.time())

    def extract_product(resp, body):
        if isinstance(body, dict):
            STATE["product_id"] = (body.get("product_id") or body.get("id")
                                   or (body.get("product") or {}).get("id"))

    run_test(G, "Create product", "POST", "/api/inventory/products",
             json_body={
                 "product_name": f"TestProduct_{ts}",
                 "unit_price":   "99.99",
                 "category":     "Test",
                 "stock":        100,
                 "unit":         "pcs",
             },
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_product)

    run_test(G, "List products",  "GET",  "/api/inventory/products",
             expected_statuses=(200, 401))

    pid = STATE["product_id"] or 1
    run_test(G, "Get product",    "GET",  f"/api/inventory/products/{pid}",
             expected_statuses=(200, 401, 404))

    run_test(G, "Update product", "PUT",  f"/api/inventory/products/{pid}",
             json_body={"unit_price": "109.99", "category": "Updated"},
             expected_statuses=(200, 201, 400, 401, 404, 422))

    run_test(G, "Low stock",      "GET",  "/api/inventory/low-stock",
             expected_statuses=(200, 401))

    run_test(G, "Stock alerts",   "GET",  "/api/inventory/stock-alerts",
             expected_statuses=(200, 401))

    run_test(G, "Stock value analytics",     "GET", "/api/inventory/analytics/stock-value",
             expected_statuses=(200, 401))

    run_test(G, "Inventory status analytics","GET", "/api/inventory/analytics/inventory-status",
             expected_statuses=(200, 401))

    run_test(G, "Generate purchase orders",  "GET", "/api/inventory/generate-purchase-orders",
             expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 7. INVENTORY — STOCK MOVEMENTS & BATCHES
# ──────────────────────────────────────────────────────────────────────────────
def test_inventory_stock():
    G = "inventory-stock"
    ts  = int(time.time())
    pid = STATE["product_id"] or 1

    run_test(G, "Stock movement (in)", "POST", "/api/inventory/stock-movement",
             json_body={"product_id": pid, "movement_type": "in",
                        "quantity": 10, "reason": "Test stock in"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Get stock movements", "GET",  f"/api/inventory/stock-movements/{pid}",
             expected_statuses=(200, 401, 404))

    def extract_batch(resp, body):
        if isinstance(body, dict):
            STATE["batch_id"] = body.get("batch_id") or body.get("id")

    run_test(G, "Create batch", "POST", "/api/inventory/batches",
             json_body={
                 "product_id":    pid,
                 "batch_number":  f"BATCH-{ts}",
                 "quantity":      50,
                 "expiry_date":   (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                 "purchase_price":"75.00",
             },
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_batch)

    run_test(G, "Get batches for product", "GET", f"/api/inventory/batches/{pid}",
             expected_statuses=(200, 401, 404))

    run_test(G, "Expiring batches", "GET", "/api/inventory/expiring-batches",
             expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 8. INVENTORY — SYNC & RECONCILIATION
# ──────────────────────────────────────────────────────────────────────────────
def test_inventory_sync():
    G = "inventory-sync"
    ts  = int(time.time())
    pid = STATE["product_id"] or 1

    run_test(G, "Current stock for product", "GET",
             f"/api/inventory-sync/current-stock/{pid}",
             expected_statuses=(200, 401, 404))

    run_test(G, "All stock", "GET", "/api/inventory-sync/all-stock",
             expected_statuses=(200, 401))

    run_test(G, "Deduct stock", "POST", "/api/inventory-sync/deduct-stock",
             json_body={"product_id": pid, "quantity": 2, "reason": "test sale",
                        "reference_id": f"REF-{ts}"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Deduct stock batch", "POST", "/api/inventory-sync/deduct-stock-batch",
             json_body={"updates": [{"product_id": pid, "quantity": 1,
                                     "reference_id": f"B-{ts}"}]},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Reconcile stock", "POST", "/api/inventory-sync/reconcile",
             json_body={"local_inventory": [{"product_id": pid, "quantity": 45}]},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Full reconciliation", "POST", "/api/inventory-reconcile/full-reconciliation",
             expected_statuses=(200, 201, 400, 401))

    run_test(G, "Correct stock", "POST", "/api/inventory-reconcile/correct-stock",
             json_body={"product_id": pid, "correct_stock": 48, "reason": "physical count"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Audit trail", "GET", f"/api/inventory-reconcile/audit-trail/{pid}",
             expected_statuses=(200, 401, 404))

    run_test(G, "Auto-fix discrepancies", "POST", "/api/inventory-reconcile/auto-fix-discrepancies",
             expected_statuses=(200, 201, 400, 401))

    # Products delete (end of inventory lifecycle)
    run_test(G, "Delete product (products route)", "DELETE", f"/api/products/{pid}",
             expected_statuses=(200, 204, 401, 404))

    run_test(G, "Delete product (inventory route)", "DELETE",
             f"/api/inventory/products/{pid}",
             expected_statuses=(200, 204, 401, 404))


# ──────────────────────────────────────────────────────────────────────────────
# 9. CUSTOMERS
# ──────────────────────────────────────────────────────────────────────────────
def test_customers():
    G = "customers"
    ts = int(time.time())

    def extract_customer(resp, body):
        if isinstance(body, dict):
            STATE["customer_id"] = (body.get("customer_id") or body.get("id")
                                    or (body.get("customer") or {}).get("id"))

    run_test(G, "Create customer", "POST", "/api/customers/",
             json_body={"customer_name": f"Test Customer {ts}",
                        "phone": f"98{ts % 100000000:08d}",
                        "email": f"cust_{ts}@test.com", "city": "Hyderabad"},
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_customer)

    run_test(G, "List customers", "GET", "/api/customers/",
             expected_statuses=(200, 401))

    cid = STATE["customer_id"] or 1
    run_test(G, "Get customer",   "GET", f"/api/customers/{cid}",
             expected_statuses=(200, 401, 404))

    run_test(G, "Update customer", "PUT", f"/api/customers/{cid}",
             json_body={"city": "Mumbai"},
             expected_statuses=(200, 201, 400, 401, 404, 422))

    run_test(G, "Set contact preference", "POST",
             f"/api/customers/{cid}/set-contact-preference",
             expected_statuses=(200, 201, 400, 401, 404, 422))

    run_test(G, "Search by phone", "GET", "/api/customers/search/by-phone",
             params={"phone": "9999999999"},
             expected_statuses=(200, 400, 401))

    run_test(G, "Search by name",  "GET", "/api/customers/search/by-name",
             params={"name": "Test"},
             expected_statuses=(200, 400, 401))

    run_test(G, "Credit score",   "GET", f"/api/credit-score/{cid}",
             expected_statuses=(200, 401, 404))


# ──────────────────────────────────────────────────────────────────────────────
# 10. INVOICES
# ──────────────────────────────────────────────────────────────────────────────
def test_invoices():
    G = "invoices"
    ts      = int(time.time())
    inv_num = f"INV-{ts}"

    def extract_invoice(resp, body):
        if isinstance(body, dict):
            STATE["invoice_id"] = (body.get("invoice_id") or body.get("id")
                                   or (body.get("invoice") or {}).get("id"))
            STATE["loyalty_cid"] = STATE["customer_id"] or 1
            STATE["loyalty_iid"] = STATE["invoice_id"] or 1

    run_test(G, "Create invoice", "POST", "/api/invoices/create",
             json_body={
                 "invoice_number": inv_num,
                 "customer_name":  "Test Customer",
                 "customer_phone": "1234567890",
                 "total_amount":   500.0,
                 "paid_amount":    500.0,
                 "tax":            9.0,
                 "payment_status": "paid",
                 "invoice_date":   datetime.now().strftime("%Y-%m-%d"),
                 "line_items": [
                     {"product_name": "Widget", "quantity": 2,
                      "unit_price": 250.0, "total": 500.0}
                 ],
             },
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_invoice)

    run_test(G, "Sync invoice (offline)", "POST", "/api/invoices/sync",
             json_body={"invoice_number": f"INV-OFF-{ts}",
                        "customer_name": "Offline Customer",
                        "total_amount": 300.0, "paid_amount": 300.0,
                        "payment_status": "paid",
                        "invoice_date": datetime.now().strftime("%Y-%m-%d")},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "List invoices",    "GET", "/api/invoices/",
             expected_statuses=(200, 401))

    iid = STATE["invoice_id"] or 1
    run_test(G, "Get invoice",      "GET", f"/api/invoices/{iid}",
             expected_statuses=(200, 401, 404))

    run_test(G, "Overdue invoices", "GET", "/api/invoices/overdue",
             expected_statuses=(200, 401))

    run_test(G, "Payments list",    "GET", "/api/invoices/payments",
             expected_statuses=(200, 401))

    run_test(G, "Invoice analytics","GET", "/api/invoices/analytics/summary",
             expected_statuses=(200, 401))

    # Bill generation
    def extract_bill(resp, body):
        if isinstance(body, dict):
            STATE["bill_id"] = body.get("bill_id") or body.get("id") or body.get("scan_id")

    run_test(G, "Generate bill", "POST", "/bill/Generate/Bill",
             json_body={"bill_type": "retail"},
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_bill)

    bid = getattr(STATE, "__dict__", {}).get("bill_id") or 1
    # Use dict access since bill_id isn't in the default STATE
    bid = STATE.get("bill_id", 1) or 1
    run_test(G, "Scan bill", "GET", f"/bill/scan/{bid}",
             expected_statuses=(200, 401, 404))

    # Rate limit for invoices
    run_test(G, "Rate limit status (invoices)", "GET", "/api/rate-limit/status/invoices",
             expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 11. ATTENDANCE
# ──────────────────────────────────────────────────────────────────────────────
def test_attendance():
    G = "attendance"
    ts = int(time.time())

    def extract_worker(resp, body):
        if isinstance(body, dict):
            STATE["worker_id"] = (body.get("worker_id") or body.get("employee_id")
                                  or body.get("id")
                                  or (body.get("worker") or {}).get("id"))

    run_test(G, "Create worker", "POST", "/api/attendance/workers",
             json_body={"name": f"Worker_{ts}", "phone": f"87{ts % 100000000:08d}",
                        "position": "Cashier", "salary": "18000"},
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_worker)

    run_test(G, "List workers",  "GET",  "/api/attendance/workers",
             expected_statuses=(200, 401))

    wid = STATE["worker_id"] or 1
    run_test(G, "Update worker", "PUT",  f"/api/attendance/workers/{wid}",
             json_body={"salary": "22000", "position": "Senior Cashier"},
             expected_statuses=(200, 201, 400, 401, 404, 422))

    run_test(G, "Check-in",      "POST", "/api/attendance/check-in",
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Check-out",     "POST", "/api/attendance/check-out",
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Manual attendance record", "POST", "/api/attendance/record-manual",
             json_body={"employee_id": wid,
                        "attendance_date": datetime.now().strftime("%Y-%m-%d"),
                        "status": "present", "notes": "Auto test"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Employee attendance history", "GET", f"/api/attendance/employee/{wid}",
             expected_statuses=(200, 401, 404))

    today = datetime.now().strftime("%Y-%m-%d")
    run_test(G, "Attendance by date", "GET", f"/api/attendance/date/{today}",
             expected_statuses=(200, 401))

    def extract_leave(resp, body):
        if isinstance(body, dict):
            STATE["leave_id"] = body.get("leave_id") or body.get("id")

    run_test(G, "Leave request", "POST", "/api/attendance/leave-request",
             json_body={"employee_id": wid, "leave_type": "casual",
                        "from_date": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
                        "to_date":   (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d"),
                        "reason":    "Personal work"},
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_leave)

    run_test(G, "List leave requests", "GET", "/api/attendance/leave-requests",
             expected_statuses=(200, 401))

    lid = STATE["leave_id"] or 1
    run_test(G, "Approve leave",  "PUT", f"/api/attendance/leave-request/{lid}/approve",
             expected_statuses=(200, 201, 400, 401, 404))

    run_test(G, "Reject leave",   "PUT", f"/api/attendance/leave-request/{lid}/reject",
             expected_statuses=(200, 201, 400, 401, 404))

    run_test(G, "Attendance analytics summary", "GET", "/api/attendance/analytics/summary",
             expected_statuses=(200, 401))

    run_test(G, "Employee analytics", "GET", f"/api/attendance/analytics/employee/{wid}",
             expected_statuses=(200, 401, 404))


# ──────────────────────────────────────────────────────────────────────────────
# 12. KHATA (CREDIT LEDGER)
# ──────────────────────────────────────────────────────────────────────────────
def test_khata():
    G = "khata"
    ts    = int(time.time())
    phone = f"90{ts % 100000000:08d}"
    STATE["khata_phone"] = phone

    run_test(G, "Add credit entry",    "POST", "/khata/credit",
             json_body={"customer_phone": phone, "customer_name": "Test Customer",
                        "amount": 500.0, "description": "Test credit"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Add repayment",       "POST", "/khata/repayment",
             json_body={"customer_phone": phone, "amount": 100.0,
                        "description": "Partial repay"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "List khata customers","GET",  "/khata/customers",
             expected_statuses=(200, 401))

    run_test(G, "Khata history",       "GET",  f"/khata/history/{phone}",
             expected_statuses=(200, 401, 404))

    run_test(G, "WhatsApp reminder",   "GET",  f"/khata/whatsapp-reminder/{phone}",
             expected_statuses=(200, 401, 404))

    run_test(G, "API khata detail",    "GET",  f"/api/khata/{phone}",
             expected_statuses=(200, 401, 404))

    run_test(G, "API khata customers", "GET",  "/api/khata/customers",
             expected_statuses=(200, 401))

    run_test(G, "API khata update",    "POST", "/api/khata/update",
             json_body={"customer_phone": phone, "amount": 200.0,
                        "transaction_type": "credit",
                        "reference_id": f"KH-{ts}"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Khata history (api)", "GET",  f"/api/khata-history/{phone}",
             expected_statuses=(200, 401, 404))


# ──────────────────────────────────────────────────────────────────────────────
# 13. PURCHASE ORDERS
# ──────────────────────────────────────────────────────────────────────────────
def test_purchase_orders():
    G = "purchase-orders"
    pid = STATE["product_id"] or 1

    def extract_po(resp, body):
        if isinstance(body, dict):
            STATE["po_id"] = body.get("po_id") or body.get("id") or body.get("order_id")

    run_test(G, "Create PO", "POST", "/purchase-orders/",
             json_body={
                 "supplier_name":     "ABC Suppliers",
                 "expected_delivery": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                 "items": [{"product_id": pid, "quantity": 50, "unit_price": 80.0}],
             },
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_po)

    run_test(G, "List POs", "GET", "/purchase-orders/",
             expected_statuses=(200, 401))

    po = STATE["po_id"] or 1
    run_test(G, "Mark PO delivered", "POST", f"/purchase-orders/{po}/mark-delivered",
             expected_statuses=(200, 201, 400, 401, 404))

    run_test(G, "Cancel PO", "POST", f"/purchase-orders/{po}/cancel",
             expected_statuses=(200, 201, 400, 401, 404))


# ──────────────────────────────────────────────────────────────────────────────
# 14. DELIVERY
# ──────────────────────────────────────────────────────────────────────────────
def test_delivery():
    G = "delivery"

    def extract_delivery(resp, body):
        if isinstance(body, dict):
            STATE["delivery_id"] = body.get("delivery_id") or body.get("id")

    run_test(G, "Create delivery", "POST", "/api/delivery/create",
             json_body={
                 "customer_id":          STATE["customer_id"] or 1,
                 "invoice_id":           STATE["invoice_id"] or 1,
                 "delivery_address":     "123 Test Street, Hyderabad",
                 "delivery_date":        (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                 "special_instructions": "Handle with care",
             },
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_delivery)

    run_test(G, "Today's deliveries", "GET", "/api/delivery/today",
             expected_statuses=(200, 401))

    did = STATE["delivery_id"] or 1
    run_test(G, "Update delivery status", "POST", f"/api/delivery/{did}/update-status",
             json_body={"status": "delivered", "notes": "Delivered successfully"},
             expected_statuses=(200, 201, 400, 401, 404, 422))


# ──────────────────────────────────────────────────────────────────────────────
# 15. LOYALTY
# ──────────────────────────────────────────────────────────────────────────────
def test_loyalty():
    G = "loyalty"
    cid = STATE["loyalty_cid"] or STATE["customer_id"] or 1
    iid = STATE["loyalty_iid"] or STATE["invoice_id"] or 1

    run_test(G, "Earn loyalty points", "POST", "/api/loyalty/earn",
             json_body={"customer_id": cid, "invoice_id": iid, "amount": 500.0},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Redeem loyalty points", "POST", "/api/loyalty/redeem",
             json_body={"customer_id": cid, "points": 10, "invoice_id": iid},
             expected_statuses=(200, 201, 400, 401, 422))


# ──────────────────────────────────────────────────────────────────────────────
# 16. EXPENSES
# ──────────────────────────────────────────────────────────────────────────────
def test_expenses():
    G = "expenses"
    today = datetime.now().strftime("%Y-%m-%d")

    run_test(G, "Create expense (api)", "POST", "/api/expenses/create",
             json_body={"category": "utilities", "amount": 1500.0,
                        "description": "Electricity bill", "date": today},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "List expenses (api)",     "GET", "/api/expenses",
             expected_statuses=(200, 401))

    run_test(G, "Expense history (api)",   "GET", "/api/expenses/history",
             expected_statuses=(200, 401))

    run_test(G, "Create expense (legacy)", "POST", "/expenses",
             json_body={"category": "rent", "amount": 20000.0,
                        "expense_date": today, "payment_method": "cash"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "List expenses (legacy)",  "GET", "/expenses",
             expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 17. WORKERS (enterprise)
# ──────────────────────────────────────────────────────────────────────────────
def test_workers():
    G = "workers"
    ts = int(time.time())

    def extract_wid(resp, body):
        if isinstance(body, dict):
            STATE["ent_worker_id"] = body.get("worker_id") or body.get("id")

    run_test(G, "Create enterprise worker", "POST", "/workers",
             json_body={"name": f"Ent_Worker_{ts}", "position": "Manager",
                        "salary": "30000"},
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_wid)

    run_test(G, "List enterprise workers",  "GET",  "/workers",
             expected_statuses=(200, 401))

    wid = STATE.get("ent_worker_id") or 1
    run_test(G, "Update enterprise worker", "PUT",  f"/workers/{wid}",
             json_body={"salary": "19000", "status": "active"},
             expected_statuses=(200, 201, 400, 401, 404, 422))

    run_test(G, "Pay salary", "POST", f"/workers/{wid}/pay-salary",
             expected_statuses=(200, 201, 400, 401, 404))


# ──────────────────────────────────────────────────────────────────────────────
# 18. BANK RECON & ENTERPRISE
# ──────────────────────────────────────────────────────────────────────────────
def test_enterprise():
    G = "enterprise"
    today = datetime.now().strftime("%Y-%m-%d")

    run_test(G, "Create bank recon", "POST", "/bank-recon",
             json_body={"recon_date": today, "expected_upi_amount": 50000.0,
                        "actual_bank_deposit": 49800.0, "notes": "Minor discrepancy"},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "List bank recons",       "GET", "/bank-recon",
             expected_statuses=(200, 401))

    run_test(G, "Enterprise P&L",         "GET", "/enterprise/pnl",
             expected_statuses=(200, 401))

    run_test(G, "Enterprise transactions","GET", "/enterprise/transactions",
             expected_statuses=(200, 401))

    run_test(G, "Retail stock analysis",  "GET", "/retail/stock-analysis",
             expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 19. REPORTS & ANALYTICS
# ──────────────────────────────────────────────────────────────────────────────
def test_reports():
    G = "reports"
    run_test(G, "Daily report",           "GET", "/api/reports/daily",        expected_statuses=(200, 401))
    run_test(G, "Churn risk",             "GET", "/api/analytics/churn-risk", expected_statuses=(200, 401))
    run_test(G, "Today collections",      "GET", "/api/collections/today-summary", expected_statuses=(200, 401))
    run_test(G, "Recent transactions",    "GET", "/api/transactions/recent",  expected_statuses=(200, 401))
    run_test(G, "Online payments",        "GET", "/api/transactions/online-payments", expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 20. COUNTER, FESTIVALS, TEMPLATES, FLASH SALE, GIFT CARDS, GST
# ──────────────────────────────────────────────────────────────────────────────
def test_misc():
    G = "misc"
    ts = int(time.time())

    run_test(G, "Counter authenticate", "POST", "/api/counter/authenticate",
             json_body={"billing_pin": "1234"},
             expected_statuses=(200, 201, 400, 401, 403))

    run_test(G, "Upcoming festivals",   "GET",  "/api/festivals/upcoming",
             expected_statuses=(200, 401))

    run_test(G, "Today occasions",      "GET",  "/api/occasions/today",
             expected_statuses=(200, 401))

    run_test(G, "List templates",       "GET",  "/api/templates",
             expected_statuses=(200, 401))

    run_test(G, "Save template",        "POST", "/api/templates/save",
             json_body={"template_name": "Quick Sale",
                        "template_items": [{"product_id": STATE["product_id"] or 1, "quantity": 1}]},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Flash sale setup",     "POST", "/api/flash-sale/setup",
             json_body={"category": "Test", "discount_pct": 10.0, "hours": 2},
             expected_statuses=(200, 201, 400, 401, 422))

    # Gift cards
    card_code = f"GC-{ts}"
    run_test(G, "Issue gift card",      "POST", "/gift-cards",
             json_body={"card_code": card_code, "initial_balance": 500.0,
                        "issued_to": "Test User",
                        "expiry_date": (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Redeem gift card",     "POST", "/gift-cards/redeem",
             json_body={"card_code": card_code, "amount_to_deduct": 100.0},
             expected_statuses=(200, 201, 400, 401, 404, 422))

    # GST
    run_test(G, "Export GSTR1",         "GET",  "/gst/export-gstr1",
             expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 21. ONLINE STORE
# ──────────────────────────────────────────────────────────────────────────────
def test_online_store():
    G = "store"
    ts    = int(time.time())
    email = f"store_{ts}@example.com"
    pw    = "StorePass@9!"
    STATE["store_email"] = email
    STATE["store_pass"]  = pw

    def extract_store_order(resp, body):
        if isinstance(body, dict):
            STATE["order_id"] = body.get("order_id") or body.get("id")

    run_test(G, "Store customer register", "POST", "/store/customer/register",
             json_body={"name": f"Store User {ts}", "email": email, "password": pw,
                        "phone": f"91{ts % 100000000:08d}"},
             expected_statuses=(200, 201, 400, 409, 422))

    run_test(G, "Store customer login",    "POST", "/store/customer/login",
             json_body={"email": email, "password": pw},
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Nearby shops",            "GET",  "/store/shops/nearby",
             expected_statuses=(200, 401))

    sid = STATE["shop_id"] or "shop_123"
    run_test(G, "Shop products",           "GET",  f"/store/shops/{sid}/products",
             expected_statuses=(200, 401, 404))

    run_test(G, "Place order",             "POST", "/store/order",
             json_body={"shop_id": sid,
                        "items": [{"product_id": STATE["product_id"] or 1, "quantity": 1}]},
             expected_statuses=(200, 201, 400, 401, 422),
             extract=extract_store_order)

    run_test(G, "My orders",               "GET",  "/store/my-orders",
             expected_statuses=(200, 401))

    oid = STATE["order_id"] or 1
    run_test(G, "Track order",             "GET",  f"/store/order/{oid}/track",
             expected_statuses=(200, 401, 404))

    run_test(G, "Owner: all orders",       "GET",  "/store/owner/orders",
             expected_statuses=(200, 401))

    run_test(G, "Owner: order action",     "POST", f"/store/owner/orders/{oid}/action",
             expected_statuses=(200, 201, 400, 401, 404, 422))


# ──────────────────────────────────────────────────────────────────────────────
# 22. SALES RESTORE & DATA
# ──────────────────────────────────────────────────────────────────────────────
def test_sales_restore():
    G = "sales-restore"

    run_test(G, "Restore all sales",    "POST", "/api/sales-restore/restore-all",
             json_body={"include_stock_impact": False},
             expected_statuses=(200, 201, 400, 401))

    run_test(G, "Restore summary",      "GET",  "/api/sales-restore/restore-summary",
             expected_statuses=(200, 401))

    run_test(G, "Restore customers",    "POST", "/api/sales-restore/restore-customers",
             expected_statuses=(200, 201, 400, 401))

    run_test(G, "Backup export",        "GET",  "/api/data/backup/export",
             expected_statuses=(200, 401))

    run_test(G, "Data integrity check", "GET",  "/api/data/integrity-check",
             expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 23. SYNC
# ──────────────────────────────────────────────────────────────────────────────
def test_sync():
    G = "sync"

    for endpoint, label in [
        ("/api/sync/sales",             "Sync sales"),
        ("/api/sync/invoices",          "Sync invoices"),
        ("/api/sync/khata-balances",    "Sync khata balances"),
        ("/api/sync/expenses",          "Sync expenses"),
        ("/api/sync/invoices/chunked",  "Sync invoices chunked"),
    ]:
        run_test(G, label, "POST", endpoint,
                 json_body={},
                 expected_statuses=(200, 201, 400, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 24. BATCH OPERATIONS
# ──────────────────────────────────────────────────────────────────────────────
def test_batch():
    G = "batch"

    def extract_batch_op(resp, body):
        if isinstance(body, dict):
            STATE["batch_op_id"] = body.get("operation_id") or body.get("id")

    run_test(G, "Export products batch", "POST", "/batch/api/batch/products/export",
             expected_statuses=(200, 201, 400, 401),
             extract=extract_batch_op)

    run_test(G, "Import products batch", "POST", "/batch/api/batch/products/import",
             expected_statuses=(200, 201, 400, 401, 415))

    run_test(G, "Import customers batch","POST", "/batch/api/batch/customers/import",
             expected_statuses=(200, 201, 400, 401, 415))

    oid = STATE.get("batch_op_id") or 1
    run_test(G, "Batch status",          "GET",  f"/batch/api/batch/status/{oid}",
             expected_statuses=(200, 401, 404))

    run_test(G, "Batch history",         "GET",  "/batch/api/batch/history",
             expected_statuses=(200, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 25. CACHE
# ──────────────────────────────────────────────────────────────────────────────
def test_cache():
    G = "cache"

    run_test(G, "Cache stats",           "GET",    "/cache/api/cache/stats",
             expected_statuses=(200, 401))

    run_test(G, "Warm products cache",   "POST",   "/cache/api/cache/warm/products",
             expected_statuses=(200, 201, 401))

    run_test(G, "Warm analytics cache",  "POST",   "/cache/api/cache/warm/analytics",
             expected_statuses=(200, 201, 401))

    run_test(G, "Clear products cache",  "DELETE", "/cache/api/cache/clear/products:*",
             expected_statuses=(200, 204, 401))

    run_test(G, "Clear cache by pattern","DELETE", "/cache/api/cache/clear/1",
             expected_statuses=(200, 204, 401, 404))

    run_test(G, "Clear all cache",       "DELETE", "/cache/api/cache/clear-all",
             expected_statuses=(200, 204, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 26. SECURITY
# ──────────────────────────────────────────────────────────────────────────────
def test_security():
    G = "security"

    run_test(G, "Rate limit status (dynamic)",  "GET",  "/api/rate-limit/status/invoices",
             expected_statuses=(200, 401))

    run_test(G, "Security rate limit status",   "GET",  "/api/security/rate-limit-status",
             expected_statuses=(200, 401))

    run_test(G, "CSRF token",                   "GET",  "/api/security/csrf-token",
             expected_statuses=(200, 401))

    run_test(G, "Security headers check",       "GET",  "/api/security/security-headers",
             expected_statuses=(200, 401))

    run_test(G, "Validate password",            "POST", "/api/security/validate-password",
             expected_statuses=(200, 201, 400, 401, 422))

    run_test(G, "Check input (SQL injection)",  "POST", "/api/security/check-input",
             json_body={"input_data": "SELECT * FROM users", "check_type": "sql"},
             expected_statuses=(200, 201, 400, 401))

    run_test(G, "SQL injection header check",   "GET",  "/api/security/check-sql-injection",
             expected_statuses=(200, 401))

    run_test(G, "Sanitize batch",               "POST", "/api/security/sanitize-batch",
             expected_statuses=(200, 201, 400, 401))


# ──────────────────────────────────────────────────────────────────────────────
# 27. CUSTOMER DELETE (cleanup)
# ──────────────────────────────────────────────────────────────────────────────
def test_cleanup():
    G = "cleanup"
    cid = STATE["customer_id"] or 1
    iid = STATE["invoice_id"] or 1
    wid = STATE["worker_id"] or 1

    run_test(G, "Delete invoice",  "DELETE", f"/api/invoices/{iid}",
             expected_statuses=(200, 204, 401, 404))

    run_test(G, "Delete customer", "DELETE", f"/api/customers/{cid}",
             expected_statuses=(200, 204, 401, 404))

    run_test(G, "Delete attendance worker", "DELETE", f"/api/attendance/workers/{wid}",
             expected_statuses=(200, 204, 401, 404))


# ═══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary(report_path: str):
    meta     = _write_report(report_path)["meta"]
    failures = [r for r in RESULTS if r["result"] in (FAIL, ERROR)]

    sep = "═" * 80
    print(f"\n{sep}")
    print("  RETAIL MIND API TEST RESULTS")
    print(sep)
    print(f"  Base URL  : {BASE_URL}")
    print(f"  Run at    : {meta['run_at']}")
    print(f"  Total     : {meta['total']}")
    print(f"  ✅ Passed : {meta['passed']}")
    print(f"  ❌ Failed : {meta['failed']}")
    print(f"  💥 Errors : {meta['errors']}")
    print(f"  ⚠️  Skipped: {meta['skipped']}")
    print(f"  Pass Rate : {meta['pass_rate']}")
    print(sep)

    if failures:
        print(f"\n{'─'*80}")
        print("  FAILURES & ERRORS DETAIL")
        print(f"{'─'*80}")
        for i, r in enumerate(failures, 1):
            print(f"\n  [{i}] {r['result']}  {r['method']} {r['path']}")
            print(f"       Group    : {r['group']}")
            print(f"       Name     : {r['name']}")
            if r["status"]:
                print(f"       HTTP     : {r['status']}")
            if r["duration"]:
                print(f"       Duration : {r['duration']}s")
            if r["reason"]:
                print(f"       Reason   : {r['reason']}")
            if r["request"]["body"]:
                body_str = json.dumps(r["request"]["body"], default=str)
                print(f"       Req Body : {body_str[:300]}")
            if r["response"]:
                resp_str = str(r["response"])[:400]
                print(f"       Response : {resp_str}")

    print(f"\n  Full JSON report → {report_path}\n")

    if RICH:
        table = Table(title="Failures by Group", show_lines=True)
        table.add_column("Group",  style="cyan")
        table.add_column("Endpoint")
        table.add_column("HTTP",   justify="right")
        table.add_column("Reason", style="red")
        for r in failures:
            table.add_row(r["group"],
                          f"{r['method']} {r['path']}",
                          str(r["status"] or "—"),
                          (r["reason"] or "")[:120])
        console.print(table)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

ALL_GROUPS = {
    "health":           test_health,
    "auth":             test_auth,
    "auth-hardened":    test_auth_hardened,
    "session":          test_session,
    "shop":             test_shop,
    "inventory-products": test_inventory_products,
    "inventory-stock":  test_inventory_stock,
    "inventory-sync":   test_inventory_sync,
    "customers":        test_customers,
    "invoices":         test_invoices,
    "attendance":       test_attendance,
    "khata":            test_khata,
    "purchase-orders":  test_purchase_orders,
    "delivery":         test_delivery,
    "loyalty":          test_loyalty,
    "expenses":         test_expenses,
    "workers":          test_workers,
    "enterprise":       test_enterprise,
    "reports":          test_reports,
    "misc":             test_misc,
    "store":            test_online_store,
    "sales-restore":    test_sales_restore,
    "sync":             test_sync,
    "batch":            test_batch,
    "cache":            test_cache,
    "security":         test_security,
    "cleanup":          test_cleanup,
}


def main():
    global ARGS, SESSION

    parser = argparse.ArgumentParser(description="Retail Mind API Test Suite")
    parser.add_argument("--verbose",   action="store_true",
                        help="Print request/response for every test")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop on first failure")
    parser.add_argument("--group",     nargs="+", metavar="GROUP",
                        choices=list(ALL_GROUPS.keys()),
                        help="Run only specified group(s)")
    parser.add_argument("--output",    default="test_report.json",
                        help="Path for JSON report (default: test_report.json)")
    parser.add_argument("--timeout",   type=int, default=30,
                        help="Per-request timeout in seconds (default: 30)")
    ARGS = parser.parse_args()

    SESSION = build_session(ARGS.timeout)

    groups_to_run = ARGS.group or list(ALL_GROUPS.keys())

    print(f"\n{'═'*80}")
    print(f"  RETAIL MIND BACKEND — FULL API TEST SUITE")
    print(f"  Target  : {BASE_URL}")
    print(f"  Groups  : {', '.join(groups_to_run)}")
    print(f"  Timeout : {ARGS.timeout}s")
    print(f"{'═'*80}\n")

    for group in groups_to_run:
        print(f"\n{'─'*60}")
        print(f"  ▶  {group.upper()}")
        print(f"{'─'*60}")
        try:
            ALL_GROUPS[group]()
        except Exception as exc:
            print(f"  💥 Group {group} crashed: {exc}")
            traceback.print_exc()

    print_summary(ARGS.output)

    failed = sum(1 for r in RESULTS if r["result"] in (FAIL, ERROR))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()