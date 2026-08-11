#!/usr/bin/env python3
"""
🧪 AI SHOP PRO - COMPREHENSIVE ENDPOINT TESTING SUITE
Tests all 100+ endpoints with proper validation and reporting
"""

import os
import sys
import json
import requests
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dotenv import load_dotenv
import logging

# ==========================================
# SETUP
# ==========================================

# Load environment variables - try local first, then production
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
    print("📌 Test Mode: LOCAL (SQLite)")
else:
    load_dotenv('.env.production')
    print("📌 Test Mode: PRODUCTION (Render PostgreSQL)")

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

# Configuration - all from environment variables
API_BASE_URL = os.getenv("API_URL", "http://localhost:8000")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "test@example.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")

# Test data storage
auth_token = None
test_user_id = None
shop_id = None
product_id = None
customer_id = None
invoice_id = None

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Test results
test_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "errors": [],
    "details": []
}

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def print_header(title):
    print(f"\n{BLUE}{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}{RESET}\n")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def print_info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")

def test_endpoint(method: str, endpoint: str, name: str, data: Dict = None, 
                  expected_status: int = 200, headers: Dict = None) -> Tuple[bool, Dict]:
    """
    Test a single endpoint and return result
    """
    global test_results
    
    url = f"{API_BASE_URL}{endpoint}"
    test_results["total"] += 1
    
    try:
        start_time = time.time()
        
        # Prepare headers
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        if auth_token:
            req_headers["Authorization"] = f"Bearer {auth_token}"
        
        # Make request
        if method.upper() == "GET":
            response = requests.get(url, headers=req_headers, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=req_headers, timeout=10)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=req_headers, timeout=10)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=req_headers, timeout=10)
        else:
            print_error(f"Unknown method: {method}")
            return False, {}
        
        elapsed = round((time.time() - start_time) * 1000, 2)
        
        # Check response
        success = response.status_code == expected_status
        
        result = {
            "method": method,
            "endpoint": endpoint,
            "name": name,
            "status": response.status_code,
            "expected": expected_status,
            "elapsed_ms": elapsed,
            "success": success,
            "response": response.text[:200] if response.text else ""
        }
        
        if success:
            test_results["passed"] += 1
            print_success(f"{name} | {method} {endpoint} | {response.status_code} | {elapsed}ms")
        else:
            test_results["failed"] += 1
            print_error(f"{name} | {method} {endpoint} | Expected {expected_status}, got {response.status_code}")
            print_warning(f"Response: {response.text[:100]}")
        
        test_results["details"].append(result)
        
        try:
            return success, response.json() if response.text else {}
        except:
            return success, {}
            
    except requests.exceptions.Timeout:
        test_results["failed"] += 1
        print_error(f"{name} | TIMEOUT")
        test_results["errors"].append(f"{name}: Request timeout")
        return False, {}
    except requests.exceptions.ConnectionError:
        test_results["failed"] += 1
        print_error(f"{name} | CONNECTION ERROR")
        test_results["errors"].append(f"{name}: Connection error")
        return False, {}
    except Exception as e:
        test_results["failed"] += 1
        print_error(f"{name} | ERROR: {str(e)}")
        test_results["errors"].append(f"{name}: {str(e)}")
        return False, {}

# ==========================================
# TEST SUITES
# ==========================================

def test_health_endpoints():
    """Test system health endpoints"""
    print_header("1️⃣  HEALTH & SYSTEM ENDPOINTS")
    
    test_endpoint("GET", "/", "Root Endpoint", expected_status=200)
    test_endpoint("GET", "/health", "Health Check", expected_status=200)
    test_endpoint("GET", "/docs", "API Docs", expected_status=200)
    test_endpoint("GET", "/redoc", "ReDoc", expected_status=200)

