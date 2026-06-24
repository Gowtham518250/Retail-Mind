import requests
import json

BASE_URL = "https://retail-mind-vkbp.onrender.com"

TOKEN = "PASTE_YOUR_ACCESS_TOKEN_HERE"

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

endpoints = {
    "sales": "/auth/sales",
    "products": "/api/inventory/products",
    "customers": "/api/customers/",
    "invoices": "/api/invoices/",
    "expenses": "/api/expenses",
    "transactions": "/api/transactions/recent",
    "shop_profile": "/api/shop/profile",
    "workers": "/api/attendance/workers",
    "khata_customers": "/api/khata/customers"
}

all_data = {}

for name, endpoint in endpoints.items():
    print(f"\nFetching {name}...")

    try:
        r = requests.get(
            BASE_URL + endpoint,
            headers=headers,
            timeout=30
        )

        print(f"{name}: {r.status_code}")

        try:
            all_data[name] = r.json()
        except:
            all_data[name] = r.text

    except Exception as e:
        all_data[name] = str(e)

with open("retail_mind_dump.json", "w", encoding="utf-8") as f:
    json.dump(all_data, f, indent=2, ensure_ascii=False)
import requests
import json

BASE_URL = "https://retail-mind-vkbp.onrender.com"

EMAIL = "ggowthamreddyv@gmail.com"
PASSWORD = "Gowtham@2004"

# LOGIN
login = requests.post(
    f"{BASE_URL}/auth/login",
    json={
        "email": EMAIL,
        "password": PASSWORD
    }
)

print("\nLOGIN STATUS:", login.status_code)

login_data = login.json()
print(json.dumps(login_data, indent=2))

token = login_data["access_token"]

headers = {
    "Authorization": f"Bearer {token}"
}

# ENDPOINTS TO TEST
endpoints = [
    "/api/transactions/recent",
    "/auth/sales",
    "/api/invoices/",
    "/api/customers/",
    "/api/inventory/products",
    "/api/shop/profile",
    "/api/expenses",
    "/api/khata/customers",
    "/api/attendance/workers"
]

for endpoint in endpoints:
    print("\n" + "=" * 80)
    print("TESTING:", endpoint)
    print("=" * 80)

    try:
        r = requests.get(
            BASE_URL + endpoint,
            headers=headers,
            timeout=30
        )

        print("STATUS:", r.status_code)

        try:
            print(json.dumps(r.json(), indent=2))
        except:
            print(r.text)

    except Exception as e:
        print("ERROR:", e)
print("\nSaved to retail_mind_dump.json")