"""
Comprehensive Test Suite for Inventory Sync Service
Tests the single source of truth inventory management system.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

# Import your app and models
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import api
from db import get_db
from models import Base, Product, StockMovement, User

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_inventory.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Override database dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

api.dependency_overrides[get_db] = override_get_db

client = TestClient(api)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    user = User(
        user_name="Test Shop Owner",
        email="test@example.com",
        password="hashed_password"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_product(db_session, test_user):
    """Create a test product"""
    product = Product(
        user_id=test_user.id,
        product_name="Test Product",
        sku="TEST-001",
        current_stock=20,
        min_stock=10,
        max_stock=100,
        unit_price=10.00,
        is_active=True
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


class TestInventorySyncService:
    """Test suite for Inventory Sync Service"""
    
    def test_deduct_stock_success(self, test_product, test_user):
        """Test successful stock deduction"""
        response = client.post(
            "/api/inventory-sync/deduct-stock",
            json={
                "product_id": test_product.id,
                "quantity": 5,
                "reason": "SALE",
                "reference_id": "TEST-INV-001",
                "idempotency_key": "test-key-001"
            },
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["new_stock"] == 15  # 20 - 5
        assert data["previous_stock"] == 20
    
    def test_deduct_stock_insufficient_stock(self, test_product, test_user):
        """Test stock deduction with insufficient stock"""
        response = client.post(
            "/api/inventory-sync/deduct-stock",
            json={
                "product_id": test_product.id,
                "quantity": 25,  # More than available (20)
                "reason": "SALE",
                "reference_id": "TEST-INV-002",
                "idempotency_key": "test-key-002"
            },
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Insufficient stock" in data["detail"]
    
    def test_deduct_stock_idempotency(self, test_product, test_user):
        """Test idempotency - duplicate deduction should not deduct twice"""
        # First deduction
        response1 = client.post(
            "/api/inventory-sync/deduct-stock",
            json={
                "product_id": test_product.id,
                "quantity": 5,
                "reason": "SALE",
                "reference_id": "TEST-INV-003",
                "idempotency_key": "test-key-003"
            },
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response1.status_code == 200
        assert response1.json()["new_stock"] == 15
        
        # Second deduction with same reference (should be idempotent)
        response2 = client.post(
            "/api/inventory-sync/deduct-stock",
            json={
                "product_id": test_product.id,
                "quantity": 5,
                "reason": "SALE",
                "reference_id": "TEST-INV-003",
                "idempotency_key": "test-key-003"
            },
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response2.status_code == 200
        assert response2.json()["success"] == True
        assert "Already processed" in response2.json()["message"]
        # Stock should still be 15, not 10
        assert response2.json()["new_stock"] == 15
    
    def test_batch_stock_deduction(self, db_session, test_user):
        """Test batch stock deduction for multiple products"""
        # Create multiple products
        product1 = Product(
            user_id=test_user.id,
            product_name="Product 1",
            sku="TEST-001",
            current_stock=20,
            min_stock=10,
            unit_price=10.00,
            is_active=True
        )
        product2 = Product(
            user_id=test_user.id,
            product_name="Product 2",
            sku="TEST-002",
            current_stock=15,
            min_stock=5,
            unit_price=15.00,
            is_active=True
        )
        db_session.add_all([product1, product2])
        db_session.commit()
        db_session.refresh(product1)
        db_session.refresh(product2)
        
        response = client.post(
            "/api/inventory-sync/deduct-stock-batch",
            json={
                "updates": [
                    {
                        "product_id": product1.id,
                        "quantity": 5,
                        "reason": "SALE",
                        "reference_id": "TEST-BATCH-001",
                        "idempotency_key": "batch-key-001"
                    },
                    {
                        "product_id": product2.id,
                        "quantity": 3,
                        "reason": "SALE",
                        "reference_id": "TEST-BATCH-001",
                        "idempotency_key": "batch-key-002"
                    }
                ]
            },
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["successful"] == 2
        assert data["failed"] == 0
    
    def test_get_current_stock(self, test_product, test_user):
        """Test getting current stock from backend"""
        response = client.get(
            f"/api/inventory-sync/current-stock/{test_product.id}",
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["product_id"] == test_product.id
        assert data["current_stock"] == test_product.current_stock
        assert data["product_name"] == test_product.product_name
    
    def test_get_all_stock(self, test_user, db_session):
        """Test getting all inventory from backend"""
        # Create multiple products
        for i in range(5):
            product = Product(
                user_id=test_user.id,
                product_name=f"Product {i}",
                sku=f"TEST-00{i}",
                current_stock=10 + i,
                min_stock=5,
                unit_price=10.00 + i,
                is_active=True
            )
            db_session.add(product)
        db_session.commit()
        
        response = client.get(
            "/api/inventory-sync/all-stock",
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_products"] >= 5
        assert len(data["products"]) >= 5
    
    def test_reconcile_inventory(self, test_product, test_user):
        """Test inventory reconciliation"""
        local_inventory = [
            {
                "id": test_product.id,
                "product_name": test_product.product_name,
                "current_stock": 25,  # Different from backend (20)
                "min_stock": test_product.min_stock
            }
        ]
        
        response = client.post(
            "/api/inventory-sync/reconcile",
            json={"local_inventory": local_inventory},
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["reconciled"] == True
        assert data["discrepancies_found"] == 1
        assert data["details"][0]["issue"] == "STOCK_MISMATCH"
        assert data["details"][0]["local_stock"] == 25
        assert data["details"][0]["backend_stock"] == 20


class TestInventoryReconciliationService:
    """Test suite for Inventory Reconciliation Service"""
    
    def test_full_reconciliation(self, db_session, test_user):
        """Test full inventory reconciliation"""
        # Create products with various stock levels
        products = []
        for i in range(10):
            product = Product(
                user_id=test_user.id,
                product_name=f"Reconcile Product {i}",
                sku=f"REC-00{i}",
                current_stock=20 + i,
                min_stock=10,
                unit_price=10.00,
                is_active=True
            )
            db_session.add(product)
            products.append(product)
        db_session.commit()
        
        # Create local inventory with some discrepancies
        local_inventory = []
        for i, p in enumerate(products):
            local_inventory.append({
                "id": p.id,
                "product_name": p.product_name,
                "current_stock": p.current_stock + 5,  # Add discrepancy
                "min_stock": p.min_stock
            })
        
        response = client.post(
            "/api/inventory-reconcile/full-reconciliation",
            json={"local_inventory": local_inventory},
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["reconciled"] == True
        assert data["discrepancies_found"] == 10
        assert data["fixes_applied"] == 10
    
    def test_stock_audit_trail(self, test_product, test_user, db_session):
        """Test stock audit trail"""
        # Create some stock movements
        movement1 = StockMovement(
            product_id=test_product.id,
            movement_type="IN",
            quantity=10,
            reason="Initial Stock",
            reference_id="INIT-001"
        )
        movement2 = StockMovement(
            product_id=test_product.id,
            movement_type="OUT",
            quantity=5,
            reason="Sale",
            reference_id="SALE-001"
        )
        db_session.add_all([movement1, movement2])
        db_session.commit()
        
        response = client.get(
            f"/api/inventory-reconcile/audit-trail/{test_product.id}",
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["product_id"] == test_product.id
        assert data["total_movements"] == 2
        assert len(data["movements"]) == 2
    
    def test_auto_fix_discrepancies(self, test_product, test_user):
        """Test auto-fix discrepancies"""
        response = client.post(
            "/api/inventory-reconcile/auto-fix-discrepancies",
            json={"local_inventory": []},
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "corrected_inventory" in data


class TestSalesRestoreService:
    """Test suite for Sales Restore Service"""
    
    def test_restore_all_sales(self, db_session, test_user):
        """Test restoring all sales from backend"""
        response = client.post(
            "/api/sales-restore/restore-all",
            json={
                "start_date": None,
                "end_date": None,
                "include_stock_impact": True
            },
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_invoices_restored" in data
        assert "total_line_items_restored" in data
    
    def test_restore_summary(self, test_user):
        """Test getting restore summary"""
        response = client.get(
            "/api/sales-restore/restore-summary",
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "available_for_restore" in data
        assert "invoice_summary" in data
    
    def test_restore_customers(self, test_user):
        """Test restoring customers"""
        response = client.post(
            "/api/sales-restore/restore-customers",
            headers={"Authorization": f"Bearer test-token-{test_user.id}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_customers_restored" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=.", "--cov-report=html"])
