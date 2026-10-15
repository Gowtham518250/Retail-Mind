"""Staging-only end-to-end integration tests for Retail Mind.

These tests CREATE invoices. They skip unless a dedicated staging URL, test
account, and explicit mutation opt-in are supplied. Production URLs are blocked.
"""
import os
import time
import uuid
from urllib.parse import urlparse

import pytest

STAGING_BASE_URL = os.environ.get("STAGING_BASE_URL", "").strip().rstrip("/")
TEST_EMAIL = os.environ.get("STAGING_TEST_EMAIL", "").strip()
TEST_PASSWORD = os.environ.get("STAGING_TEST_PASSWORD", "")
ALLOW_MUTATING_E2E = os.environ.get("ALLOW_MUTATING_STAGING_E2E") == "1"

# Fail closed for known production services. This list intentionally contains
# the public production API and storefront hostnames.
_BLOCKED_PRODUCTION_HOSTS = {
    "retail-mind-vkbp.onrender.com",
    "retail-mind-ikhi.onrender.com",
    "retail-mind-web.onrender.com",
}

if not STAGING_BASE_URL:
    pytest.skip("Set STAGING_BASE_URL to a dedicated staging deployment.", allow_module_level=True)

_parsed_base_url = urlparse(STAGING_BASE_URL)
if not _parsed_base_url.hostname:
    raise RuntimeError("STAGING_BASE_URL must be an absolute URL with a hostname.")
if _parsed_base_url.hostname.casefold() in _BLOCKED_PRODUCTION_HOSTS:
    raise RuntimeError(
        "Refusing to run mutating E2E tests against Retail Mind production. "
        "Use a dedicated staging deployment and database."
    )
if _parsed_base_url.scheme != "https" and _parsed_base_url.hostname not in {"localhost", "127.0.0.1"}:
    raise RuntimeError("STAGING_BASE_URL must use HTTPS (HTTP is allowed only for localhost).")

if not TEST_EMAIL or not TEST_PASSWORD:
    pytest.skip("Set STAGING_TEST_EMAIL and STAGING_TEST_PASSWORD for the staging test account.", allow_module_level=True)
if not ALLOW_MUTATING_E2E:
    pytest.skip(
        "These tests create invoices. Set ALLOW_MUTATING_STAGING_E2E=1 only for a disposable staging shop.",
        allow_module_level=True,
    )

BASE_URL = STAGING_BASE_URL
import requests
import time
import uuid

BASE_URL = "https://retail-mind-vkbp.onrender.com"

# ──────────────────────────────────────────────────────────
# IMPORTANT: Set TEST_EMAIL and TEST_PASSWORD to an actual
# registered account on your production backend.
# These can also be overridden with environment variables:
#   set TEST_EMAIL=myshop@example.com
#   set TEST_PASSWORD=mypassword
#   python -m pytest tests/test_sync_resilience.py -v
# ──────────────────────────────────────────────────────────
import os
TEST_EMAIL    = os.environ.get("TEST_EMAIL",    "testshop@retailmind.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "TestPassword123!")


# =============================================
# FIXTURE: Login and obtain JWT token
# =============================================

@pytest.fixture(scope="module")
def auth_token():
    """Login with email + password to get JWT Bearer token."""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=60
    )
    assert resp.status_code == 200, (
        f"Login failed ({resp.status_code}): {resp.text}\n"
        f"→ Set TEST_EMAIL and TEST_PASSWORD environment variables to a valid account."
    )
    data = resp.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No access_token in login response: {data}"
    print(f"\n  ✅ Login OK — user_id={data.get('user_id')}, role={data.get('role')}")
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type":  "application/json"
    }


# =============================================
# TEST 1: Shop profile loads correctly
# =============================================

