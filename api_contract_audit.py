"""
API Contract Audit Script
Performs comprehensive Frontend ↔ Backend API Contract Audit
"""

# Backend endpoints discovered (183 total)
BACKEND_ENDPOINTS = {
    'auth_routes': {
        'POST /register': 'UserCreate',
        'POST /send-otp': 'OtpRequest',
        'POST /verify-otp': 'OtpVerify',
        'POST /login': 'UserLogin',
        'GET /sales': 'SalesData'
    },
    'auth_hardening_service': {
        'POST /register': 'UserCreate',
        'POST /login': 'UserLogin',
        'POST /refresh': 'TokenRefresh',
        'POST /logout': 'Logout',
        'POST /logout-all': 'LogoutAll',
        'GET /active-sessions/{user_id}': 'ActiveSessions'
    },
    'session_routes': {
        'POST /refresh': 'TokenRefresh',
        'POST /logout': 'Logout',
        'POST /logout-all': 'LogoutAll',
        'GET /active/{user_id}': 'ActiveSession',
        'POST /offline/queue': 'OfflineQueue',
        'POST /offline/sync': 'OfflineSync'
    },
    'inventory': {
        'POST /products': 'ProductCreate',
        'GET /products': 'ProductList',
        'GET /products/{product_id}': 'ProductGet',
        'PUT /products/{product_id}': 'ProductUpdate',
        'DELETE /products/{product_id}': 'ProductDelete',
        'POST /stock-movement': 'StockMovement',
        'GET /stock-movements/{product_id}': 'StockMovements',
        'GET /low-stock': 'LowStock',
        'GET /stock-alerts': 'StockAlerts',
        'POST /batches': 'BatchCreate',
        'GET /batches/{product_id}': 'BatchGet',
        'GET /expiring-batches': 'ExpiringBatches',
        'GET /analytics/stock-value': 'StockValue',
        'GET /analytics/inventory-status': 'InventoryStatus'
    },
    'inventory_sync_service': {
        'POST /deduct-stock': 'StockDeduct',
        'POST /deduct-stock-batch': 'StockDeductBatch',
        'POST /reconcile': 'InventoryReconcile',
        'GET /current-stock/{product_id}': 'CurrentStock',
        'GET /all-stock': 'AllStock'
    },
    'sales_restore_service': {
        'POST /restore-all': 'RestoreAll',
        'GET /restore-summary': 'RestoreSummary',
        'POST /restore-customers': 'RestoreCustomers'
    },
    'attendance': {
        'POST /workers': 'WorkerCreate',
        'GET /workers': 'WorkerList',
        'PUT /workers/{worker_id}': 'WorkerUpdate',
        'DELETE /workers/{worker_id}': 'WorkerDelete',
        'POST /check-in': 'CheckIn',
        'POST /check-out': 'CheckOut',
        'POST /record-manual': 'RecordManual',
        'GET /employee/{employee_id}': 'EmployeeGet',
        'GET /date/{date_str}': 'AttendanceByDate',
        'POST /leave-request': 'LeaveRequest',
        'GET /leave-requests': 'LeaveRequests',
        'PUT /leave-request/{leave_id}/approve': 'LeaveApprove',
        'PUT /leave-request/{leave_id}/reject': 'LeaveReject',
        'GET /analytics/summary': 'AttendanceSummary',
        'GET /analytics/employee/{employee_id}': 'EmployeeAnalytics'
    },
    'invoices_billing': {
        'POST /sync': 'InvoiceSync',
        'GET /': 'InvoiceList',
        'GET /{invoice_id}': 'InvoiceGet',
        'POST /create': 'InvoiceCreate',
        'GET /overdue': 'OverdueInvoices',
        'GET /payments': 'InvoicePayments',
        'GET /analytics/summary': 'InvoiceAnalytics',
        'DELETE /{invoice_id}': 'InvoiceDelete'
    },
    'customers': {
        'POST /': 'CustomerCreate',
        'GET /': 'CustomerList',
        'GET /{customer_id}': 'CustomerGet',
        'PUT /{customer_id}': 'CustomerUpdate',
        'DELETE /{customer_id}': 'CustomerDelete',
        'POST /{customer_id}/set-contact-preference': 'SetContactPreference',
        'GET /search/by-phone': 'SearchByPhone',
        'GET /search/by-name': 'SearchByName'
    },
    'shop_management': {
        'POST /create': 'ShopCreate',
        'GET /profile': 'ShopProfile',
        'PUT /profile': 'ShopProfileUpdate',
        'DELETE /profile': 'ShopDelete',
        'PUT /settings': 'ShopSettings',
        'POST /upload-logo': 'UploadLogo',
        'GET /business-hours': 'BusinessHours',
        'GET /tax-config': 'TaxConfig'
    },
    'security_hardening': {
        'POST /check-input': 'CheckInput',
        'GET /rate-limit-status': 'RateLimitStatus',
        'POST /validate-password': 'ValidatePassword',
        'GET /security-headers': 'SecurityHeaders',
        'POST /sanitize-batch': 'SanitizeBatch',
        'GET /csrf-token': 'CsrfToken',
        'GET /check-sql-injection': 'CheckSqlInjection'
    },
    'observability_service': {
        'GET /health': 'HealthCheck',
        'GET /ready': 'ReadinessCheck',
        'GET /metrics': 'Metrics',
        'POST /log': 'LogEvent',
        'POST /error': 'LogError',
        'GET /performance/summary': 'PerformanceSummary',
        'GET /performance/database': 'DatabasePerformance',
        'GET /business/overview': 'BusinessOverview'
    }
}

