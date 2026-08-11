import requests
import json

BASE_URL = "http://localhost:8000"

print("Testing Retail Mind API Endpoints")
print("=" * 50)

# Test 1: Health Check
print("\n1. Testing Health Check Endpoint...")
try:
    response = requests.get(f"{BASE_URL}/api/observability/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 2: Readiness Check
print("\n2. Testing Readiness Check Endpoint...")
try:
    response = requests.get(f"{BASE_URL}/api/observability/ready")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 3: Metrics
print("\n3. Testing Metrics Endpoint...")
try:
    response = requests.get(f"{BASE_URL}/api/observability/metrics")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 4: Security Check
print("\n4. Testing Security Check Endpoint...")
try:
    response = requests.get(f"{BASE_URL}/api/security/check")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   Error: {e}")

# Test 5: Root endpoint
print("\n5. Testing Root Endpoint...")
try:
    response = requests.get(f"{BASE_URL}/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 50)
print("Endpoint Testing Complete")