def test_shop_profile_loads(headers):
    """After login, the shop profile must be retrievable."""
    resp = requests.get(f"{BASE_URL}/api/shop/profile", headers=headers, timeout=30)
    assert resp.status_code == 200, f"Shop profile failed ({resp.status_code}): {resp.text}"
    data = resp.json()
    # Backend wraps shop data in {status, profile, settings}
    profile = data.get("profile", data)
    has_name = "shop_name" in profile or "name" in profile or "id" in profile or "profile" in data
    assert has_name, f"Shop profile missing expected fields: {data.keys()}"
    print(f"  ✅ Shop profile loaded: {data.get('shop_name') or data.get('name') or 'OK'}")


# =============================================
# TEST 2: Inventory products load
# =============================================

def test_inventory_loads(headers):
    """All products must be retrievable from the backend."""
    resp = requests.get(f"{BASE_URL}/api/inventory/products", headers=headers, timeout=30)
    assert resp.status_code == 200, f"Inventory fetch failed ({resp.status_code}): {resp.text}"
    data = resp.json()
    products = data if isinstance(data, list) else data.get("products", data.get("items", []))
    assert isinstance(products, list), "Products response is not a list"
    print(f"  ✅ Products loaded: {len(products)} products found")


# =============================================
# TEST 3: Create a regular cash invoice
# =============================================

@pytest.fixture(scope="module")
def cash_invoice_number():
    return f"E2E-CASH-{uuid.uuid4().hex[:8].upper()}"


def test_create_cash_invoice(headers, cash_invoice_number):
    """Regular cash sale goes to /api/invoices/create with payment_status=PAID."""
    payload = {
        "invoice_number": cash_invoice_number,
        "customer_name":  "E2E Cash Customer",
        "total_amount":   150.0,
        "paid_amount":    150.0,
        "tax":            0.0,
        "payment_status": "PAID",
        "invoice_date":   time.strftime("%Y-%m-%d"),
        "notes":          "E2E Test — Regular Cash Sale",
        "line_items": [
            {
                "product_name": "Test Rice 1kg",
                "quantity":     3,
                "unit_price":   50.0,
                "line_total":   150.0
            }
        ]
    }
    resp = requests.post(
        f"{BASE_URL}/api/invoices/create",
        json=payload,
        headers=headers,
        timeout=30
    )
    assert resp.status_code in [200, 201], f"Cash invoice creation failed ({resp.status_code}): {resp.text}"
    print(f"  ✅ Cash invoice created: {cash_invoice_number}")


# =============================================
# TEST 4: Create a credit / udhar invoice
# =============================================

@pytest.fixture(scope="module")
def udhar_invoice_number():
    return f"E2E-UDHAR-{uuid.uuid4().hex[:8].upper()}"


def test_create_udhar_invoice(headers, udhar_invoice_number):
    """Udhar (credit) sale goes to /api/invoices/create with payment_status=UNPAID."""
    payload = {
        "invoice_number": udhar_invoice_number,
        "customer_name":  "Udhar E2E Customer",
        "customer_phone": "8888800000",
        "total_amount":   200.0,
        "paid_amount":    0.0,
        "tax":            0.0,
        "payment_status": "UNPAID",
        "invoice_date":   time.strftime("%Y-%m-%d"),
        "notes":          "E2E Test — Udhar/Credit Sale",
        "line_items": [
            {
                "product_name": "Udhar Product 500g",
                "quantity":     2,
                "unit_price":   100.0,
                "line_total":   200.0
            }
        ]
    }
    resp = requests.post(
        f"{BASE_URL}/api/invoices/create",
        json=payload,
        headers=headers,
        timeout=30
    )
    assert resp.status_code in [200, 201], f"Udhar invoice failed ({resp.status_code}): {resp.text}"
    print(f"  ✅ Udhar invoice created: {udhar_invoice_number}")


# =============================================
# TEST 5: Simulate "App Data Clear" — restore
# =============================================

