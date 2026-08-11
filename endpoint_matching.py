"""
Endpoint Matching Script
Compares actual backend routes with Flutter endpoints and classifies matches
"""

# Actual backend routes from app.py registration
BACKEND_ROUTES = {
    'GET /': 'system',
    'GET /health': 'system',
    'POST /auth/register': 'authentication_router',
    'POST /auth/send-otp': 'authentication_router',
    'POST /auth/verify-otp': 'authentication_router',
    'POST /auth/login': 'authentication_router',
    'GET /auth/sales': 'authentication_router',
    'POST /bill/Generate/Bill': 'bill_router',
    'GET /bill/scan/{bill_id}': 'bill_router',
    'GET /bill/qr/{bill_id}': 'bill_router',
    'POST /api/inventory-sync/deduct-stock': 'inventory_sync_router',
    'POST /api/inventory-sync/deduct-stock-batch': 'inventory_sync_router',
    'POST /api/inventory-sync/reconcile': 'inventory_sync_router',
    'GET /api/inventory-sync/current-stock/{product_id}': 'inventory_sync_router',
    'GET /api/inventory-sync/all-stock': 'inventory_sync_router',
    'POST /api/sales-restore/restore-all': 'sales_restore_router',
    'GET /api/sales-restore/restore-summary': 'sales_restore_router',
    'POST /api/sales-restore/restore-customers': 'sales_restore_router',
    'POST /api/security/check-input': 'security_hardening_router',
    'GET /api/security/rate-limit-status': 'security_hardening_router',
    'POST /api/security/validate-password': 'security_hardening_router',
    'GET /api/security/security-headers': 'security_hardening_router',
    'POST /api/security/sanitize-batch': 'security_hardening_router',
    'GET /api/security/csrf-token': 'security_hardening_router',
    'GET /api/security/check-sql-injection': 'security_hardening_router',
    'GET /api/observability/health': 'observability_router',
    'GET /api/observability/ready': 'observability_router',
    'GET /api/observability/metrics': 'observability_router',
    'POST /api/observability/log': 'observability_router',
    'POST /api/observability/error': 'observability_router',
    'GET /api/observability/performance/summary': 'observability_router',
    'GET /api/observability/performance/database': 'observability_router',
    'GET /api/observability/business/overview': 'observability_router',
    'POST /store/customer/register': 'online_store_router',
    'POST /store/customer/login': 'online_store_router',
    'GET /store/shops/nearby': 'online_store_router',
    'GET /store/shops/{shop_id}/products': 'online_store_router',
    'POST /store/order': 'online_store_router',
    'GET /store/my-orders': 'online_store_router',
    'GET /store/order/{order_id}/track': 'online_store_router',
    'GET /store/owner/orders': 'online_store_router',
    'POST /store/owner/orders/{order_id}/action': 'online_store_router',
}

# Flutter endpoints from api_client.dart
FLUTTER_ENDPOINTS = {
    '/health': 'healthEndpoint',
    '/auth/register': 'registerEndpoint',
    '/auth/login': 'loginEndpoint',
    '/store/customer/login': 'customerLogin',
    '/store/customer/register': 'customerRegister',
    '/store/my-orders': 'myOrders',
    '/auth/sales': 'salesEndpoint',
    '/api/sales-restore/restore-all': 'salesRestoreRestoreAll',
    '/api/sales-restore/restore-summary': 'salesRestoreRestoreSummary',
    '/api/sales-restore/restore-customers': 'salesRestoreRestoreCustomers',
    '/auth/send-otp': 'authSendOtp',
    '/auth/verify-otp': 'authVerifyOtp',
    '/bill/Generate/Bill': 'billGenerateEndpoint',
    '/bill/scan/': 'billScanEndpoint',
    '/bill/qr/': 'billQrEndpoint',
    '/api/inventory-sync/deduct-stock': 'inventorySyncDeductStock',
    '/api/inventory-sync/deduct-stock-batch': 'inventorySyncDeductStockBatch',
    '/api/inventory-sync/reconcile': 'inventorySyncReconcile',
    '/api/inventory-sync/all-stock': 'inventorySyncAllStock',
    '/api/security/check-input': 'securityCheckInput',
    '/api/security/rate-limit-status': 'securityRateLimitStatus',
    '/api/security/validate-password': 'securityValidatePassword',
    '/api/security/security-headers': 'securitySecurityHeaders',
    '/api/security/sanitize-batch': 'securitySanitizeBatch',
    '/api/security/csrf-token': 'securityCsrfToken',
    '/api/security/check-sql-injection': 'securityCheckSqlInjection',
    '/api/observability/health': 'observabilityHealth',
    '/api/observability/ready': 'observabilityReady',
    '/api/observability/metrics': 'observabilityMetrics',
    '/api/observability/log': 'observabilityLog',
    '/api/observability/error': 'observabilityError',
    '/api/observability/performance/summary': 'observabilityPerformanceSummary',
    '/api/observability/performance/database': 'observabilityPerformanceDatabase',
    '/api/observability/business/overview': 'observabilityBusinessOverview',
}

