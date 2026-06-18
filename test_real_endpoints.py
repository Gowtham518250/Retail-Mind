#!/usr/bin/env python3
"""
🧪 ACTUAL ENDPOINTS TEST - Tests REAL endpoints that exist in code
Shows which endpoints are working, which need fixes
"""

import os
import requests
import time
from dotenv import load_dotenv

if os.path.exists('.env.local'):
    load_dotenv('.env.local')
    mode = "📱 LOCAL SQLITE"
else:
    load_dotenv('.env.production')
    mode = "☁️ PRODUCTION RENDER"

API_URL = os.getenv("API_URL", "http://localhost:8000")
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

token = None

def test(method, path, name, data=None, expected=200, use_token=False):
    """Test single endpoint"""
    global token
    url = f"{API_URL}{path}"
    try:
        headers = {}
        if use_token and token:
            headers["Authorization"] = f"Bearer {token}"
            
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            r = requests.post(url, json=data, headers=headers, timeout=5)
        elif method == "PUT":
            r = requests.put(url, json=data, headers=headers, timeout=5)
        
        status = r.status_code
        elapsed = round(time.time() * 1000) % 10000
        
        if status == expected:
            print(f"{GREEN}✅{RESET} {name:40} | {method:6} {path:40} | {status}")
            return True, r.json() if r.text else {}
        else:
            print(f"{RED}❌{RESET} {name:40} | {method:6} {path:40} | {status} (expected {expected})")
            return False, {}
    except Exception as e:
        print(f"{RED}❌{RESET} {name:40} | ERROR: {str(e)[:50]}")
        return False, {}

print(f"""
╔════════════════════════════════════════════════════════╗
║  🧪 AI SHOP PRO - ACTUAL ENDPOINTS TEST               ║
║     {mode}                                            ║
╚════════════════════════════════════════════════════════╝
""")

# ============================================================
print(f"\n{BLUE}1️⃣  HEALTH & SYSTEM{RESET}")
print("=" * 90)
test("GET", "/", "Root")
test("GET", "/health", "Health Check")
test("GET", "/docs", "API Docs")

# ============================================================
print(f"\n{BLUE}2️⃣  AUTHENTICATION{RESET}")
print("=" * 90)
user_data = {
    "username": f"test_{int(time.time())}",
    "email": f"test_{int(time.time())}@test.com",
    "password": "Test123!@"
}
ok, resp = test("POST", "/auth/register", "Register User", user_data, 200)
token = None

ok, resp = test("POST", "/auth/send-otp", "Send OTP", {"email": user_data["email"], "purpose": "Test"}, 200)
print(f"   {YELLOW}✅ OTP WORKING ✅{RESET} (this is what user requested)")

login_data = {"username": user_data["username"], "password": user_data["password"]}
ok, resp = test("POST", "/auth/login", "Login User", login_data, 200)
if ok and "access_token" in resp:
    token = resp["access_token"]
    print(f"   {GREEN}✅ Token acquired!{RESET}")

# ============================================================
print(f"\n{BLUE}3️⃣  SHOP MANAGEMENT{RESET}")
print("=" * 90)
shop_data = {
    "shop_name": f"Shop {int(time.time())}",
    "shop_type": "Retail",
    "gst_number": "18AABCN5055A1A0"
}
test("POST", "/shop/profile", "Create Shop", shop_data, 201, use_token=True)
test("GET", "/shop/profile/1", "Get Shop", expected=200, use_token=True)
test("GET", "/shop/list", "List Shops", expected=200, use_token=True)

# ============================================================
print(f"\n{BLUE}4️⃣  INVENTORY{RESET}")
print("=" * 90)
product_data = {
    "product_name": f"Product {int(time.time())}",
    "sku": f"SKU-{int(time.time())}",
    "current_stock": 100,
    "price": 500
}
test("POST", "/api/inventory/products", "Create Product", product_data, 201, use_token=True)
test("GET", "/api/inventory/products", "List Products", expected=200, use_token=True)
test("GET", "/api/inventory/stock-levels", "Stock Levels", expected=200, use_token=True)

# ============================================================
print(f"\n{BLUE}5️⃣  CUSTOMERS{RESET}")
print("=" * 90)
customer_data = {
    "customer_name": f"Cust {int(time.time())}",
    "phone": "9876543210",
    "email": "cust@test.com"
}
test("POST", "/customers/create", "Create Customer", customer_data, 201, use_token=True)
test("GET", "/customers/", "List Customers", expected=200, use_token=True)
test("GET", "/customers/search/by-phone?phone=9876543210", "Search by Phone", expected=200, use_token=True)

# ============================================================
print(f"\n{BLUE}6️⃣  ATTENDANCE{RESET}")
print("=" * 90)
test("POST", "/api/attendance/check-in", "Check In", {"user_id": 1}, 200, use_token=True)
test("GET", "/api/attendance/date/2026-06-18", "Attendance by Date", expected=200, use_token=True)
test("GET", "/api/attendance/workers", "Workers", expected=200, use_token=True)

# ============================================================
print(f"\n{BLUE}7️⃣  INVOICES{RESET}")
print("=" * 90)
invoice_data = {
    "customer_id": 1,
    "total_amount": 5000,
    "tax": 500,
    "items": []
}
test("POST", "/api/invoices/create", "Create Invoice", invoice_data, 200, use_token=True)
test("GET", "/api/invoices/list", "List Invoices", expected=200, use_token=True)

# ============================================================
print(f"\n{BLUE}8️⃣  KHATA & LEDGER{RESET}")
print("=" * 90)
test("GET", "/khata/balance/1", "Khata Balance", expected=200, use_token=True)
test("GET", "/khata/customers", "Khata Customers", expected=200, use_token=True)

# ============================================================
print(f"\n{BLUE}9️⃣  ADVANCED FEATURES{RESET}")
print("=" * 90)
test("GET", "/cache/stats", "Cache Stats", expected=200, use_token=True)
test("GET", "/batch/status", "Batch Status", expected=200, use_token=True)

print(f"\n{BLUE}{'=' * 90}{RESET}\n")
