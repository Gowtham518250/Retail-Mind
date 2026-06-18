import requests
import time

base_url = 'https://retail-mind-ikhi.onrender.com'

print("Fetching OpenAPI Spec from live server...")
resp = requests.get(f"{base_url}/openapi.json")
if resp.status_code != 200:
    print("Failed to fetch OpenAPI spec.")
    exit(1)

spec = resp.json()
paths = spec.get("paths", {})

print(f"Found {len(paths)} endpoints.")

# Get a token to test authenticated routes
print("Registering dummy test user...")
user_id = int(time.time())
username = f"livetest{user_id}"
email = f"livetest{user_id}@mailinator.com"
password = "Password123!"

requests.post(f"{base_url}/auth/register", json={
    "username": username,
    "email": email,
    "password": password
})

print("Logging in...")
login_resp = requests.post(f"{base_url}/auth/login", json={
    "username": username,
    "password": password
})

token = ""
if login_resp.status_code == 200:
    token = login_resp.json().get("access_token", "")
    print("Login OK!")
else:
    print(f"Login Failed: {login_resp.text}")

headers = {"Authorization": f"Bearer {token}"} if token else {}

success = 0
errors = []

for path, operations in paths.items():
    if "get" in operations:
        # Fill required path parameters
        test_path = path.replace("{shop_id}", "1").replace("{product_id}", "1").replace("{customer_id}", "1").replace("{invoice_id}", "1").replace("{supplier_id}", "1").replace("{order_id}", "1")
        
        # Avoid websocket or download routes if they hang
        if "ws" in test_path or "export" in test_path:
            continue
            
        print(f"Testing GET {test_path}...")
        try:
            res = requests.get(f"{base_url}{test_path}", headers=headers, timeout=10)
            if res.status_code >= 500:
                errors.append(f"GET {test_path} -> {res.status_code}: {res.text[:100]}")
            else:
                success += 1
        except Exception as e:
            errors.append(f"GET {test_path} -> Timeout/Exception: {str(e)}")

print(f"\n--- TEST RESULTS ---")
print(f"Success: {success}")
print(f"Errors: {len(errors)}")

if errors:
    print("\nCRITICAL ERRORS FOUND:")
    for e in errors[:15]:
        print("->", e)
else:
    print("\nAll GET endpoints passed successfully!")

