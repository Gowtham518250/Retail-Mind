"""
API Mapping Validation Script
Compares backend endpoints with Flutter API client to identify connections
"""

import re
from typing import List, Dict, Any, Tuple

# Backend endpoints discovered (from Phase 1)
BACKEND_ENDPOINTS = {
    'auth_routes.py': [
        ('POST', '/register'),
        ('POST', '/send-otp'),
        ('POST', '/verify-otp'),
        ('POST', '/login'),
        ('GET', '/sales')
    ],
    'inventory.py': [
        ('POST', '/api/inventory/products'),
        ('GET', '/api/inventory/products'),
        ('GET', '/api/inventory/products/{product_id}'),
        ('PUT', '/api/inventory/products/{product_id}'),
        ('DELETE', '/api/inventory/products/{product_id}'),
        ('POST', '/api/inventory/stock-movement'),
        ('GET', '/api/inventory/stock-movements/{product_id}'),
        ('GET', '/api/inventory/low-stock'),
        ('GET', '/api/inventory/stock-alerts'),
        ('POST', '/api/inventory/batches'),
        ('GET', '/api/inventory/batches/{product_id}'),
        ('GET', '/api/inventory/expiring-batches'),
        ('GET', '/api/inventory/analytics/stock-value'),
        ('GET', '/api/inventory/analytics/inventory-status')
    ],
    'inventory_sync_service.py': [
        ('POST', '/api/inventory-sync/deduct-stock'),
        ('POST', '/api/inventory-sync/deduct-stock-batch'),
        ('POST', '/api/inventory-sync/reconcile'),
        ('GET', '/api/inventory-sync/current-stock/{product_id}'),
        ('GET', '/api/inventory-sync/all-stock')
    ],
    'sales_restore_service.py': [
        ('POST', '/api/sales-restore/restore-all'),
        ('GET', '/api/sales-restore/restore-summary'),
        ('POST', '/api/sales-restore/restore-customers')
    ],
    'attendance.py': [
        ('POST', '/api/attendance/workers'),
        ('GET', '/api/attendance/workers'),
        ('PUT', '/api/attendance/workers/{worker_id}'),
        ('DELETE', '/api/attendance/workers/{worker_id}'),
        ('POST', '/api/attendance/check-in'),
        ('POST', '/api/attendance/check-out'),
        ('POST', '/api/attendance/record-manual'),
        ('GET', '/api/attendance/employee/{employee_id}'),
        ('GET', '/api/attendance/date/{date_str}'),
        ('POST', '/api/attendance/leave-request'),
        ('GET', '/api/attendance/leave-requests'),
        ('PUT', '/api/attendance/leave-request/{leave_id}/approve'),
        ('PUT', '/api/attendance/leave-request/{leave_id}/reject'),
        ('GET', '/api/attendance/analytics/summary'),
        ('GET', '/api/attendance/analytics/employee/{employee_id}')
    ],
    'invoices_billing.py': [
        ('POST', '/api/invoices/sync'),
        ('GET', '/api/invoices'),
        ('GET', '/api/invoices/{invoice_id}'),
        ('POST', '/api/invoices/create'),
        ('GET', '/api/invoices/overdue'),
        ('GET', '/api/invoices/payments'),
        ('GET', '/api/invoices/analytics/summary'),
        ('DELETE', '/api/invoices/{invoice_id}')
    ],
    'customers.py': [
        ('POST', '/api/customers'),
        ('GET', '/api/customers'),
        ('GET', '/api/customers/{customer_id}'),
        ('PUT', '/api/customers/{customer_id}'),
        ('DELETE', '/api/customers/{customer_id}'),
        ('POST', '/api/customers/{customer_id}/set-contact-preference'),
        ('GET', '/api/customers/search/by-phone'),
        ('GET', '/api/customers/search/by-name')
    ],
    'shop_management.py': [
        ('POST', '/api/shop/create'),
        ('GET', '/api/shop/profile'),
        ('PUT', '/api/shop/profile'),
        ('DELETE', '/api/shop/profile'),
        ('PUT', '/api/shop/settings'),
        ('POST', '/api/shop/upload-logo'),
        ('GET', '/api/shop/business-hours'),
        ('GET', '/api/shop/tax-config')
    ],
    'observability_service.py': [
        ('GET', '/api/observability/health'),
        ('GET', '/api/observability/ready'),
        ('GET', '/api/observability/metrics'),
        ('POST', '/api/observability/log'),
        ('POST', '/api/observability/error'),
        ('GET', '/api/observability/performance/summary'),
        ('GET', '/api/observability/performance/database'),
        ('GET', '/api/observability/business/overview')
    ],
    'security_hardening.py': [
        ('POST', '/api/security/check-input'),
        ('GET', '/api/security/rate-limit-status'),
        ('POST', '/api/security/validate-password'),
        ('GET', '/api/security/security-headers'),
        ('POST', '/api/security/sanitize-batch'),
        ('GET', '/api/security/csrf-token'),
        ('GET', '/api/security/check-sql-injection')
    ]
}

