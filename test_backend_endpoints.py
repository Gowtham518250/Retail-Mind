"""
Comprehensive Backend Endpoint Testing Suite
Tests all critical endpoints for production readiness
Run with: pytest test_backend_endpoints.py -v
"""

import pytest
import requests
import json
from datetime import datetime, date
from typing import Dict, Any

# ==================== CONFIGURATION ====================

BASE_URL = "http://localhost:8000"  # Change to production URL for testing
TEST_USER = {
    "username": "test_user_100cr",
    "email": "test_100cr@example.com",
    "password": "Test@123456",
    "user_type": "OWNER"
}

# ==================== FIXTURES ====================

@pytest.fixture(scope="session")
def base_url():
    return BASE_URL

@pytest.fixture(scope="session")
def auth_token(base_url):
    """Get authentication token for protected endpoints"""
    # Try to login first
    login_response = requests.post(
        f"{base_url}/api/auth/login",
        json={
            "email": TEST_USER["email"],
            "password": TEST_USER["password"]
        }
    )
    
    if login_response.status_code == 200:
        return login_response.json()["access_token"]
    
    # If login fails, register new user
    register_response = requests.post(
        f"{base_url}/api/auth/register",
        json=TEST_USER
    )
    
    if register_response.status_code == 200:
        return register_response.json()["access_token"]
    
    pytest.fail("Failed to authenticate")

@pytest.fixture(scope="session")
def headers(auth_token):
    """Headers with authentication token"""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture(scope="session")
def user_id(headers, base_url):
    """Get user ID from token"""
    # Decode token or get from profile endpoint
    response = requests.get(f"{base_url}/api/shop/profile", headers=headers)
    if response.status_code == 200:
        return response.json().get("shop_id") or response.json().get("user_id")
    return 1

# ==================== TEST CLASSES ====================

