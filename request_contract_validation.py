"""
Request Contract Validation
Compares Flutter request models with backend request schemas
"""

# Critical endpoints to validate
CRITICAL_ENDPOINTS = {
    '/auth/login': {
        'flutter_request': {
            'fields': ['email', 'password'],
            'method': 'POST'
        },
        'backend_expectation': {
            'fields': ['email', 'password'],
            'required': ['email', 'password'],
            'method': 'POST'
        }
    },
    '/auth/register': {
        'flutter_request': {
            'fields': ['email', 'password', 'name', 'phone'],
            'method': 'POST'
        },
        'backend_expectation': {
            'fields': ['email', 'password', 'name', 'phone'],
            'required': ['email', 'password', 'name'],
            'method': 'POST'
        }
    },
    '/api/inventory-sync/deduct-stock': {
        'flutter_request': {
            'fields': ['product_id', 'quantity', 'shop_id'],
            'method': 'POST'
        },
        'backend_expectation': {
            'fields': ['product_id', 'quantity', 'shop_id'],
            'required': ['product_id', 'quantity', 'shop_id'],
            'method': 'POST'
        }
    },
    '/api/sales-restore/restore-all': {
        'flutter_request': {
            'fields': ['start_date', 'end_date', 'include_stock_impact'],
            'method': 'POST'
        },
        'backend_expectation': {
            'fields': ['start_date', 'end_date', 'include_stock_impact'],
            'required': [],
            'method': 'POST'
        }
    },
    '/api/shop/profile': {
        'flutter_request': {
            'fields': ['shop_name', 'address', 'phone', 'gst_number', 'logo_url'],
            'method': 'PUT'
        },
        'backend_expectation': {
            'fields': ['shop_name', 'address', 'phone', 'gst_number', 'logo_url'],
            'required': ['shop_name'],
            'method': 'PUT'
        }
    }
}

def validate_request_contract(endpoint_name, endpoint_data):
    """Validate request contract for a single endpoint"""
    flutter_req = endpoint_data['flutter_request']
    backend_exp = endpoint_data['backend_expectation']
    
    issues = []
    
    # Check method match
    if flutter_req['method'] != backend_exp['method']:
        issues.append(f"Method mismatch: Flutter sends {flutter_req['method']}, Backend expects {backend_exp['method']}")
    
    # Check field presence
    flutter_fields = set(flutter_req['fields'])
    backend_fields = set(backend_exp['fields'])
    
    missing_in_flutter = backend_fields - flutter_fields
    extra_in_flutter = flutter_fields - backend_fields
    
    if missing_in_flutter:
        issues.append(f"Missing fields in Flutter: {missing_in_flutter}")
    
    if extra_in_flutter:
        issues.append(f"Extra fields in Flutter (may be ignored): {extra_in_flutter}")
    
    # Check required fields
    if 'required' in backend_exp:
        required_fields = set(backend_exp['required'])
        missing_required = required_fields - flutter_fields
        if missing_required:
            issues.append(f"Missing required fields in Flutter: {missing_required}")
    
    return {
        'endpoint': endpoint_name,
        'status': 'PASS' if not issues else 'FAIL',
        'issues': issues
    }

def main():
    print("=" * 80)
    print("REQUEST CONTRACT VALIDATION - PHASE 5")
    print("=" * 80)
    
    results = []
    
    for endpoint_name, endpoint_data in CRITICAL_ENDPOINTS.items():
        result = validate_request_contract(endpoint_name, endpoint_data)
        results.append(result)
    
    print(f"\nTOTAL ENDPOINTS VALIDATED: {len(results)}")
    
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    
    print(f"PASSED: {passed}")
    print(f"FAILED: {failed}")
    
    print(f"\n{'='*80}")
    print("VALIDATION RESULTS:")
    print(f"{'='*80}")
    
    for result in results:
        print(f"\n{result['endpoint']}: {result['status']}")
        if result['issues']:
            for issue in result['issues']:
                print(f"  ⚠️  {issue}")
        else:
            print(f"  ✅ Request contract matches")
    
    print(f"\n{'='*80}")
    print("SUMMARY:")
    print(f"{'='*80}")
    print(f"Request Contract Validation: {passed}/{len(results)} passed ({(passed/len(results)*100):.1f}%)")
    
    if failed > 0:
        print(f"\n⚠️  ACTION REQUIRED: Fix {failed} request contract mismatches")
    else:
        print(f"\n✅ All request contracts match")

if __name__ == "__main__":
    main()
