#!/usr/bin/env python3
"""Test legacy POST /auth/sales on production (uses int user_id)."""
import json, time, uuid, requests, os

BASE = "https://retail-mind-vkbp.onrender.com"
LOG = r"d:\AI_Shop_Latest_Source_June2\lib\debug-6d3a75.log"
EMAIL = f"legacy_{uuid.uuid4().hex[:8]}@retailmind.test"
PASSWORD = "LegacyProbe123!"


def log(hid, loc, msg, data):
    e = {"sessionId": "6d3a75", "runId": "legacy-probe", "hypothesisId": hid,
         "location": loc, "message": msg, "data": data, "timestamp": int(time.time() * 1000)}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e))


def main():
    requests.get(f"{BASE}/health", timeout=90)
    uname = f"legacy_{uuid.uuid4().hex[:6]}"
    reg = requests.post(f"{BASE}/auth/register", json={
        "username": uname, "email": EMAIL, "password": PASSWORD,
        "user_type": "OWNER", "role": "OWNER",
    }, timeout=90)
    log("H7", "legacy:register", "REGISTER", {"status": reg.status_code})

    login = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=90)
    token = login.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    sale_id = f"SALE_LEGACY_{uuid.uuid4().hex[:8].upper()}"

    post = requests.post(f"{BASE}/auth/sales", headers=headers, data={
        "product_name": "Legacy Probe Item",
        "price": "75.0",
        "quantity": "2",
        "total": "150.0",
        "sale_id": sale_id,
        "date": time.strftime("%Y-%m-%d"),
    }, timeout=90)
    log("H7", "legacy:post", "POST /auth/sales", {"status": post.status_code, "body": post.text[:400], "sale_id": sale_id})

    sales = requests.get(f"{BASE}/auth/sales", headers=headers, timeout=90)
    exists = sale_id in sales.text
    log("H7", "legacy:verify", "GET /auth/sales", {
        "status": sales.status_code, "saleExists": exists, "sale_id": sale_id,
    })


if __name__ == "__main__":
    main()
