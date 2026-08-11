#!/usr/bin/env python3
"""Simulate Flutter flow: create(500) -> sync(500) -> legacy(200) multi-item"""
import json, time, uuid, requests

BASE = "https://retail-mind-vkbp.onrender.com"
LOG = r"d:\AI_Shop_Latest_Source_June2\lib\debug-6d3a75.log"
EMAIL = f"multi_{uuid.uuid4().hex[:8]}@retailmind.test"
PASSWORD = "MultiProbe123!"


def log(hid, loc, msg, data, run_id="flutter-sim"):
    e = {"sessionId": "6d3a75", "runId": run_id, "hypothesisId": hid,
         "location": loc, "message": msg, "data": data, "timestamp": int(time.time() * 1000)}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e))


def main():
    requests.get(f"{BASE}/health", timeout=90)
    uname = f"multi_{uuid.uuid4().hex[:6]}"
    requests.post(f"{BASE}/auth/register", json={
        "username": uname, "email": EMAIL, "password": PASSWORD,
        "user_type": "OWNER", "role": "OWNER",
    }, timeout=90)
    login = requests.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=90)
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    sale_id = f"SALE_{int(time.time() * 1000000)}"
    line_items = [
        {"product_name": "Rice 1kg", "quantity": 2, "unit_price": 50.0, "line_total": 100.0},
        {"product_name": "Dal 500g", "quantity": 1, "unit_price": 80.0, "line_total": 80.0},
    ]
    payload = {
        "invoice_number": sale_id,
        "offline_id": f"{sale_id}_off",
        "customer_name": "Cash Customer",
        "total_amount": 180.0,
        "paid_amount": 180.0,
        "payment_status": "PAID",
        "invoice_date": time.strftime("%Y-%m-%d"),
        "line_items": line_items,
    }

    c = requests.post(f"{BASE}/api/invoices/create", json=payload, headers=headers, timeout=90)
    log("H2", "sim:create", "POST /create", {"status": c.status_code})
    s = requests.post(f"{BASE}/api/invoices/sync", json=payload, headers=headers, timeout=90)
    log("H2", "sim:sync", "POST /sync", {"status": s.status_code})

    synced = 0
    for item in line_items:
        r = requests.post(f"{BASE}/auth/sales", headers={"Authorization": f"Bearer {token}"}, data={
            "product_name": item["product_name"],
            "product": item["product_name"],
            "price": str(item["unit_price"]),
            "quantity": str(item["quantity"]),
            "total": str(item["line_total"]),
            "sale_id": sale_id,
            "date": time.strftime("%Y-%m-%d"),
        }, timeout=90)
        if r.status_code in (200, 201):
            synced += 1
        log("H7", "sim:legacy_line", "POST /auth/sales line", {
            "status": r.status_code, "product": item["product_name"], "synced_so_far": synced,
        })

    verify = requests.get(f"{BASE}/auth/sales", headers={"Authorization": f"Bearer {token}"}, timeout=90)
    exists = sale_id in verify.text
    log("H3", "sim:verify", "FINAL RESULT", {
        "legacyLinesSynced": synced,
        "totalLines": len(line_items),
        "legacySuccess": synced == len(line_items),
        "saleExists": exists,
        "saleId": sale_id,
    })


if __name__ == "__main__":
    main()
