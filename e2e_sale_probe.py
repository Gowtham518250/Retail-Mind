#!/usr/bin/env python3
"""End-to-end probe: register/login -> POST invoice -> GET /auth/sales"""
import json
import time
import uuid
import requests
import os

BASE = "https://retail-mind-vkbp.onrender.com"
LOG = r"d:\AI_Shop_Latest_Source_June2\lib\debug-6d3a75.log"
EMAIL = os.environ.get("TEST_EMAIL", f"probe_{uuid.uuid4().hex[:8]}@retailmind.test")
PASSWORD = os.environ.get("TEST_PASSWORD", "ProbeTest123!")


def log(hid, loc, msg, data, run_id="e2e-probe"):
    e = {
        "sessionId": "6d3a75",
        "runId": run_id,
        "hypothesisId": hid,
        "location": loc,
        "message": msg,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e))


def main():
    # Wake server
    try:
        h = requests.get(f"{BASE}/health", timeout=90)
        log("H2", "e2e:health", "HEALTH", {"status": h.status_code, "body": h.text[:200]})
    except Exception as ex:
        log("H2", "e2e:health", "HEALTH FAILED", {"error": str(ex)})
        return

    token = None
    user_id = None

    # Try login with test creds first
    for email, password, label in [
        (os.environ.get("TEST_EMAIL"), os.environ.get("TEST_PASSWORD"), "env"),
        (EMAIL, PASSWORD, "register"),
    ]:
        if not email or not password:
            continue
        if label == "register":
            reg = requests.post(
                f"{BASE}/auth/register",
                json={
                    "username": f"probe_{uuid.uuid4().hex[:8]}",
                    "email": email,
                    "password": password,
                    "user_type": "OWNER",
                    "role": "OWNER",
                },
                timeout=90,
            )
            log("H2", "e2e:register", "REGISTER", {"status": reg.status_code, "body": reg.text[:300], "email": email})

        login = requests.post(
            f"{BASE}/auth/login",
            json={"email": email, "password": password},
            timeout=90,
        )
        log("H2", "e2e:login", f"LOGIN {label}", {"status": login.status_code, "body": login.text[:300]})
        if login.status_code == 200:
            data = login.json()
            token = data.get("access_token") or data.get("token")
            user_id = data.get("user_id")
            break

    if not token:
        log("H2", "e2e:abort", "NO TOKEN", {"hint": "Set TEST_EMAIL and TEST_PASSWORD env vars"})
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    inv = f"SALE_PROBE_{uuid.uuid4().hex[:10].upper()}"

    payload = {
        "invoice_number": inv,
        "offline_id": f"{inv}_{int(time.time()*1000)}",
        "customer_name": "E2E Probe",
        "total_amount": 50.0,
        "paid_amount": 50.0,
        "tax": 0.0,
        "payment_status": "PAID",
        "invoice_date": time.strftime("%Y-%m-%d"),
        "line_items": [{"product_name": "Probe Product", "quantity": 1, "unit_price": 50.0}],
    }

    log("H1", "e2e:pre_create", "POST /api/invoices/create", {"invoice_number": inv, "user_id": user_id})

    create = requests.post(f"{BASE}/api/invoices/create", json=payload, headers=headers, timeout=90)
    log("H2", "e2e:create_response", "POST /create RESPONSE", {
        "status": create.status_code,
        "body": create.text[:600],
        "invoice_number": inv,
    })

    if create.status_code not in (200, 201):
        sync = requests.post(f"{BASE}/api/invoices/sync", json=payload, headers=headers, timeout=90)
        log("H2", "e2e:sync_response", "POST /sync RESPONSE", {
            "status": sync.status_code,
            "body": sync.text[:600],
        })

    sales = requests.get(f"{BASE}/auth/sales", headers=headers, timeout=90)
    exists = inv in sales.text
    count = 0
    if sales.status_code == 200:
        try:
            d = sales.json()
            if isinstance(d, list):
                count = len(d)
        except Exception:
            pass

    log("H3", "e2e:get_sales", "GET /auth/sales VERIFY", {
        "status": sales.status_code,
        "count": count,
        "saleExists": exists,
        "invoice_number": inv,
    })

    invoices = requests.get(f"{BASE}/api/invoices/", headers=headers, timeout=90)
    inv_exists = inv in invoices.text
    log("H3", "e2e:get_invoices", "GET /api/invoices VERIFY", {
        "status": invoices.status_code,
        "invoiceExists": inv_exists,
        "bodyPreview": invoices.text[:400],
    })


if __name__ == "__main__":
    main()
