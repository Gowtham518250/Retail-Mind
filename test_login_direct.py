#!/usr/bin/env python3
"""Test login endpoint directly"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 10

print("Testing Login Endpoint...")
print("=" * 60)

# First, test if the server is up
try:
    r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    print(f"✓ Server is up: {r.status_code}")
except Exception as e:
    print(f"✗ Server not responding: {e}")
    exit(1)

# Try to register a new user
print("\n1. Testing Register...")
payload = {
    "username": f"testuser_{int(time.time())}",
    "email": f"test_{int(time.time())}@example.com",
    "password": "Test@1234567",
    "user_type": "OWNER"
}

try:
    r = requests.post(
        f"{BASE_URL}/auth/register",
        json=payload,
        timeout=TIMEOUT,
        headers={"Content-Type": "application/json"}
    )
    print(f"Status: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2)}")
    
    if r.status_code != 200:
        print(f"✗ Register failed!")
        if r.text:
            print(f"Raw response: {r.text[:500]}")
except Exception as e:
    print(f"✗ Register error: {e}")

# Now try to login with those credentials
print("\n2. Testing Login...")
login_payload = {
    "email": payload["email"],
    "password": payload["password"]
}

try:
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json=login_payload,
        timeout=TIMEOUT,
        headers={"Content-Type": "application/json"}
    )
    print(f"Status: {r.status_code}")
    print(f"Response: {json.dumps(r.json(), indent=2)}")
    
    if r.status_code == 200:
        print("✓ Login successful!")
        token = r.json().get("access_token")
        print(f"Token: {token[:50]}...")
    else:
        print(f"✗ Login failed!")
except Exception as e:
    print(f"✗ Login error: {e}")

print("\n" + "=" * 60)
