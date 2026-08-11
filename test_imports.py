#!/usr/bin/env python3
"""Test app imports"""
import sys
import traceback

print("Testing app imports...")

try:
    print("1. Importing FastAPI...")
    from fastapi import FastAPI
    print("✓ FastAPI imported")
    
    print("2. Importing db...")
    from db import engine, get_db, Base
    print("✓ db imported")
    
    print("3. Importing models...")
    import models
    print("✓ models imported")
    
    print("4. Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized")
    
    print("5. Importing auth_routes...")
    from auth_routes import router as authentication_router
    print("✓ auth_routes imported")
    
    print("6. Importing auth_hardening_service...")
    from auth_hardening_service import router as auth_hardening_router
    print("✓ auth_hardening_service imported")
    
    print("7. Importing session_routes...")
    from session_routes import router as session_router
    print("✓ session_routes imported")
    
    print("8. Importing inventory...")
    from inventory import router as inventory_router
    print("✓ inventory imported")
    
    print("9. Importing inventory_sync_service...")
    from inventory_sync_service import router as inventory_sync_router
    print("✓ inventory_sync_service imported")
    
    print("10. Importing other routers...")
    from inventory_reconciliation_service import router as inventory_reconcile_router
    from sales_restore_service import router as sales_restore_router
    from attendance import router as attendance_router
    from invoices_billing import router as invoices_router
    from customers import router as customers_router
    from shop_management import router as shop_management_router
    from bill_generated import router as bill_router
    from shop_settings import router as shop_settings_router
    from khata_ledger import router as khata_router
    from purchase_orders import router as purchase_orders_router
    from online_store import router as online_store_router
    from retail_intelligence import router as intelligence_router
    from gst_and_giftcards import router as gst_and_giftcards_router
    from new_feature_routers import router as new_features_router
    from caching_system import router as caching_router
    from batch_operations import router as batch_operations_router
    from rate_limiting import router as rate_limiting_router
    from security_hardening import router as security_hardening_router
    from observability_service import router as observability_router
    print("✓ All routers imported")
    
    print("\n✓✓✓ ALL IMPORTS SUCCESSFUL ✓✓✓")
    
except Exception as e:
    print(f"\n✗✗✗ IMPORT FAILED ✗✗✗")
    print(f"Error: {type(e).__name__}: {str(e)}")
    traceback.print_exc()
    sys.exit(1)
