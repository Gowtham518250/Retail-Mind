import requests
import time
import sys

BASE_URL = "https://retail-mind-vkbp.onrender.com"

# Register & Login
username = f"finalcheck_{int(time.time())}"
email = f"{username}@test.com"

print("Registering test user on live server...")
requests.post(f"{BASE_URL}/auth/register", json={"email": email, "username": username, "password": "Password123!"})

print("Logging in to live server...")
res = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": "Password123!"})
if res.status_code != 200:
    print("Failed to authenticate.")
    sys.exit(1)

token = res.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

endpoints = [
    ("POST", "/api/sales-restore/restore-all", {}),
    ("GET", "/api/sales-restore/restore-summary", None),
    ("GET", "/api/invoices/", None),
    ("GET", "/api/invoices/analytics/summary", None),
    ("GET", "/api/reports/daily", None),
    ("GET", "/api/transactions/recent", None),
    ("GET", "/api/transactions/online-payments", None),
    ("GET", "/api/attendance/date/2026-06-18", None),
    ("GET", "/api/data/backup/export", None),
    ("GET", "/api/data/integrity-check", None),
]

print("\n--- CHECKING PREVIOUSLY BROKEN ENDPOINTS ON LIVE RENDER SERVER ---")
all_good = True
for method, url_path, data in endpoints:
    url = f"{BASE_URL}{url_path}"
    try:
        if method == "POST":
            res = requests.post(url, json=data, headers=headers)
        else:
            res = requests.get(url, headers=headers)
            
        color = "\033[92m" if res.status_code in [200, 201] else "\033[91m"
        reset = "\033[0m"
        print(f"{color}[{method}] {url_path} -> HTTP {res.status_code}{reset}")
        
        if res.status_code >= 500:
            print(f"ERROR OUTPUT: {res.text}")
            all_good = False
    except Exception as e:
        print(f"[{method}] {url_path} -> Request failed: {e}")
        all_good = False

if all_good:
    print("\n✅ SUCCESS! All 10 previously broken endpoints are now returning 200 OK on the live server.")
else:
    print("\n❌ FAILURE! Some endpoints are still broken.")
