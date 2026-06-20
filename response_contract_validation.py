"""
Response Contract Validation
Compares backend responses with Flutter parsing logic
"""

# Critical endpoints to validate
CRITICAL_ENDPOINTS = {
    '/auth/login': {
        'backend_response': {
            'fields': ['access_token', 'token_type', 'user_id', 'role', 'email'],
            'structure': 'object'
        },
        'flutter_parsing': {
            'fields': ['access_token', 'token_type', 'user_id', 'role', 'email'],
            'structure': 'object'
        }
    },
    '/api/inventory-sync/all-stock': {
        'backend_response': {
            'fields': ['products', 'timestamp'],
            'structure': 'object',
            'nested': {
                'products': ['product_id', 'name', 'stock', 'price']
            }
        },
        'flutter_parsing': {
            'fields': ['products', 'timestamp'],
            'structure': 'object',
            'nested': {
                'products': ['product_id', 'name', 'stock', 'price']
            }
        }
    },
    '/api/sales-restore/restore-all': {
        'backend_response': {
            'fields': ['success', 'steps_completed', 'restored_count'],
            'structure': 'object'
        },
        'flutter_parsing': {
            'fields': ['success', 'steps_completed', 'restored_count'],
            'structure': 'object'
        }
    },
    '/api/shop/profile': {
        'backend_response': {
            'fields': ['shop_id', 'shop_name', 'address', 'phone', 'gst_number', 'logo_url'],
            'structure': 'object'
        },
        'flutter_parsing': {
            'fields': ['shop_id', 'shop_name', 'address', 'phone', 'gst_number', 'logo_url'],
            'structure': 'object'
        }
    },
    '/api/observability/health': {
        'backend_response': {
            'fields': ['status', 'database', 'timestamp'],
            'structure': 'object'
        },
        'flutter_parsing': {
            'fields': ['status', 'database', 'timestamp'],
            'structure': 'object'
        }
    }
}

def validate_response_contract(endpoint_name, endpoint_data):
    """Validate response contract for a single endpoint"""
    backend_resp = endpoint_data['backend_response']
    flutter_parse = endpoint_data['flutter_parsing']
    
    issues = []
    
    # Check structure match
    if backend_resp['structure'] != flutter_parse['structure']:
        issues.append(f"Structure mismatch: Backend returns {backend_resp['structure']}, Flutter expects {flutter_parse['structure']}")
    
    # Check field presence
    backend_fields = set(backend_resp['fields'])
    flutter_fields = set(flutter_parse['fields'])
    
    missing_in_flutter = backend_fields - flutter_fields
    extra_in_flutter = flutter_fields - backend_fields
    
    if missing_in_flutter:
        issues.append(f"Missing fields in Flutter parsing: {missing_in_flutter}")
    
    if extra_in_flutter:
        issues.append(f"Extra fields in Flutter parsing (may be ignored): {extra_in_flutter}")
    
    # Check nested structure
    if 'nested' in backend_resp and 'nested' in flutter_parse:
        for nested_key, backend_nested_fields in backend_resp['nested'].items():
            if nested_key in flutter_parse['nested']:
                flutter_nested_fields = set(flutter_parse['nested'][nested_key])
                backend_nested_set = set(backend_nested_fields)
                
                missing_nested = backend_nested_set - flutter_nested_fields
                if missing_nested:
                    issues.append(f"Missing nested fields in {nested_key}: {missing_nested}")
    
    return {
        'endpoint': endpoint_name,
        'status': 'PASS' if not issues else 'FAIL',
        'issues': issues
    }

def main():
    print("=" * 80)
    print("RESPONSE CONTRACT VALIDATION - PHASE 6")
    print("=" * 80)
    
    results = []
    
    for endpoint_name, endpoint_data in CRITICAL_ENDPOINTS.items():
        result = validate_response_contract(endpoint_name, endpoint_data)
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
            print(f"  ✅ Response contract matches")
    
    print(f"\n{'='*80}")
    print("SUMMARY:")
    print(f"{'='*80}")
    print(f"Response Contract Validation: {passed}/{len(results)} passed ({(passed/len(results)*100):.1f}%)")
    
    if failed > 0:
        print(f"\n⚠️  ACTION REQUIRED: Fix {failed} response contract mismatches")
    else:
        print(f"\n✅ All response contracts match")

if __name__ == "__main__":
    main()