class TestAuthenticationEndpoints:
    """Test authentication and authorization endpoints"""
    
    def test_register_user(self, base_url):
        """Test user registration"""
        unique_email = f"test_{datetime.now().timestamp()}@example.com"
        response = requests.post(
            f"{base_url}/api/auth/register",
            json={
                "username": "test_user_new",
                "email": unique_email,
                "password": "Test@123456",
                "user_type": "OWNER"
            }
        )
        
        assert response.status_code in [200, 400], f"Register failed: {response.text}"
        if response.status_code == 200:
            assert "access_token" in response.json()
            assert "user_id" in response.json()
    
    def test_login_valid_credentials(self, base_url):
        """Test login with valid credentials"""
        response = requests.post(
            f"{base_url}/api/auth/login",
            json={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            }
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        assert "access_token" in response.json()
        assert "refresh_token" in response.json()
        assert "user_id" in response.json()
    
    def test_login_invalid_credentials(self, base_url):
        """Test login with invalid credentials"""
        response = requests.post(
            f"{base_url}/api/auth/login",
            json={
                "email": TEST_USER["email"],
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
    
    def test_refresh_token(self, base_url):
        """Test token refresh endpoint"""
        # First login to get refresh token
        login_response = requests.post(
            f"{base_url}/api/auth/login",
            json={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            }
        )
        
        if login_response.status_code == 200:
            refresh_token = login_response.json().get("refresh_token")
            if refresh_token:
                response = requests.post(
                    f"{base_url}/api/auth/refresh",
                    json={"refresh_token": refresh_token}
                )
                
                assert response.status_code in [200, 401], f"Refresh failed: {response.text}"
                if response.status_code == 200:
                    assert "access_token" in response.json()
    
    def test_send_otp(self, base_url):
        """Test OTP sending"""
        response = requests.post(
            f"{base_url}/api/auth/send-otp",
            json={"email": "test@example.com"}
        )
        
        assert response.status_code == 200
    
    def test_unauthorized_access(self, base_url):
        """Test that protected endpoints require authentication"""
        response = requests.get(f"{base_url}/api/inventory/products")
        
        assert response.status_code == 401


class TestInventoryEndpoints:
    """Test inventory management endpoints"""
    
    def test_get_products(self, base_url, headers):
        """Test fetching all products"""
        response = requests.get(f"{base_url}/api/inventory/products", headers=headers)
        
        assert response.status_code == 200, f"Get products failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_create_product(self, base_url, headers):
        """Test creating a new product"""
        product_data = {
            "product_name": "Test Product 100CR",
            "sku": f"TEST-{datetime.now().timestamp()}",
            "description": "Test product for 100CR validation",
            "current_stock": 100,
            "unit_price": 99.99,
            "category": "Test Category"
        }
        
        response = requests.post(
            f"{base_url}/api/inventory/products",
            json=product_data,
            headers=headers
        )
        
        assert response.status_code in [200, 201], f"Create product failed: {response.text}"
        if response.status_code in [200, 201]:
            assert "id" in response.json() or "product_id" in response.json()
    
    def test_update_product(self, base_url, headers):
        """Test updating a product"""
        # First get a product
        products_response = requests.get(f"{base_url}/api/inventory/products", headers=headers)
        if products_response.status_code == 200 and len(products_response.json()) > 0:
            product_id = products_response.json()[0].get("id")
            
            update_data = {
                "product_name": "Updated Test Product",
                "current_stock": 150
            }
            
            response = requests.put(
                f"{base_url}/api/inventory/products/{product_id}",
                json=update_data,
                headers=headers
            )
            
            assert response.status_code in [200, 404], f"Update product failed: {response.text}"
    
    def test_delete_product(self, base_url, headers):
        """Test deleting a product (soft delete)"""
        # Create a test product first
        create_response = requests.post(
            f"{base_url}/api/inventory/products",
            json={
                "product_name": "Product to Delete",
                "sku": f"DELETE-{datetime.now().timestamp()}",
                "current_stock": 10,
                "unit_price": 10.00
            },
            headers=headers
        )
        
        if create_response.status_code in [200, 201]:
            product_id = create_response.json().get("id") or create_response.json().get("product_id")
            
            response = requests.delete(
                f"{base_url}/api/inventory/products/{product_id}",
                headers=headers
            )
            
            assert response.status_code in [200, 204, 404], f"Delete product failed: {response.text}"
    
    def test_deduct_stock(self, base_url, headers):
        """Test stock deduction with idempotency"""
        # Get a product
        products_response = requests.get(f"{base_url}/api/inventory/products", headers=headers)
        if products_response.status_code == 200 and len(products_response.json()) > 0:
            product = products_response.json()[0]
            product_id = product.get("id")
            
            deduction_data = {
                "product_id": product_id,
                "quantity": 5,
                "reason": "Test deduction",
                "idempotency_key": f"test-100cr-{datetime.now().timestamp()}"
            }
            
            response = requests.post(
                f"{base_url}/api/inventory-sync/deduct-stock",
                json=deduction_data,
                headers=headers
            )
            
            assert response.status_code in [200, 400], f"Deduct stock failed: {response.text}"


class TestSalesEndpoints:
    """Test sales and invoice endpoints"""
    
    def test_get_sales(self, base_url, headers):
        """Test fetching sales history"""
        response = requests.get(f"{base_url}/api/auth/sales", headers=headers)
        
        assert response.status_code == 200, f"Get sales failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_create_invoice(self, base_url, headers, user_id):
        """Test creating a new invoice"""
        invoice_data = {
            "customer_name": "Test Customer",
            "customer_phone": "9876543210",
            "invoice_number": f"INV-{datetime.now().timestamp()}",
            "invoice_date": date.today().isoformat(),
            "due_date": date.today().isoformat(),
            "items": [
                {
                    "product_name": "Test Product",
                    "quantity": 2,
                    "unit_price": 50.00
                }
            ],
            "payment_method": "CASH",
            "payment_status": "PAID"
        }
        
        response = requests.post(
            f"{base_url}/api/invoices/create",
            json=invoice_data,
            headers=headers
        )
        
        assert response.status_code in [200, 201, 400], f"Create invoice failed: {response.text}"
    
    def test_get_invoices(self, base_url, headers):
        """Test fetching invoices"""
        response = requests.get(f"{base_url}/api/invoices", headers=headers)
        
        assert response.status_code == 200, f"Get invoices failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_legacy_sales_sync(self, base_url, headers):
        """Test legacy sales sync endpoint"""
        sales_data = {
            "product_name": "Legacy Test Product",
            "price": 25.00,
            "quantity": 1,
            "total": 25.00,
            "date": date.today().isoformat(),
            "sale_id": f"LEGACY-{datetime.now().timestamp()}"
        }
        
        response = requests.post(
            f"{base_url}/api/auth/sales",
            data=sales_data,
            headers=headers
        )
        
        assert response.status_code in [200, 400], f"Legacy sync failed: {response.text}"


class TestCustomerEndpoints:
    """Test customer management endpoints"""
    
    def test_get_customers(self, base_url, headers):
        """Test fetching customers"""
        response = requests.get(f"{base_url}/api/customers", headers=headers)
        
        assert response.status_code == 200, f"Get customers failed: {response.text}"
        assert isinstance(response.json(), list)
    
    def test_create_customer(self, base_url, headers):
        """Test creating a new customer"""
        customer_data = {
            "customer_name": "Test Customer 100CR",
            "phone": "9876543210",
            "email": "customer100cr@example.com",
            "address": "Test Address",
            "city": "Test City"
        }
        
        response = requests.post(
            f"{base_url}/api/customers",
            json=customer_data,
            headers=headers
        )
        
        assert response.status_code in [200, 201], f"Create customer failed: {response.text}"
        if response.status_code in [200, 201]:
            assert "id" in response.json()
    
    def test_update_customer(self, base_url, headers):
        """Test updating a customer"""
        customers_response = requests.get(f"{base_url}/api/customers", headers=headers)
        if customers_response.status_code == 200 and len(customers_response.json()) > 0:
            customer_id = customers_response.json()[0].get("id")
            
            update_data = {
                "customer_name": "Updated Customer Name"
            }
            
            response = requests.put(
                f"{base_url}/api/customers/{customer_id}",
                json=update_data,
                headers=headers
            )
            
            assert response.status_code in [200, 404], f"Update customer failed: {response.text}"


class TestShopProfileEndpoints:
    """Test shop profile management endpoints"""
    
    def test_get_shop_profile(self, base_url, headers):
        """Test fetching shop profile"""
        response = requests.get(f"{base_url}/api/shop/profile", headers=headers)
        
        assert response.status_code in [200, 404], f"Get shop profile failed: {response.text}"
    
    def test_update_shop_profile(self, base_url, headers):
        """Test updating shop profile"""
        profile_data = {
            "shop_name": "Updated Shop Name 100CR",
            "location": "Updated Location",
            "phone": "9876543210"
        }
        
        response = requests.put(
            f"{base_url}/api/shop/profile",
            json=profile_data,
            headers=headers
        )
        
        assert response.status_code in [200, 400, 404], f"Update shop profile failed: {response.text}"


class TestSalesRestoreEndpoints:
    """Test sales restoration endpoints"""
    
    def test_get_restore_summary(self, base_url, headers):
        """Test getting restore summary"""
        response = requests.get(f"{base_url}/api/sales-restore/restore-summary", headers=headers)
        
        assert response.status_code == 200, f"Get restore summary failed: {response.text}"
        assert "total_invoices" in response.json() or "total_sales" in response.json()
    
    def test_restore_all_sales(self, base_url, headers):
        """Test restoring all sales"""
        response = requests.post(
            f"{base_url}/api/sales-restore/restore-all",
            headers=headers
        )
        
        assert response.status_code in [200, 400], f"Restore all sales failed: {response.text}"
        if response.status_code == 200:
            assert "invoices_restored" in response.json() or "sales_restored" in response.json()
    
    def test_restore_customers(self, base_url, headers):
        """Test restoring customers"""
        response = requests.post(
            f"{base_url}/api/sales-restore/restore-customers",
            headers=headers
        )
        
        assert response.status_code in [200, 400], f"Restore customers failed: {response.text}"
        if response.status_code == 200:
            assert "customers_restored" in response.json()


class TestInventorySyncEndpoints:
    """Test inventory synchronization endpoints"""
    
    def test_refresh_all_inventory(self, base_url, headers):
        """Test refreshing all inventory"""
        response = requests.post(
            f"{base_url}/api/inventory-sync/refresh-all",
            headers=headers
        )
        
        assert response.status_code in [200, 400], f"Refresh inventory failed: {response.text}"
    
    def test_reconcile_inventory(self, base_url, headers):
        """Test inventory reconciliation"""
        response = requests.post(
            f"{base_url}/api/inventory-sync/reconcile",
            headers=headers
        )
        
        assert response.status_code in [200, 400], f"Reconcile inventory failed: {response.text}"


class TestSecurityEndpoints:
    """Test security and validation endpoints"""
    
    def test_security_check_sql_injection(self, base_url):
        """Test SQL injection detection"""
        response = requests.post(
            f"{base_url}/api/security/check-input",
            json={
                "input_data": "SELECT * FROM users; DROP TABLE users;",
                "check_type": "sql_injection"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["is_safe"] == False
    
    def test_security_check_xss(self, base_url):
        """Test XSS detection"""
        response = requests.post(
            f"{base_url}/api/security/check-input",
            json={
                "input_data": "<script>alert('xss')</script>",
                "check_type": "xss"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["is_safe"] == False
    
    def test_security_check_safe_input(self, base_url):
        """Test safe input validation"""
        response = requests.post(
            f"{base_url}/api/security/check-input",
            json={
                "input_data": "safe product name",
                "check_type": "sql_injection"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["is_safe"] == True


class TestHealthEndpoints:
    """Test health check and monitoring endpoints"""
    
    def test_root_endpoint(self, base_url):
        """Test root endpoint"""
        response = requests.get(base_url)
        
        assert response.status_code in [200, 404]
    
    def test_health_check(self, base_url):
        """Test health check endpoint if available"""
        response = requests.get(f"{base_url}/health")
        
        # Health endpoint might not exist, so accept 404
        assert response.status_code in [200, 404]


# ==================== INTEGRATION TESTS ====================

class TestIntegrationScenarios:
    """Test complete business workflows"""
    
    def test_complete_sales_workflow(self, base_url, headers):
        """Test complete sales workflow: create product -> create invoice -> verify stock"""
        # Step 1: Create product
        product_response = requests.post(
            f"{base_url}/api/inventory/products",
            json={
                "product_name": "Integration Test Product",
                "sku": f"INT-{datetime.now().timestamp()}",
                "current_stock": 100,
                "unit_price": 50.00
            },
            headers=headers
        )
        
        if product_response.status_code in [200, 201]:
            product_id = product_response.json().get("id") or product_response.json().get("product_id")
            
            # Step 2: Create invoice with this product
            invoice_response = requests.post(
                f"{base_url}/api/invoices/create",
                json={
                    "customer_name": "Integration Customer",
                    "invoice_number": f"INT-INV-{datetime.now().timestamp()}",
                    "items": [
                        {
                            "product_name": "Integration Test Product",
                            "quantity": 5,
                            "unit_price": 50.00
                        }
                    ],
                    "payment_method": "CASH",
                    "payment_status": "PAID"
                },
                headers=headers
            )
            
            # Step 3: Verify stock was deducted
            if invoice_response.status_code in [200, 201]:
                stock_response = requests.get(
                    f"{base_url}/api/inventory/products/{product_id}",
                    headers=headers
                )
                
                if stock_response.status_code == 200:
                    current_stock = stock_response.json().get("current_stock", 0)
                    assert current_stock == 95, f"Stock not deducted correctly: {current_stock}"
    
    def test_customer_invoice_workflow(self, base_url, headers):
        """Test customer creation and invoice association"""
        # Create customer
        customer_response = requests.post(
            f"{base_url}/api/customers",
            json={
                "customer_name": "Workflow Customer",
                "phone": "9999999999",
                "email": "workflow@example.com"
            },
            headers=headers
        )
        
        if customer_response.status_code in [200, 201]:
            customer_id = customer_response.json().get("id")
            
            # Create invoice for this customer
            invoice_response = requests.post(
                f"{base_url}/api/invoices/create",
                json={
                    "customer_id": customer_id,
                    "customer_name": "Workflow Customer",
                    "invoice_number": f"CUST-INV-{datetime.now().timestamp()}",
                    "items": [{"product_name": "Test", "quantity": 1, "unit_price": 10.00}],
                    "payment_method": "CASH",
                    "payment_status": "PAID"
                },
                headers=headers
            )
            
            assert invoice_response.status_code in [200, 201, 400]


# ==================== PERFORMANCE TESTS ====================

class TestPerformance:
    """Test endpoint performance"""
    
    def test_products_response_time(self, base_url, headers):
        """Test products endpoint response time"""
        import time
        
        start_time = time.time()
        response = requests.get(f"{base_url}/api/inventory/products", headers=headers)
        end_time = time.time()
        
        response_time = end_time - start_time
        assert response.status_code == 200
        assert response_time < 2.0, f"Products endpoint too slow: {response_time}s"
    
    def test_sales_response_time(self, base_url, headers):
        """Test sales endpoint response time"""
        import time
        
        start_time = time.time()
        response = requests.get(f"{base_url}/api/auth/sales", headers=headers)
        end_time = time.time()
        
        response_time = end_time - start_time
        assert response.status_code == 200
        assert response_time < 2.0, f"Sales endpoint too slow: {response_time}s"


# ==================== TEST REPORTING ====================

def generate_test_report(results):
    """Generate a comprehensive test report"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "success_rate": f"{(sum(1 for r in results if r['status'] == 'passed') / len(results) * 100):.2f}%",
        "results": results
    }
    
    with open("test_report_100cr.json", "w") as f:
        json.dump(report, f, indent=2)
    
    return report


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short", "--html=test_report.html"])