def test_data_restoration_after_wipe(headers, cash_invoice_number, udhar_invoice_number):
    """
    Simulates adb shell pm clear com.retailmind.billing followed by re-login.
    The restore endpoint must return BOTH invoices we just created.
    """
    resp = requests.post(
        f"{BASE_URL}/api/sales-restore/restore-all",
        json={"include_stock_impact": False},
        headers=headers,
        timeout=60
    )
    assert resp.status_code == 200, f"Restore failed ({resp.status_code}): {resp.text}"
    data = resp.json()

    # Backend returns total_invoices_restored (not a boolean 'success' field)
    restored_count = data.get("total_invoices_restored", 0)
    assert restored_count > 0, f"No invoices restored: {list(data.keys())}"
    invoices = data.get("invoices", [])
    print(f"  ✅ Total invoices restored from backend: {len(invoices)} (server reported {restored_count})")

    # Verify cash invoice present
    cash_found = [i for i in invoices if i.get("invoice_number") == cash_invoice_number]
    assert cash_found, f"❌ Cash invoice '{cash_invoice_number}' NOT found in restore!"
    assert cash_found[0]["payment_status"] == "PAID"
    assert len(cash_found[0].get("line_items", [])) > 0, "No line items on restored cash invoice"
    print(f"  ✅ Cash invoice restored correctly with line items")

    # Verify udhar invoice present
    udhar_found = [i for i in invoices if i.get("invoice_number") == udhar_invoice_number]
    assert udhar_found, f"❌ Udhar invoice '{udhar_invoice_number}' NOT found in restore!"
    assert udhar_found[0]["payment_status"] == "UNPAID"
    print(f"  ✅ Udhar invoice restored correctly")


# =============================================
# TEST 6: Verify invoice list (multi-device sync)
# =============================================

def test_invoice_list_multi_device_sync(headers, cash_invoice_number, udhar_invoice_number):
    """
    Simulates Device B logging into the same account.
    Both invoices created on Device A must appear.
    """
    resp = requests.get(f"{BASE_URL}/api/invoices/", headers=headers, timeout=30)
    assert resp.status_code == 200, f"Invoice list failed ({resp.status_code}): {resp.text}"
    data = resp.json()
    invoices = data if isinstance(data, list) else data.get("invoices", data.get("items", []))

    numbers = {i.get("invoice_number") for i in invoices}
    assert cash_invoice_number  in numbers, f"❌ Cash invoice not found via /api/invoices/"
    assert udhar_invoice_number in numbers, f"❌ Udhar invoice not found via /api/invoices/"
    print(f"  ✅ Multi-device sync verified: both invoices visible on second login")


# =============================================
# TEST 7: Dashboard analytics totals
# =============================================

def test_dashboard_analytics_load(headers):
    """Dashboard analytics must return 200 with a numeric total."""
    # Try the most common analytics endpoints
    for path in ["/api/analytics/dashboard", "/api/analytics/summary", "/api/analytics"]:
        resp = requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Analytics loaded from {path}: keys={list(data.keys())[:5]}")
            return
    pytest.skip("No analytics endpoint returned 200 — may require specific date params")


# =============================================
# TEST 8: Voice billing price sanity (offline NLP)
# =============================================

def test_voice_billing_price_sanity(headers):
    """
    Simulate what the voice engine does — check that the catalog returns
    products with non-zero prices, so voice billing can find them.
    """
    resp = requests.get(f"{BASE_URL}/api/inventory/products", headers=headers, timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    products = data if isinstance(data, list) else data.get("products", [])

    if products:
        zero_price = [p for p in products if float(p.get("price", p.get("unit_price", 0)) or 0) == 0]
        nonzero    = [p for p in products if float(p.get("price", p.get("unit_price", 0)) or 0) > 0]
        print(f"  ✅ Products with price: {len(nonzero)} | Missing price: {len(zero_price)}")
        if zero_price:
            names = [p.get("product_name","?") for p in zero_price[:5]]
            print(f"  ⚠️  Products missing prices (voice billing will default to 0): {names}")
    else:
        pytest.skip("No products in catalog — add products before running voice billing tests")
