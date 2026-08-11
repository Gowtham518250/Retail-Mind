#!/usr/bin/env python3
"""Test register endpoint with detailed error reporting"""
import requests
import json
import time
import traceback
import sys

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 10

print("Testing Register Endpoint with Error Details")
print("=" * 70)

# Test server connectivity first
try:
    print("1. Testing server connectivity...")
    r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        print("   ✓ Server is responding")
    else:
        print(f"   ✗ Server returned {r.status_code}")
except Exception as e:
    print(f"   ✗ Cannot connect: {e}")
    sys.exit(1)

# Now test registration with full error details
print("\n2. Testing Register Endpoint...")
payload = {
    "username": f"testuser_{int(time.time())}",
    "email": f"test_{int(time.time())}@test.com",
    "password": "Test@123456",
    "user_type": "OWNER"
}

print(f"   Payload: {json.dumps(payload, indent=6)}")

try:
    print("\n   Sending request...")
    r = requests.post(
        f"{BASE_URL}/auth/register",
        json=payload,
        timeout=TIMEOUT,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\n   Response Status: {r.status_code}")
    print(f"   Response Headers: {dict(r.headers)}")
    
    try:
        response_json = r.json()
        print(f"   Response JSON:\n{json.dumps(response_json, indent=6)}")
    except:
        print(f"   Response Text:\n{r.text[:500]}")
    
    if r.status_code != 200:
        print(f"\n✗ REGISTRATION FAILED")
        print(f"  Status Code: {r.status_code}")
        print(f"  Expected: 200")
    else:
        print(f"\n✓ REGISTRATION SUCCEEDED")
        
except requests.exceptions.RequestException as e:
    print(f"\n✗ Request Error: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"\n✗ Unexpected Error: {e}")
    traceback.print_exc()

print("\n" + "=" * 70)
