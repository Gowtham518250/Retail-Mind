#!/usr/bin/env python3
"""Probe POST /api/invoices/create + GET /auth/sales — writes NDJSON to debug log."""
import json, time, uuid, os, requests

BASE_URL = "https://retail-mind-vkbp.onrender.com"
LOG_PATH = r"d:\AI_Shop_Latest_Source_June2\lib\debug-6d3a75.log"
TEST_EMAIL = os.environ.get("TEST_EMAIL", "testshop@retailmind.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "TestPassword123!")


def log(hypothesis_id, location, message, data):
    entry = {
        "sessionId": "6d3a75",
        "runId": "api-probe",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry))


def main():
    # Login
    login = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=60,
    )
    log("H2", "probe:login", "LOGIN", {"status": login.status_code, "body": login.text[:300]})
    if login.status_code != 200:
        return
    token = login.json().get("access_token") or login.json().get("token")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    invoice_number = f"SALE_PROBE_{uuid.uuid4().hex[:12].upper()}"
    payload = {
        "invoice_number": invoice_number,
        "offline_id": f"{invoice_number}_{int(time.time()*1000)}",
        "customer_name": "Probe Customer",
        "total_amount": 99.0,
        "paid_amount": 99.0,
        "tax": 0.0,
        "payment_status": "PAID",
        "invoice_date": time.strftime("%Y-%m-%d"),
        "notes": "Debug probe sale",
        "line_items": [{"product_name": "Probe Item", "quantity": 1, "unit_price": 99.0}],
    }
    log("H1", "probe:pre_post", "POST REQUEST", {
        "url": f"{BASE_URL}/api/invoices/create",
        "invoice_number": invoice_number,
    })

    post = requests.post(f"{BASE_URL}/api/invoices/create", json=payload, headers=headers, timeout=60)
    log("H2", "probe:post_response", "POST RESPONSE", {
        "status": post.status_code,
        "body": post.text[:500],
        "invoice_number": invoice_number,
    })

    get_sales = requests.get(f"{BASE_URL}/auth/sales", headers=headers, timeout=60)
    sale_exists = invoice_number in get_sales.text
    count = 0
    if get_sales.status_code == 200:
        data = get_sales.json()
        if isinstance(data, list):
            count = len(data)
    log("H3", "probe:get_sales", "DATABASE VERIFY", {
        "status": get_sales.status_code,
        "count": count,
        "saleExists": sale_exists,
        "invoice_number": invoice_number,
    })


if __name__ == "__main__":
    main()
