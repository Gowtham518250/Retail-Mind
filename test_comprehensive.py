#!/usr/bin/env python3
"""
Comprehensive API Test and Fix Suite
Tests all endpoints and fixes issues found
"""
import requests
import json
import time
import sys
import os
from datetime import datetime

# Configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT = 10

# Test state
STATE = {
    "user_id": None,
    "access_token": None,
    "shop_id": 1,
}

RESULTS = {
    "PASS": [],
    "FAIL": [],
    "ERROR": []
}

def log(level, msg):
    """Simple logging"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{timestamp}] {level.ljust(7)}"
    print(f"{prefix} {msg}")

def test_health():
    """Test if server is responsive"""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        if r.status_code == 200:
            log("✓", "Server health check OK")
            return True
        else:
            log("✗", f"Server health check failed: {r.status_code}")
            return False
    except Exception as e:
        log("✗", f"Cannot connect to server: {e}")
        return False

def test_register():
    """Test user registration"""
    payload = {
        "username": f"testuser_{int(time.time())}",
        "email": f"test_{int(time.time())}@test.com",
        "password": "Test@123456",
        "user_type": "OWNER"
    }
    try:
        r = requests.post(
            f"{BASE_URL}/auth/register",
            json=payload,
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            STATE["username"] = payload["username"]
            STATE["email"] = payload["email"]
            STATE["password"] = payload["password"]
            log("✓", "Registration successful")
            RESULTS["PASS"].append("Register")
            return True
        else:
            log("✗", f"Register failed [{r.status_code}]: {r.text[:100]}")
            RESULTS["FAIL"].append(f"Register ({r.status_code})")
            return False
    except Exception as e:
        log("✗", f"Register error: {e}")
        RESULTS["ERROR"].append(f"Register ({str(e)[:50]})")
        return False

def test_login():
    """Test login"""
    if "email" not in STATE or "password" not in STATE:
        log("⚠", "Skipping login - no registered user")
        return False
    
    payload = {
        "email": STATE["email"],
        "password": STATE["password"]
    }
    
    try:
        r = requests.post(
            f"{BASE_URL}/auth/login",
            json=payload,
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            data = r.json()
            STATE["access_token"] = data.get("access_token")
            STATE["user_id"] = data.get("user_id")
            log("✓", "Login successful")
            RESULTS["PASS"].append("Login")
            return True
        else:
            log("✗", f"Login failed [{r.status_code}]: {r.text[:200]}")
            RESULTS["FAIL"].append(f"Login ({r.status_code})")
            return False
    except Exception as e:
        log("✗", f"Login error: {e}")
        RESULTS["ERROR"].append(f"Login ({str(e)[:50]})")
        return False

def test_protected_endpoint():
    """Test a protected endpoint"""
    if not STATE.get("access_token"):
        log("⚠", "Skipping protected test - no token")
        return False
    
    headers = {
        "Authorization": f"Bearer {STATE['access_token']}",
        "Content-Type": "application/json"
    }
    
    try:
        r = requests.get(
            f"{BASE_URL}/api/shop",
            headers=headers,
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            log("✓", "Protected endpoint accessible")
            RESULTS["PASS"].append("Protected Endpoint")
            return True
        else:
            log("✗", f"Protected endpoint failed [{r.status_code}]: {r.text[:100]}")
            RESULTS["FAIL"].append(f"Protected Endpoint ({r.status_code})")
            return False
    except Exception as e:
        log("✗", f"Protected endpoint error: {e}")
        RESULTS["ERROR"].append(f"Protected Endpoint ({str(e)[:50]})")
        return False

def main():
    print("\n" + "="*70)
    print("  RETAIL MIND - COMPREHENSIVE TEST SUITE")
    print("="*70)
    print(f"Base URL: {BASE_URL}\n")
    
    # Test server connectivity
    log("START", "Testing server connectivity...")
    if not test_health():
        log("ABORT", "Server is not responding. Start app with:")
        print(f"  python -m uvicorn app:api --host 127.0.0.1 --port 8000")
        sys.exit(1)
    
    print("\n" + "-"*70)
    log("START", "Running authentication tests...")
    
    test_register()
    time.sleep(0.5)
    test_login()
    
    print("\n" + "-"*70)
    log("START", "Running protected endpoint tests...")
    
    test_protected_endpoint()
    
    print("\n" + "="*70)
    print("  TEST RESULTS")
    print("="*70)
    print(f"✓ PASSED: {len(RESULTS['PASS'])}")
    for test in RESULTS['PASS']:
        print(f"  - {test}")
    
    print(f"\n✗ FAILED: {len(RESULTS['FAIL'])}")
    for test in RESULTS['FAIL']:
        print(f"  - {test}")
    
    print(f"\n⚠ ERRORS: {len(RESULTS['ERROR'])}")
    for test in RESULTS['ERROR']:
        print(f"  - {test}")
    
    print("\n" + "="*70)
    
    if RESULTS['FAIL'] or RESULTS['ERROR']:
        log("RESULT", "Some tests failed - see details above")
        sys.exit(1)
    else:
        log("RESULT", "All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()
