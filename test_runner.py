import urllib.request
import json
import time

base_url = 'https://retail-mind-ikhi.onrender.com'

with open('openapi_dump.json', 'r') as f:
    paths = json.load(f)

print("Registering dummy user...")
# We use urllib to post
req = urllib.request.Request(f"{base_url}/auth/register", method="POST", headers={'Content-Type': 'application/json'})
data = json.dumps({
    "username": f"livetest_{int(time.time())}",
    "email": f"livetest_{int(time.time())}@test.com",
    "password": "Password123!"
}).encode('utf-8')

try:
    with urllib.request.urlopen(req, data=data) as resp:
        print("Registration OK:", resp.status)
except urllib.error.HTTPError as e:
    print("Registration Failed:", e.code, e.read().decode())

req = urllib.request.Request(f"{base_url}/auth/login", method="POST", headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, data=data) as resp:
        token = json.loads(resp.read().decode()).get("access_token")
        print("Login OK! Got token.")
except urllib.error.HTTPError as e:
    print("Login Failed:", e.code, e.read().decode())
    token = ""

headers = {'Authorization': f'Bearer {token}'} if token else {}

print("\nScanning GET endpoints...")
success = 0
errors = []
count = 0

for path, operations in paths.items():
    if count >= 30: # Limit to 30 for quick status
        break
    if "get" in operations:
        test_path = path.replace("{shop_id}", "1").replace("{product_id}", "1").replace("{customer_id}", "1")
        if "ws" in test_path or "export" in test_path or "{" in test_path:
            continue
            
        req = urllib.request.Request(f"{base_url}{test_path}", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                print(f"[OK] {res.status} - {test_path}")
                success += 1
        except urllib.error.HTTPError as e:
            if e.code == 500:
                print(f"[ERROR 500] {test_path} : {e.read().decode()[:100]}")
                errors.append(f"{test_path} (500)")
            else:
                print(f"[OK] {e.code} - {test_path}") # 401, 404, 422 are fine (auth/validation)
                success += 1
        except Exception as e:
            print(f"[TIMEOUT/FAIL] {test_path} : {str(e)}")
        count += 1

print(f"\nScan complete. Success: {success}, Errors: {len(errors)}")
