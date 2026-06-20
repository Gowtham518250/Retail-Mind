"""
Actual Backend Route Discovery
Generates actual runtime route table from app.py router registration
"""

# Actual router registrations from app.py
ROUTER_REGISTRATIONS = {
    'authentication_router': {
        'prefix': '/auth',
        'source': 'auth_routes.py',
        'routes': [
            {'method': 'POST', 'path': '/register', 'function': 'register'},
            {'method': 'POST', 'path': '/send-otp', 'function': 'send_otp'},
            {'method': 'POST', 'path': '/verify-otp', 'function': 'verify_otp'},
            {'method': 'POST', 'path': '/login', 'function': 'login'},
            {'method': 'GET', 'path': '/sales', 'function': 'get_sales'}
        ]
    },
    'auth_hardening_router': {
        'prefix': '',
        'source': 'auth_hardening_service.py',
        'routes': [
            {'method': 'POST', 'path': '/register', 'function': 'register'},
            {'method': 'POST', 'path': '/login', 'function': 'login'},
            {'method': 'POST', 'path': '/refresh', 'function': 'refresh'},
            {'method': 'POST', 'path': '/logout', 'function': 'logout'},
            {'method': 'POST', 'path': '/logout-all', 'function': 'logout_all'},
            {'method': 'GET', 'path': '/active-sessions/{user_id}', 'function': 'active_sessions'}
        ]
    },
    'session_router': {
        'prefix': '',
        'source': 'session_routes.py',
        'routes': [
            {'method': 'POST', 'path': '/refresh', 'function': 'refresh'},
            {'method': 'POST', 'path': '/logout', 'function': 'logout'},
            {'method': 'POST', 'path': '/logout-all', 'function': 'logout_all'},
            {'method': 'GET', 'path': '/active/{user_id}', 'function': 'active'},
            {'method': 'POST', 'path': '/offline/queue', 'function': 'offline_queue'},
            {'method': 'POST', 'path': '/offline/sync', 'function': 'offline_sync'}
        ]
    },
    'bill_router': {
        'prefix': '/bill',
        'source': 'bill_generated.py',
        'routes': [
            {'method': 'POST', 'path': '/Generate/Bill', 'function': 'generate_bill'},
            {'method': 'GET', 'path': '/scan/{bill_id}', 'function': 'get_bill'},
            {'method': 'GET', 'path': '/qr/{bill_id}', 'function': 'get_qr_image'}
        ]
    },
    'inventory_router': {
        'prefix': '',
        'source': 'inventory.py',
        'routes': [
            {'method': 'POST', 'path': '/products', 'function': 'create_product'},
            {'method': 'GET', 'path': '/products', 'function': 'get_products'},
            {'method': 'GET', 'path': '/products/{product_id}', 'function': 'get_product'},
            {'method': 'PUT', 'path': '/products/{product_id}', 'function': 'update_product'},
            {'method': 'DELETE', 'path': '/products/{product_id}', 'function': 'delete_product'},
            {'method': 'POST', 'path': '/stock-movement', 'function': 'stock_movement'},
            {'method': 'GET', 'path': '/stock-movements/{product_id}', 'function': 'stock_movements'},
            {'method': 'GET', 'path': '/low-stock', 'function': 'low_stock'},
            {'method': 'GET', 'path': '/stock-alerts', 'function': 'stock_alerts'},
            {'method': 'POST', 'path': '/batches', 'function': 'create_batch'},
            {'method': 'GET', 'path': '/batches/{product_id}', 'function': 'get_batches'},
            {'method': 'GET', 'path': '/expiring-batches', 'function': 'expiring_batches'},
            {'method': 'GET', 'path': '/analytics/stock-value', 'function': 'stock_value'},
            {'method': 'GET', 'path': '/analytics/inventory-status', 'function': 'inventory_status'}
        ]
    },
    'inventory_sync_router': {
        'prefix': '',
        'source': 'inventory_sync_service.py',
        'routes': [
            {'method': 'POST', 'path': '/deduct-stock', 'function': 'deduct_stock'},
            {'method': 'POST', 'path': '/deduct-stock-batch', 'function': 'deduct_stock_batch'},
            {'method': 'POST', 'path': '/reconcile', 'function': 'reconcile'},
            {'method': 'GET', 'path': '/current-stock/{product_id}', 'function': 'current_stock'},
            {'method': 'GET', 'path': '/all-stock', 'function': 'all_stock'}
        ]
    },
    'inventory_reconcile_router': {
        'prefix': '',
        'source': 'inventory_reconciliation_service.py',
        'routes': [
            {'method': 'POST', 'path': '/full-reconciliation', 'function': 'full_reconciliation'},
            {'method': 'POST', 'path': '/correct-stock', 'function': 'correct_stock'},
            {'method': 'GET', 'path': '/audit-trail/{product_id}', 'function': 'audit_trail'},
            {'method': 'POST', 'path': '/auto-fix-discrepancies', 'function': 'auto_fix_discrepancies'}
        ]
    },
    'sales_restore_router': {
        'prefix': '',
        'source': 'sales_restore_service.py',
        'routes': [
            {'method': 'POST', 'path': '/restore-all', 'function': 'restore_all'},
            {'method': 'GET', 'path': '/restore-summary', 'function': 'restore_summary'},
            {'method': 'POST', 'path': '/restore-customers', 'function': 'restore_customers'}
        ]
    },
    'attendance_router': {
        'prefix': '',
        'source': 'attendance.py',
        'routes': [
            {'method': 'POST', 'path': '/workers', 'function': 'create_worker'},
            {'method': 'GET', 'path': '/workers', 'function': 'get_workers'},
            {'method': 'PUT', 'path': '/workers/{worker_id}', 'function': 'update_worker'},
            {'method': 'DELETE', 'path': '/workers/{worker_id}', 'function': 'delete_worker'},
            {'method': 'POST', 'path': '/check-in', 'function': 'check_in'},
            {'method': 'POST', 'path': '/check-out', 'function': 'check_out'},
            {'method': 'POST', 'path': '/record-manual', 'function': 'record_manual'},
            {'method': 'GET', 'path': '/employee/{employee_id}', 'function': 'get_employee'},
            {'method': 'GET', 'path': '/date/{date_str}', 'function': 'attendance_by_date'},
            {'method': 'POST', 'path': '/leave-request', 'function': 'leave_request'},
            {'method': 'GET', 'path': '/leave-requests', 'function': 'leave_requests'},
            {'method': 'PUT', 'path': '/leave-request/{leave_id}/approve', 'function': 'leave_approve'},
            {'method': 'PUT', 'path': '/leave-request/{leave_id}/reject', 'function': 'leave_reject'},
            {'method': 'GET', 'path': '/analytics/summary', 'function': 'analytics_summary'},
            {'method': 'GET', 'path': '/analytics/employee/{employee_id}', 'function': 'employee_analytics'}
        ]
    },
    'invoices_router': {
        'prefix': '',
        'source': 'invoices_billing.py',
        'routes': [
            {'method': 'POST', 'path': '/sync', 'function': 'sync'},
            {'method': 'GET', 'path': '/', 'function': 'list'},
            {'method': 'GET', 'path': '/{invoice_id}', 'function': 'get'},
            {'method': 'POST', 'path': '/create', 'function': 'create'},
            {'method': 'GET', 'path': '/overdue', 'function': 'overdue'},
            {'method': 'GET', 'path': '/payments', 'function': 'payments'},
            {'method': 'GET', 'path': '/analytics/summary', 'function': 'analytics_summary'},
            {'method': 'DELETE', 'path': '/{invoice_id}', 'function': 'delete'}
        ]
    },
    'customers_router': {
        'prefix': '',
        'source': 'customers.py',
        'routes': [
            {'method': 'POST', 'path': '/', 'function': 'create'},
            {'method': 'GET', 'path': '/', 'function': 'list'},
            {'method': 'GET', 'path': '/{customer_id}', 'function': 'get'},
            {'method': 'PUT', 'path': '/{customer_id}', 'function': 'update'},
            {'method': 'DELETE', 'path': '/{customer_id}', 'function': 'delete'},
            {'method': 'POST', 'path': '/{customer_id}/set-contact-preference', 'function': 'set_contact_preference'},
            {'method': 'GET', 'path': '/search/by-phone', 'function': 'search_by_phone'},
            {'method': 'GET', 'path': '/search/by-name', 'function': 'search_by_name'}
        ]
    },
    'shop_management_router': {
        'prefix': '',
        'source': 'shop_management.py',
        'routes': [
            {'method': 'POST', 'path': '/create', 'function': 'create'},
            {'method': 'GET', 'path': '/profile', 'function': 'get_profile'},
            {'method': 'PUT', 'path': '/profile', 'function': 'update_profile'},
            {'method': 'DELETE', 'path': '/profile', 'function': 'delete_profile'},
            {'method': 'PUT', 'path': '/settings', 'function': 'update_settings'},
            {'method': 'POST', 'path': '/upload-logo', 'function': 'upload_logo'},
            {'method': 'GET', 'path': '/business-hours', 'function': 'business_hours'},
            {'method': 'GET', 'path': '/tax-config', 'function': 'tax_config'}
        ]
    },
    'shop_settings_router': {
        'prefix': '/shop',
        'source': 'shop_settings.py',
        'routes': [
            {'method': 'POST', 'path': '/profile', 'function': 'profile'},
            {'method': 'GET', 'path': '/profile', 'function': 'profile'},
            {'method': 'PUT', 'path': '/profile', 'function': 'profile'},
            {'method': 'GET', 'path': '/upi-qr', 'function': 'upi_qr'},
            {'method': 'POST', 'path': '/toggle-online-store', 'function': 'toggle_online_store'},
            {'method': 'GET', 'path': '/public/{shop_id}', 'function': 'public_profile'}
        ]
    },
    'khata_router': {
        'prefix': '/khata',
        'source': 'khata_ledger.py',
        'routes': [
            {'method': 'POST', 'path': '/credit', 'function': 'credit'},
            {'method': 'POST', 'path': '/repayment', 'function': 'repayment'},
            {'method': 'GET', 'path': '/customers', 'function': 'customers'},
            {'method': 'GET', 'path': '/history/{customer_phone}', 'function': 'history'},
            {'method': 'GET', 'path': '/whatsapp-reminder/{customer_phone}', 'function': 'whatsapp_reminder'}
        ]
    },
    'purchase_orders_router': {
        'prefix': '/purchase-orders',
        'source': 'purchase_orders.py',
        'routes': [
            {'method': 'POST', 'path': '/', 'function': 'create'},
            {'method': 'GET', 'path': '/', 'function': 'list'},
            {'method': 'POST', 'path': '/{po_id}/mark-delivered', 'function': 'mark_delivered'},
            {'method': 'POST', 'path': '/{po_id}/cancel', 'function': 'cancel'}
        ]
    },
    'online_store_router': {
        'prefix': '/store',
        'source': 'online_store.py',
        'routes': [
            {'method': 'POST', 'path': '/customer/register', 'function': 'customer_register'},
            {'method': 'POST', 'path': '/customer/login', 'function': 'customer_login'},
            {'method': 'GET', 'path': '/shops/nearby', 'function': 'nearby_shops'},
            {'method': 'GET', 'path': '/shops/{shop_id}/products', 'function': 'shop_products'},
            {'method': 'POST', 'path': '/order', 'function': 'place_order'},
            {'method': 'GET', 'path': '/my-orders', 'function': 'my_orders'},
            {'method': 'GET', 'path': '/order/{order_id}/track', 'function': 'track_order'},
            {'method': 'GET', 'path': '/owner/orders', 'function': 'owner_orders'},
            {'method': 'POST', 'path': '/owner/orders/{order_id}/action', 'function': 'order_action'}
        ]
    },
    'intelligence_router': {
        'prefix': '',
        'source': 'retail_intelligence.py',
        'routes': [
            {'method': 'POST', 'path': '/expenses', 'function': 'expenses'},
            {'method': 'GET', 'path': '/expenses', 'function': 'expenses'},
            {'method': 'POST', 'path': '/workers', 'function': 'workers'},
            {'method': 'GET', 'path': '/workers', 'function': 'workers'},
            {'method': 'PUT', 'path': '/workers/{worker_id}', 'function': 'workers'},
            {'method': 'POST', 'path': '/workers/{worker_id}/pay-salary', 'function': 'pay_salary'},
            {'method': 'POST', 'path': '/bank-recon', 'function': 'bank_recon'},
            {'method': 'GET', 'path': '/bank-recon', 'function': 'bank_recon'},
            {'method': 'GET', 'path': '/enterprise/pnl', 'function': 'enterprise_pnl'},
            {'method': 'GET', 'path': '/enterprise/transactions', 'function': 'enterprise_transactions'},
            {'method': 'GET', 'path': '/retail/stock-analysis', 'function': 'stock_analysis'}
        ]
    },
    'gst_and_giftcards_router': {
        'prefix': '',
        'source': 'gst_and_giftcards.py',
        'routes': [
            {'method': 'POST', 'path': '/gift-cards', 'function': 'gift_cards'},
            {'method': 'POST', 'path': '/gift-cards/redeem', 'function': 'redeem'},
            {'method': 'GET', 'path': '/gst/export-gstr1', 'function': 'export_gstr1'}
        ]
    },
    'new_features_router': {
        'prefix': '/api',
        'source': 'new_feature_routers.py',
        'routes': [
            {'method': 'POST', 'path': '/counter/authenticate', 'function': 'counter_authenticate'},
            {'method': 'POST', 'path': '/delivery/create', 'function': 'delivery_create'},
            {'method': 'GET', 'path': '/delivery/today', 'function': 'delivery_today'},
            {'method': 'POST', 'path': '/delivery/{delivery_id}/update-status', 'function': 'delivery_update'},
            {'method': 'POST', 'path': '/loyalty/earn', 'function': 'loyalty_earn'},
            {'method': 'POST', 'path': '/loyalty/redeem', 'function': 'loyalty_redeem'},
            {'method': 'GET', 'path': '/festivals/upcoming', 'function': 'festivals_upcoming'},
            {'method': 'GET', 'path': '/occasions/today', 'function': 'occasions_today'},
            {'method': 'GET', 'path': '/collections/today-summary', 'function': 'collections_summary'},
            {'method': 'GET', 'path': '/templates', 'function': 'templates'},
            {'method': 'POST', 'path': '/templates/save', 'function': 'templates_save'},
            {'method': 'GET', 'path': '/credit-score/{customer_id}', 'function': 'credit_score'},
            {'method': 'GET', 'path': '/reports/daily', 'function': 'reports_daily'},
            {'method': 'POST', 'path': '/flash-sale/setup', 'function': 'flash_sale_setup'},
            {'method': 'GET', 'path': '/analytics/churn-risk', 'function': 'analytics_churn'},
            {'method': 'GET', 'path': '/inventory/generate-purchase-orders', 'function': 'generate_purchase_orders'},
            {'method': 'GET', 'path': '/khata/{customer_phone}', 'function': 'khata_balance'},
            {'method': 'GET', 'path': '/khata/customers', 'function': 'khata_customers'},
            {'method': 'POST', 'path': '/khata/update', 'function': 'khata_update'},
            {'method': 'POST', 'path': '/expenses/create', 'function': 'expenses_create'},
            {'method': 'GET', 'path': '/expenses', 'function': 'expenses_list'},
            {'method': 'GET', 'path': '/khata-history/{customer_phone}', 'function': 'khata_history'},
            {'method': 'GET', 'path': '/expenses/history', 'function': 'expenses_history'},
            {'method': 'GET', 'path': '/transactions/recent', 'function': 'transactions_recent'},
            {'method': 'GET', 'path': '/transactions/online-payments', 'function': 'transactions_online'},
            {'method': 'GET', 'path': '/data/backup/export', 'function': 'backup_export'},
            {'method': 'GET', 'path': '/data/integrity-check', 'function': 'integrity_check'},
            {'method': 'POST', 'path': '/sync/sales', 'function': 'sync_sales'},
            {'method': 'POST', 'path': '/sync/invoices', 'function': 'sync_invoices'},
            {'method': 'POST', 'path': '/sync/khata-balances', 'function': 'sync_khata'},
            {'method': 'POST', 'path': '/sync/expenses', 'function': 'sync_expenses'},
            {'method': 'POST', 'path': '/sync/invoices/chunked', 'function': 'sync_invoices_chunked'},
            {'method': 'DELETE', 'path': '/products/{product_id}', 'function': 'delete_product'},
            {'method': 'DELETE', 'path': '/customers/{customer_id}', 'function': 'delete_customer'}
        ]
    },
    'caching_router': {
        'prefix': '/cache',
        'source': 'caching_system.py',
        'routes': [
            {'method': 'GET', 'path': '/stats', 'function': 'get_cache_stats'},
            {'method': 'POST', 'path': '/warm/products', 'function': 'warm_products'},
            {'method': 'POST', 'path': '/warm/analytics', 'function': 'warm_analytics'},
            {'method': 'DELETE', 'path': '/clear/{pattern}', 'function': 'clear_pattern'},
            {'method': 'DELETE', 'path': '/clear-all', 'function': 'clear_all'}
        ]
    },
    'batch_operations_router': {
        'prefix': '/batch',
        'source': 'batch_operations.py',
        'routes': [
            {'method': 'POST', 'path': '/products/import', 'function': 'products_import'},
            {'method': 'POST', 'path': '/products/export', 'function': 'products_export'},
            {'method': 'POST', 'path': '/customers/import', 'function': 'customers_import'},
            {'method': 'GET', 'path': '/status/{operation_id}', 'function': 'status'},
            {'method': 'GET', 'path': '/history', 'function': 'history'}
        ]
    },
    'rate_limiting_router': {
        'prefix': '',
        'source': 'rate_limiting.py',
        'routes': [
            {'method': 'GET', 'path': '/status/{endpoint}', 'function': 'status'}
        ]
    },
    'security_hardening_router': {
        'prefix': '/api/security',
        'source': 'security_hardening.py',
        'routes': [
            {'method': 'POST', 'path': '/check-input', 'function': 'check_input'},
            {'method': 'GET', 'path': '/rate-limit-status', 'function': 'rate_limit_status'},
            {'method': 'POST', 'path': '/validate-password', 'function': 'validate_password'},
            {'method': 'GET', 'path': '/security-headers', 'function': 'security_headers'},
            {'method': 'POST', 'path': '/sanitize-batch', 'function': 'sanitize_batch'},
            {'method': 'GET', 'path': '/csrf-token', 'function': 'csrf_token'},
            {'method': 'GET', 'path': '/check-sql-injection', 'function': 'check_sql_injection'}
        ]
    },
    'observability_router': {
        'prefix': '/api/observability',
        'source': 'observability_service.py',
        'routes': [
            {'method': 'GET', 'path': '/health', 'function': 'health'},
            {'method': 'GET', 'path': '/ready', 'function': 'ready'},
            {'method': 'GET', 'path': '/metrics', 'function': 'metrics'},
            {'method': 'POST', 'path': '/log', 'function': 'log'},
            {'method': 'POST', 'path': '/error', 'function': 'error'},
            {'method': 'GET', 'path': '/performance/summary', 'function': 'performance_summary'},
            {'method': 'GET', 'path': '/performance/database', 'function': 'performance_database'},
            {'method': 'GET', 'path': '/business/overview', 'function': 'business_overview'}
        ]
    }
}

