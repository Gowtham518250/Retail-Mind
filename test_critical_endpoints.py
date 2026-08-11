import requests
import json

BASE_URL = "http://localhost:8000"

print("Testing Critical Business Endpoints")
print("=" * 50)

# Test Authentication - Register
print("\n1. Testing User Registration...")
try:
    register_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPassword123!"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {response.json()}")
        user_data = response.json()
    else:
        print(f"   Error: {response.text}")
except Exception as e:
    print(f"   Error: {e}")

# Test Authentication - Login
print("\n2. Testing User Login...")
try:
    login_data = {
        "email": "test@example.com",
        "password": "TestPassword123!"
    }
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {response.json()}")
        token_data = response.json()
        access_token = token_data.get("access_token")
    else:
        print(f"   Error: {response.text}")
        access_token = None
except Exception as e:
    print(f"   Error: {e}")
    access_token = None

# Test Inventory Sync - Get All Stock
print("\n3. Testing Inventory Sync - Get All Stock...")
if access_token:
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BASE_URL}/api/inventory-sync/all-stock", headers=headers)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
else:
    print("   Skipped - No access token")

# Test Sales Restore - Get Restoration Summary
print("\n4. Testing Sales Restore - Get Restoration Summary...")
if access_token:
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BASE_URL}/api/sales-restore/restore-summary", headers=headers)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
else:
    print("   Skipped - No access token")

# Test Security Hardening - Input Check
print("\n5. Testing Security Hardening - Input Check...")
try:
    input_data = {
        "input_data": "test input",
        "check_type": "sql_injection"
    }
    response = requests.post(f"{BASE_URL}/api/security/check-input", json=input_data)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 50)
print("Critical Endpoint Testing Complete")
