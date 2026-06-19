"""
Backend Endpoint Discovery Script
Systematically scans all backend router files to extract complete endpoint information
"""

import os
import re
import ast
from typing import List, Dict, Any

# List of all router files to analyze
ROUTER_FILES = [
    'auth_routes.py',
    'auth_hardening_service.py', 
    'session_routes.py',
    'inventory.py',
    'inventory_sync_service.py',
    'inventory_reconciliation_service.py',
    'sales_restore_service.py',
    'attendance.py',
    'invoices_billing.py',
    'customers.py',
    'shop_management.py',
    'bill_generated.py',
    'shop_settings.py',
    'khata_ledger.py',
    'purchase_orders.py',
    'online_store.py',
    'retail_intelligence.py',
    'gst_and_giftcards.py',
    'new_feature_routers.py',
    'caching_system.py',
    'batch_operations.py',
    'rate_limiting.py',
    'security_hardening.py',
    'observability_service.py'
]

def extract_endpoints_from_file(filepath: str) -> List[Dict[str, Any]]:
    """Extract endpoint information from a router file"""
    endpoints = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all @router decorators
        router_pattern = r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'
        matches = re.finditer(router_pattern, content)
        
        for match in matches:
            method = match.group(1).upper()
            path = match.group(2)
            
            # Extract function definition after decorator
            func_pattern = r'def\s+(\w+)\s*\([^)]*\):'
            func_match = re.search(func_pattern, content[match.end():match.end()+200])
            func_name = func_match.group(1) if func_match else "unknown"
            
            endpoints.append({
                'file': os.path.basename(filepath),
                'method': method,
                'path': path,
                'function': func_name,
                'line': content[:match.start()].count('\n') + 1
            })
            
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    
    return endpoints

def main():
    print("=" * 80)
    print("BACKEND ENDPOINT DISCOVERY")
    print("=" * 80)
    
    all_endpoints = []
    
    for router_file in ROUTER_FILES:
        filepath = os.path.join('D:\\deploy-retail-mind', router_file)
        if os.path.exists(filepath):
            endpoints = extract_endpoints_from_file(filepath)
            all_endpoints.extend(endpoints)
            print(f"\n{router_file}: {len(endpoints)} endpoints")
            for ep in endpoints:
                print(f"  {ep['method']} {ep['path']} -> {ep['function']}")
        else:
            print(f"\n{router_file}: FILE NOT FOUND")
    
    print("\n" + "=" * 80)
    print(f"TOTAL ENDPOINTS DISCOVERED: {len(all_endpoints)}")
    print("=" * 80)
    
    # Categorize by method
    methods = {}
    for ep in all_endpoints:
        methods[ep['method']] = methods.get(ep['method'], 0) + 1
    
    print("\nENDPOINTS BY METHOD:")
    for method, count in sorted(methods.items()):
        print(f"  {method}: {count}")
    
    # Categorize by file
    files = {}
    for ep in all_endpoints:
        files[ep['file']] = files.get(ep['file'], 0) + 1
    
    print("\nENDPOINTS BY FILE:")
    for file, count in sorted(files.items(), key=lambda x: x[1], reverse=True):
        print(f"  {file}: {count}")

if __name__ == "__main__":
    main()