# Flutter endpoints discovered (from Phase 2)
FLUTTER_ENDPOINTS = {
    'healthEndpoint': '/health',
    'registerEndpoint': '/auth/register',
    'loginEndpoint': '/auth/login',
    'salesEndpoint': '/auth/sales',
    'authSendOtp': '/auth/send-otp',
    'authVerifyOtp': '/auth/verify-otp',
    'inventoryProducts': '/api/inventory/products',
    'inventoryStockMovement': '/api/inventory/stock-movement',
    'inventoryLowStock': '/api/inventory/low-stock',
    'inventoryStockAlerts': '/api/inventory/stock-alerts',
    'inventoryBatches': '/api/inventory/batches',
    'inventoryExpiringBatches': '/api/inventory/expiring-batches',
    'inventoryStockValue': '/api/inventory/analytics/stock-value',
    'inventoryStatus': '/api/inventory/analytics/inventory-status',
    'attendanceWorkers': '/api/attendance/workers',
    'attendanceCheckIn': '/api/attendance/check-in',
    'attendanceCheckOut': '/api/attendance/check-out',
    'attendanceRecordManual': '/api/attendance/record-manual',
    'attendanceLeaveRequest': '/api/attendance/leave-request',
    'attendanceLeaveRequests': '/api/attendance/leave-requests',
    'attendanceSummary': '/api/attendance/analytics/summary',
    'invoicesCreate': '/api/invoices/create',
    'invoicesSync': '/api/invoices/sync',
    'invoicesOverdue': '/api/invoices/overdue',
    'invoicesPayments': '/api/invoices/payments',
    'invoicesAnalyticsSummary': '/api/invoices/analytics/summary',
    'invoicesList': '/api/invoices',
    'customersList': '/api/customers',
    'customerSearchByPhone': '/api/customers/search/by-phone',
    'customerSearchByName': '/api/customers/search/by-name',
    'sessionRefresh': '/api/session/refresh',
    'sessionLogoutAll': '/api/session/logout-all',
    'sessionOfflineQueue': '/api/session/offline/queue',
    'sessionOfflineSync': '/api/session/offline/sync',
    'sessionLogout': '/api/session/logout',
    'khataBalance': '/api/khata',
    'khataUpdate': '/api/khata/update',
    'khataCustomers': '/api/khata/customers',
    'expensesCreate': '/api/expenses/create',
    'expensesList': '/api/expenses',
    'expensesHistory': '/api/expenses/history',
    'syncSales': '/api/sync/sales',
    'syncInvoices': '/api/sync/invoices',
    'syncKhataBalances': '/api/sync/khata-balances',
    'syncExpenses': '/api/sync/expenses',
    'storeCustomerRegister': '/store/customer/register',
    'storeCustomerLogin': '/store/customer/login',
    'storeNearbyShops': '/store/shops/nearby',
    'storeOrderPlace': '/store/order',
    'storeMyOrders': '/store/my-orders',
    'storeOwnerOrders': '/store/owner/orders',
    'expensesAdd': '/expenses',
    'expensesListLegacy': '/expenses',
    'workersList': '/workers',
    'workersAdd': '/workers',
    'bankReconciliation': '/bank-recon',
    'enterprisePnl': '/enterprise/pnl',
    'enterpriseTransactions': '/enterprise/transactions',
    'retailStockAnalysis': '/retail/stock-analysis',
    'giftCards': '/gift-cards',
    'giftCardRedeem': '/gift-cards/redeem',
    'gstExportGstr1': '/gst/export-gstr1',
    'shopProfile': '/api/shop/profile',
    'shopSettings': '/api/shop/settings',
    'shopCreate': '/api/shop/create',
    'shopUpiQr': '/shop/upi-qr',
    'shopToggleOnlineStore': '/shop/toggle-online-store'
}

