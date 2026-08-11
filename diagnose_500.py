from fastapi.testclient import TestClient
from app import api
from db import get_db, Base, engine
import traceback
import sys
import uuid
import time

# Create all tables explicitly in case something is missing locally
Base.metadata.create_all(bind=engine)

client = TestClient(api)

username = f"diag_{int(time.time())}"
email = f"{username}@test.com"

client.post("/auth/register", json={"email": email, "username": username, "password": "Password123!"})
res = client.post("/auth/login", json={"email": email, "password": "Password123!"})
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

for method, url, data in endpoints:
    try:
        if method == "POST":
            res = client.post(url, json=data, headers=headers)
        else:
            res = client.get(url, headers=headers)
            
        print(f"{method} {url} -> {res.status_code}")
        if res.status_code == 500:
            print("Response:", res.text)
    except Exception as e:
        print(f"{method} {url} -> Exception Thrown Natively:")
        traceback.print_exc()
        print("-" * 40)