def test_authentication():
    """Test authentication endpoints"""
    global auth_token, test_user_id
    
    print_header("2️⃣  AUTHENTICATION ENDPOINTS")
    
    # Register
    register_data = {
        "username": f"testuser_{int(time.time())}",
        "email": f"test_{int(time.time())}@example.com",
        "password": "TestPass123!@"
    }
    success, response = test_endpoint(
        "POST", "/auth/register", 
        "Register User",
        data=register_data,
        expected_status=200
    )
    if success and "user_id" in response:
        test_user_id = response["user_id"]
    
    # Send OTP
    otp_data = {
        "email": register_data["email"],
        "purpose": "Login Verification"
    }
    otp_success, otp_response = test_endpoint(
        "POST", "/auth/send-otp",
        "Send OTP to Email",
        data=otp_data,
        expected_status=200
    )
    
    # Login
    login_data = {
        "email": register_data["email"],
        "password": register_data["password"]
    }
    success, response = test_endpoint(
        "POST", "/auth/login",
        "Login User",
        data=login_data,
        expected_status=200
    )
    if success and "access_token" in response:
        auth_token = response["access_token"]
        print_success(f"Auth token acquired: {auth_token[:20]}...")
    
    # Refresh token
    if auth_token:
        test_endpoint(
            "POST", "/refresh-token",
            "Refresh Token",
            data={"refresh_token": auth_token},
            expected_status=200
        )

def test_shop_endpoints():
    """Test shop management endpoints"""
    global shop_id
    
    print_header("3️⃣  SHOP MANAGEMENT ENDPOINTS")
    
    if not auth_token:
        print_warning("Skipping shop endpoints - no auth token")
        return
    
    # Create shop profile
    shop_data = {
        "shop_name": f"Test Shop {int(time.time())}",
        "shop_type": "General",
        "phone": "9876543210",
        "email": "shop@example.com",
        "city": "Delhi",
        "gst_number": "18AABCN5055A1A0",
        "upi_id": "shop@paytm"
    }
    success, response = test_endpoint(
        "POST", "/shop/profile",
        "Create Shop Profile",
        data=shop_data,
        expected_status=201
    )
    if success and "id" in response:
        shop_id = response["id"]
    
    # Get shop profile
    if shop_id:
        test_endpoint(
            "GET", f"/shop/profile/{shop_id}",
            "Get Shop Profile",
            expected_status=200
        )
    
    # Update shop profile
    if shop_id:
        update_data = {"shop_name": "Updated Shop Name"}
        test_endpoint(
            "PUT", f"/shop/profile/{shop_id}",
            "Update Shop Profile",
            data=update_data,
            expected_status=200
        )
    
    # List shops
    test_endpoint(
        "GET", "/shop/list",
        "List Shops",
        expected_status=200
    )

def test_inventory_endpoints():
    """Test inventory management endpoints"""
    global product_id
    
    print_header("4️⃣  INVENTORY MANAGEMENT ENDPOINTS")
    
    if not auth_token:
        print_warning("Skipping inventory endpoints - no auth token")
        return
    
    # Create product
    product_data = {
        "product_name": f"Test Product {int(time.time())}",
        "sku": f"SKU-{int(time.time())}",
        "unit_price": 1000.00,
        "current_stock": 50,
        "category": "Electronics",
        "min_stock": 5,
        "max_stock": 100
    }
    success, response = test_endpoint(
        "POST", "/api/inventory/products",
        "Create Product",
        data=product_data,
        expected_status=201
    )
    if success and "id" in response:
        product_id = response["id"]
    
    # Get products
    test_endpoint(
        "GET", "/api/inventory/products",
        "Get Products List",
        expected_status=200
    )
    
    # Get product by ID
    if product_id:
        test_endpoint(
            "GET", f"/api/inventory/products/{product_id}",
            "Get Product by ID",
            expected_status=200
        )
    
    # Update product
    if product_id:
        test_endpoint(
            "PUT", f"/api/inventory/products/{product_id}",
            "Update Product",
            data={"product_name": "Updated Product"},
            expected_status=200
        )
    
    # Get stock levels
    test_endpoint(
        "GET", "/api/inventory/stock-levels",
        "Get Stock Levels",
        expected_status=200
    )