def normalize_endpoint(endpoint: str) -> str:
    """Normalize endpoint for comparison"""
    # Remove parameter placeholders for comparison
    return re.sub(r'\{[^}]+\}', '*', endpoint)

def find_matches():
    """Find matching and mismatched endpoints"""
    flutter_endpoints_set = set(FLUTTER_ENDPOINTS.values())
    
    matched = []
    backend_only = []
    flutter_only = []
    
    # Flatten backend endpoints
    all_backend = []
    for file, endpoints in BACKEND_ENDPOINTS.items():
        for method, path in endpoints:
            all_backend.append((file, method, path))
    
    # Check each backend endpoint
    for file, method, path in all_backend:
        normalized_path = normalize_endpoint(path)
        
        # Look for matching Flutter endpoint
        found = False
        for flutter_path in flutter_endpoints_set:
            normalized_flutter = normalize_endpoint(flutter_path)
            if normalized_path == normalized_flutter:
                matched.append((file, method, path, flutter_path))
                found = True
                break
        
        if not found:
            backend_only.append((file, method, path))
    
    # Check Flutter-only endpoints
    for flutter_name, flutter_path in FLUTTER_ENDPOINTS.items():
        normalized_flutter = normalize_endpoint(flutter_path)
        
        found = False
        for file, method, path in all_backend:
            normalized_path = normalize_endpoint(path)
            if normalized_path == normalized_flutter:
                found = True
                break
        
        if not found:
            flutter_only.append((flutter_name, flutter_path))
    
    return matched, backend_only, flutter_only

def main():
    print("=" * 80)
    print("API MAPPING VALIDATION")
    print("=" * 80)
    
    matched, backend_only, flutter_only = find_matches()
    
    print(f"\n✅ MATCHED ENDPOINTS: {len(matched)}")
    print(f"⚠️  BACKEND-ONLY ENDPOINTS: {len(backend_only)}")
    print(f"⚠️  FLUTTER-ONLY ENDPOINTS: {len(flutter_only)}")
    
    print(f"\n{'='*80}")
    print("BACKEND-ONLY ENDPOINTS (Not connected to Flutter):")
    print(f"{'='*80}")
    for file, method, path in backend_only:
        print(f"  {method} {path} ({file})")
    
    print(f"\n{'='*80}")
    print("FLUTTER-ONLY ENDPOINTS (Not found in backend):")
    print(f"{'='*80}")
    for name, path in flutter_only:
        print(f"  {name}: {path}")
    
    print(f"\n{'='*80}")
    print("CONNECTION RATE:")
    print(f"{'='*80}")
    total_backend = len(matched) + len(backend_only)
    connection_rate = (len(matched) / total_backend * 100) if total_backend > 0 else 0
    print(f"  Backend endpoints connected to Flutter: {len(matched)}/{total_backend} ({connection_rate:.1f}%)")

if __name__ == "__main__":
    main()