# System endpoints (defined directly in app.py)
SYSTEM_ENDPOINTS = [
    {'method': 'GET', 'path': '/', 'function': 'root', 'source': 'app.py'},
    {'method': 'GET', 'path': '/health', 'function': 'health_check', 'source': 'app.py'}
]

def generate_actual_routes():
    """Generate actual runtime route table"""
    actual_routes = []
    
    # Add system endpoints
    for endpoint in SYSTEM_ENDPOINTS:
        actual_routes.append({
            'method': endpoint['method'],
            'path': endpoint['path'],
            'full_path': endpoint['path'],
            'function': endpoint['function'],
            'source': endpoint['source'],
            'router': 'system'
        })
    
    # Add router endpoints
    for router_name, router_info in ROUTER_REGISTRATIONS.items():
        prefix = router_info['prefix']
        source = router_info['source']
        
        for route in router_info['routes']:
            method = route['method']
            path = route['path']
            function = route['function']
            
            # Combine prefix and path
            if prefix:
                full_path = f"{prefix}{path}"
            else:
                full_path = path
            
            actual_routes.append({
                'method': method,
                'path': path,
                'full_path': full_path,
                'function': function,
                'source': source,
                'router': router_name
            })
    
    return actual_routes

def main():
    print("=" * 80)
    print("ACTUAL BACKEND ROUTE TABLE FROM APP.PY REGISTRATION")
    print("=" * 80)
    
    actual_routes = generate_actual_routes()
    
    print(f"\nTOTAL BACKEND ROUTES: {len(actual_routes)}")
    
    print(f"\n{'='*80}")
    print("ROUTES BY ROUTER:")
    print(f"{'='*80}")
    
    router_counts = {}
    for route in actual_routes:
        router = route['router']
        router_counts[router] = router_counts.get(router, 0) + 1
    
    for router, count in sorted(router_counts.items()):
        print(f"{router}: {count} routes")
    
    print(f"\n{'='*80}")
    print("COMPLETE ROUTE TABLE:")
    print(f"{'='*80}")
    
    for route in actual_routes:
        print(f"{route['method']:6} {route['full_path']:50} [{route['router']}]")

if __name__ == "__main__":
    main()
