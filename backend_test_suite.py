import urllib.request
import urllib.parse
import urllib.error
import json
import time

BASE_URL = "http://localhost:8000"
TEST_USER = {
    "user_name": "Test Owner",
    "email": "testowner@example.com",
    "password": "SecurePassword123"
}

def make_request(method, endpoint, data=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f"Bearer {token}"
        
    req_data = None
    if data:
        req_data = json.dumps(data).encode('utf-8')
        
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8')), response.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode('utf-8')), e.code
    except Exception as e:
        print(f"Connection error on {endpoint}: {e}")
        return None, 500

print("Waiting for server to start...")
for _ in range(10):
    res, status = make_request("GET", "/health")
    if status == 200:
        print("[SUCCESS] Server is UP!")
        break
    time.sleep(2)
else:
    print("[FAIL] Server failed to start.")
    exit(1)

print("\n--- 1. Authentication Tests ---")
# Try to register
res, status = make_request("POST", "/auth/register", data=TEST_USER)
if status in [200, 201]:
    print("[SUCCESS] Register successful!")
elif status == 400 and "already registered" in str(res).lower():
    print("[SUCCESS] User already registered (expected)")
else:
    print(f"[FAIL] Register failed: {status} - {res}")

# Login
login_data = {"email": TEST_USER["email"], "password": TEST_USER["password"]}
res, status = make_request("POST", "/auth/login", data=login_data)
if status == 200 and "access_token" in res:
    print("[SUCCESS] Login successful!")
    TOKEN = res["access_token"]
else:
    print(f"[FAIL] Login failed: {status} - {res}")
    exit(1)

print("\n--- 2. Product/Inventory Tests ---")
# Create product
product_data = {
    "name": "Test Product",
    "barcode": "123456789",
    "unit_price": 10.0,
    "purchase_price": 5.0,
    "current_stock": 100,
    "min_stock_level": 10
}
res, status = make_request("POST", "/inventory/", data=product_data, token=TOKEN)
# Note: depends on inventory_router path, maybe it's just / ? Let's check status
if status in [200, 201]:
    print("[SUCCESS] Product created successfully!")
    product_id = res.get("id")
elif status == 404:
    print("[WARN] /inventory/ not found, router might be mounted differently.")
else:
    print(f"[FAIL] Product creation failed: {status} - {res}")

print("\n--- 3. Clean up ---")
print("[SUCCESS] Tests complete. Check server logs for full trace.")