# Flutter endpoints discovered (137 constants in api_client.dart)
FLUTTER_ENDPOINTS = {
    'healthEndpoint': '/health',
    'registerEndpoint': '/auth/register',
    'loginEndpoint': '/auth/login',
    'customerLogin': '/store/customer/login',
    'customerRegister': '/store/customer/register',
    'myOrders': '/store/my-orders',
    'salesEndpoint': '/auth/sales',
    'salesRestoreRestoreAll': '/api/sales-restore/restore-all',
    'salesRestoreRestoreSummary': '/api/sales-restore/restore-summary',
    'salesRestoreRestoreCustomers': '/api/sales-restore/restore-customers',
    'authSendOtp': '/auth/send-otp',
    'authVerifyOtp': '/auth/verify-otp',
    'ragEndpoint': '/rag/upload',
    'ragListEndpoint': '/rag/list_files',
    'sqlAnalystEndpoint': '/sql_analyst/analysis/',
    'chatbotEndpoint': '/chatbot/',
    'billGenerateEndpoint': '/bill/Generate/Bill',
    'billScanEndpoint': '/bill/scan/',
    'billQrEndpoint': '/bill/qr/',
    'todayInsightEndpoint': '/today_insight/',
    'inventorySyncDeductStock': '/api/inventory-sync/deduct-stock',
    'inventorySyncDeductStockBatch': '/api/inventory-sync/deduct-stock-batch',
    'inventorySyncReconcile': '/api/inventory-sync/reconcile',
    'inventorySyncAllStock': '/api/inventory-sync/all-stock',
    'securityCheckInput': '/api/security/check-input',
    'securityRateLimitStatus': '/api/security/rate-limit-status',
    'securityValidatePassword': '/api/security/validate-password',
    'securitySecurityHeaders': '/api/security/security-headers',
    'securitySanitizeBatch': '/api/security/sanitize-batch',
    'securityCsrfToken': '/api/security/csrf-token',
    'securityCheckSqlInjection': '/api/security/check-sql-injection',
    'observabilityHealth': '/api/observability/health',
    'observabilityReady': '/api/observability/ready',
    'observabilityMetrics': '/api/observability/metrics',
    'observabilityLog': '/api/observability/log',
    'observabilityError': '/api/observability/error',
    'observabilityPerformanceSummary': '/api/observability/performance/summary',
    'observabilityPerformanceDatabase': '/api/observability/performance/database',
    'observabilityBusinessOverview': '/api/observability/business/overview'
}

def normalize_endpoint(endpoint):
    """Normalize endpoint for comparison"""
    # Remove trailing slashes
    endpoint = endpoint.rstrip('/')
    # Convert to lowercase for comparison
    return endpoint.lower()

def find_dead_flutter_endpoints():
    """Find Flutter endpoints that don't exist in backend"""
    dead_endpoints = []
    
    # Flatten backend endpoints
    backend_set = set()
    for router, endpoints in BACKEND_ENDPOINTS.items():
        for endpoint in endpoints.keys():
            # Add router prefix if needed
            if router == 'auth_routes':
                normalized = normalize_endpoint(f'/auth/{endpoint}')
            elif router == 'inventory':
                normalized = normalize_endpoint(f'/api/inventory/{endpoint}')
            elif router == 'inventory_sync_service':
                normalized = normalize_endpoint(f'/api/inventory-sync/{endpoint}')
            elif router == 'sales_restore_service':
                normalized = normalize_endpoint(f'/api/sales-restore/{endpoint}')
            elif router == 'security_hardening':
                normalized = normalize_endpoint(f'/api/security/{endpoint}')
            elif router == 'observability_service':
                normalized = normalize_endpoint(f'/api/observability/{endpoint}')
            elif router == 'attendance':
                normalized = normalize_endpoint(f'/api/attendance/{endpoint}')
            elif router == 'invoices_billing':
                normalized = normalize_endpoint(f'/api/invoices/{endpoint}')
            elif router == 'customers':
                normalized = normalize_endpoint(f'/api/customers/{endpoint}')
            elif router == 'shop_management':
                normalized = normalize_endpoint(f'/api/shop/{endpoint}')
            else:
                normalized = normalize_endpoint(f'/api/{endpoint}')
            backend_set.add(normalized)
    
    # Check Flutter endpoints
    for flutter_name, flutter_endpoint in FLUTTER_ENDPOINTS.items():
        normalized_flutter = normalize_endpoint(flutter_endpoint)
        
        # Check if exists in backend
        found = False
        for backend_endpoint in backend_set:
            if normalized_flutter == backend_endpoint:
                found = True
                break
        
        if not found:
            dead_endpoints.append({
                'flutter_name': flutter_name,
                'flutter_endpoint': flutter_endpoint,
                'normalized': normalized_flutter
            })
    
    return dead_endpoints

def main():
    print("=" * 80)
    print("API CONTRACT AUDIT - PHASE 3: DEAD FLUTTER ENDPOINTS")
    print("=" * 80)
    
    dead_endpoints = find_dead_flutter_endpoints()
    
    print(f"\nTOTAL FLUTTER ENDPOINTS: {len(FLUTTER_ENDPOINTS)}")
    print(f"DEAD ENDPOINTS FOUND: {len(dead_endpoints)}")
    
    if dead_endpoints:
        print(f"\n{'='*80}")
        print("DEAD FLUTTER ENDPOINTS (Flutter has, Backend does NOT):")
        print(f"{'='*80}")
        
        for dead in dead_endpoints:
            print(f"\n❌ {dead['flutter_name']}")
            print(f"   Flutter Endpoint: {dead['flutter_endpoint']}")
            print(f"   Normalized: {dead['normalized']}")
            print(f"   Recommendation: REMOVE from api_client.dart")
    else:
        print(f"\n✅ NO DEAD ENDPOINTS FOUND - All Flutter endpoints have backend counterparts")

if __name__ == "__main__":
    main()