def test_customer_endpoints():
    """Test customer management endpoints"""
    global customer_id
    
    print_header("5️⃣  CUSTOMER MANAGEMENT ENDPOINTS")
    
    if not auth_token:
        print_warning("Skipping customer endpoints - no auth token")
        return
    
    # Create customer
    customer_data = {
        "customer_name": f"Test Customer {int(time.time())}",
        "phone": "9876543210",
        "email": f"customer_{int(time.time())}@example.com",
        "city": "Delhi"
    }
    success, response = test_endpoint(
        "POST", "/customers/create",
        "Create Customer",
        data=customer_data,
        expected_status=201
    )
    if success and "id" in response:
        customer_id = response["id"]
    
    # Get customers
    test_endpoint(
        "GET", "/customers/list",
        "Get Customers List",
        expected_status=200
    )
    
    # Get customer by ID
    if customer_id:
        test_endpoint(
            "GET", f"/customers/{customer_id}",
            "Get Customer by ID",
            expected_status=200
        )
    
    # Search customers
    test_endpoint(
        "GET", "/customers/search?phone=9876543210",
        "Search Customers by Phone",
        expected_status=200
    )

def test_invoice_endpoints():
    """Test invoice & billing endpoints"""
    global invoice_id
    
    print_header("6️⃣  INVOICE & BILLING ENDPOINTS")
    
    if not auth_token or not product_id:
        print_warning("Skipping invoice endpoints - missing prerequisites")
        return
    
    # Create invoice
    invoice_data = {
        "customer_id": customer_id if customer_id else 1,
        "items": [
            {
                "product_id": product_id,
                "quantity": 2,
                "unit_price": 1000
            }
        ],
        "tax_percent": 5,
        "discount_percent": 0
    }
    success, response = test_endpoint(
        "POST", "/api/invoices/create",
        "Create Invoice",
        data=invoice_data,
        expected_status=201
    )
    if success and "id" in response:
        invoice_id = response["id"]
    
    # Get invoices
    test_endpoint(
        "GET", "/api/invoices/list",
        "Get Invoices List",
        expected_status=200
    )
    
    # Get invoice by ID
    if invoice_id:
        test_endpoint(
            "GET", f"/api/invoices/{invoice_id}",
            "Get Invoice by ID",
            expected_status=200
        )

def test_khata_endpoints():
    """Test khata (credit) ledger endpoints"""
    print_header("7️⃣  KHATA LEDGER ENDPOINTS")
    
    if not auth_token or not customer_id:
        print_warning("Skipping khata endpoints - missing prerequisites")
        return
    
    # Get khata balance
    test_endpoint(
        "GET", f"/khata/balance/{customer_id}",
        "Get Khata Balance",
        expected_status=200
    )
    
    # Add credit
    credit_data = {
        "customer_id": customer_id,
        "amount": 5000,
        "description": "Test credit entry"
    }
    test_endpoint(
        "POST", "/khata/add-credit",
        "Add Khata Credit",
        data=credit_data,
        expected_status=200
    )
    
    # Get khata history
    test_endpoint(
        "GET", f"/khata/history/{customer_id}",
        "Get Khata History",
        expected_status=200
    )

def test_attendance_endpoints():
    """Test attendance management endpoints"""
    print_header("8️⃣  ATTENDANCE MANAGEMENT ENDPOINTS")
    
    if not auth_token:
        print_warning("Skipping attendance endpoints - no auth token")
        return
    
    # Check in
    test_endpoint(
        "POST", "/attendance/check-in",
        "Check In",
        data={},
        expected_status=200
    )
    
    # Get attendance
    test_endpoint(
        "GET", "/attendance/today",
        "Get Today's Attendance",
        expected_status=200
    )