def normalize_path(path):
    """Normalize path for comparison"""
    path = path.rstrip('/')
    return path.lower()

def match_endpoints():
    """Match Flutter endpoints with backend routes"""
    matched = []
    not_found = []
    path_mismatch = []
    
    for flutter_endpoint, flutter_name in FLUTTER_ENDPOINTS.items():
        normalized_flutter = normalize_path(flutter_endpoint)
        
        # Try to find exact match (ignore HTTP method for Flutter endpoints)
        exact_match = None
        for backend_route in BACKEND_ROUTES.keys():
            # Extract path from backend route (remove HTTP method)
            backend_path = backend_route.split(' ', 1)[1] if ' ' in backend_route else backend_route
            normalized_backend = normalize_path(backend_path)
            
            if normalized_flutter == normalized_backend:
                exact_match = backend_route
                break
        
        if exact_match:
            matched.append({
                'flutter_name': flutter_name,
                'flutter_endpoint': flutter_endpoint,
                'backend_route': exact_match,
                'status': 'MATCHED'
            })
        else:
            # Check for partial matches
            partial_matches = []
            for backend_route in BACKEND_ROUTES.keys():
                backend_path = backend_route.split(' ', 1)[1] if ' ' in backend_route else backend_route
                normalized_backend = normalize_path(backend_path)
                
                if normalized_flutter in normalized_backend or normalized_backend in normalized_flutter:
                    partial_matches.append(backend_route)
            
            if partial_matches:
                path_mismatch.append({
                    'flutter_name': flutter_name,
                    'flutter_endpoint': flutter_endpoint,
                    'possible_matches': partial_matches,
                    'status': 'PATH_MISMATCH'
                })
            else:
                not_found.append({
                    'flutter_name': flutter_name,
                    'flutter_endpoint': flutter_endpoint,
                    'status': 'NOT_FOUND'
                })
    
    return matched, not_found, path_mismatch

def main():
    print("=" * 80)
    print("ENDPOINT MATCHING - PHASE 3")
    print("=" * 80)
    
    matched, not_found, path_mismatch = match_endpoints()
    
    print(f"\nTOTAL BACKEND ROUTES: {len(BACKEND_ROUTES)}")
    print(f"TOTAL FLUTTER ENDPOINTS: {len(FLUTTER_ENDPOINTS)}")
    
    print(f"\n{'='*80}")
    print(f"MATCHED ENDPOINTS: {len(matched)}")
    print(f"{'='*80}")
    
    for match in matched:
        print(f"✅ {match['flutter_name']:40} -> {match['backend_route']}")
    
    print(f"\n{'='*80}")
    print(f"NOT FOUND ENDPOINTS: {len(not_found)}")
    print(f"{'='*80}")
    
    for not_found_item in not_found:
        print(f"❌ {not_found_item['flutter_name']:40} -> {not_found_item['flutter_endpoint']}")
    
    print(f"\n{'='*80}")
    print(f"PATH MISMATCH ENDPOINTS: {len(path_mismatch)}")
    print(f"{'='*80}")
    
    for mismatch in path_mismatch:
        print(f"⚠️  {mismatch['flutter_name']:40} -> {mismatch['flutter_endpoint']}")
        print(f"   Possible matches: {mismatch['possible_matches']}")
    
    print(f"\n{'='*80}")
    print("MATCHING SUMMARY:")
    print(f"{'='*80}")
    print(f"Matched: {len(matched)}")
    print(f"Not Found: {len(not_found)}")
    print(f"Path Mismatch: {len(path_mismatch)}")
    
    match_rate = (len(matched) / len(FLUTTER_ENDPOINTS) * 100) if FLUTTER_ENDPOINTS else 0
    print(f"Match Rate: {match_rate:.1f}%")

if __name__ == "__main__":
    main()