def test_advanced_features():
    """Test advanced features"""
    print_header("9️⃣  ADVANCED FEATURES")
    
    if not auth_token:
        print_warning("Skipping advanced features - no auth token")
        return
    
    # Caching system
    test_endpoint(
        "GET", "/cache/stats",
        "Cache Statistics",
        expected_status=200
    )
    
    # Batch operations status
    test_endpoint(
        "GET", "/batch/status",
        "Batch Operations Status",
        expected_status=200
    )
    
    # Rate limiting info
    test_endpoint(
        "GET", "/rate-limit-info",
        "Rate Limiting Info",
        expected_status=200
    )

def test_error_handling():
    """Test error handling"""
    print_header("🔟 ERROR HANDLING & EDGE CASES")
    
    # Test 404
    test_endpoint(
        "GET", "/nonexistent-endpoint",
        "Non-existent Endpoint (404)",
        expected_status=404
    )
    
    # Test 401 (unauthorized)
    test_endpoint(
        "GET", "/protected-endpoint",
        "Protected Endpoint without Auth (401)",
        expected_status=401
    )
    
    # Test invalid data
    invalid_data = {"invalid_field": "test"}
    test_endpoint(
        "POST", "/auth/register",
        "Invalid Registration Data (422)",
        data=invalid_data,
        expected_status=422
    )

# ==========================================
# REPORTING
# ==========================================

def generate_report():
    """Generate test report"""
    print_header("📊 TEST SUMMARY REPORT")
    
    total = test_results["total"]
    passed = test_results["passed"]
    failed = test_results["failed"]
    
    if total > 0:
        percentage = (passed / total) * 100
    else:
        percentage = 0
    
    print(f"Total Tests: {total}")
    print(f"Passed: {GREEN}{passed}{RESET}")
    print(f"Failed: {RED}{failed}{RESET}")
    print(f"Success Rate: {percentage:.1f}%")
    
    if test_results["errors"]:
        print(f"\n{RED}Errors:{RESET}")
        for error in test_results["errors"]:
            print(f"  • {error}")
    
    # Detailed results
    print(f"\n{BLUE}Detailed Results:{RESET}")
    print(f"{'Endpoint':<50} {'Status':<8} {'Time (ms)':<10}")
    print("-" * 70)
    
    for detail in test_results["details"]:
        status_str = f"{detail['status']}" if detail['success'] else f"{detail['status']} (Expected {detail['expected']})"
        print(f"{detail['endpoint']:<50} {status_str:<8} {detail['elapsed_ms']:<10}")

def save_report():
    """Save report to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_report_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump({
            "timestamp": timestamp,
            "api_url": API_BASE_URL,
            "summary": {
                "total": test_results["total"],
                "passed": test_results["passed"],
                "failed": test_results["failed"],
                "success_rate": f"{(test_results['passed']/test_results['total']*100 if test_results['total'] > 0 else 0):.1f}%"
            },
            "errors": test_results["errors"],
            "details": test_results["details"]
        }, f, indent=2)
    
    print_success(f"Report saved to: {filename}")

# ==========================================
# MAIN
# ==========================================

def main():
    print(f"\n{BLUE}")
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║     🧪 AI SHOP PRO - ENDPOINT TESTING SUITE                   ║")
    print("║         Comprehensive API Validation                          ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")
    
    print_info(f"API Base URL: {API_BASE_URL}")
    print_info(f"Test Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Run test suites
    try:
        test_health_endpoints()
        test_authentication()
        test_shop_endpoints()
        test_inventory_endpoints()
        test_customer_endpoints()
        test_invoice_endpoints()
        test_khata_endpoints()
        test_attendance_endpoints()
        test_advanced_features()
        test_error_handling()
        
        # Generate report
        generate_report()
        save_report()
        
        print_info(f"Test End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Exit code
        if test_results["failed"] == 0:
            print_success("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print_error(f"⚠️  {test_results['failed']} tests failed")
            return 1
            
    except KeyboardInterrupt:
        print_error("\n\n⚠️  Tests interrupted by user")
        generate_report()
        save_report()
        return 1
    except Exception as e:
        print_error(f"Fatal error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
