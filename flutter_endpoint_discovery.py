"""
Flutter Endpoint Discovery
Scans api_client.dart and service files to discover all Flutter endpoints
"""

import re
import os
from pathlib import Path

# Flutter project directory
FLUTTER_DIR = r"d:\AI_Shop_Latest_Source_June1\lib"

def extract_endpoints_from_api_client():
    """Extract endpoint constants from api_client.dart"""
    api_client_path = os.path.join(FLUTTER_DIR, "api_client.dart")
    
    if not os.path.exists(api_client_path):
        return []
    
    with open(api_client_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all endpoint constants
    pattern = r'static const String (\w+)\s*=\s*[\'"]([^\'"]+)[\'"]'
    matches = re.findall(pattern, content)
    
    endpoints = []
    for name, endpoint in matches:
        endpoints.append({
            'name': name,
            'endpoint': endpoint,
            'source': 'api_client.dart',
            'type': 'constant'
        })
    
    return endpoints

def extract_api_calls_from_services():
    """Extract API calls from service files"""
    service_files = []
    
    # Find all service files
    for root, dirs, files in os.walk(FLUTTER_DIR):
        for file in files:
            if file.endswith('_service.dart') or file.endswith('_client.dart'):
                service_files.append(os.path.join(root, file))
    
    api_calls = []
    
    for service_file in service_files:
        relative_path = os.path.relpath(service_file, FLUTTER_DIR)
        
        try:
            with open(service_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find API calls
            # Pattern: ApiClient.get/post/put/delete("endpoint")
            api_pattern = r'ApiClient\.(get|post|put|delete)(Json)?\s*\(\s*[\'"]([^\'"]+)[\'"]'
            matches = re.findall(api_pattern, content)
            
            for method, json_type, endpoint in matches:
                api_calls.append({
                    'method': method.upper(),
                    'endpoint': endpoint,
                    'source': relative_path,
                    'type': 'api_call'
                })
            
            # Find direct HTTP calls
            http_pattern = r'http\.(get|post|put|delete)\s*\(\s*[\'"]([^\'"]+)[\'"]'
            http_matches = re.findall(http_pattern, content)
            
            for method, endpoint in http_matches:
                api_calls.append({
                    'method': method.upper(),
                    'endpoint': endpoint,
                    'source': relative_path,
                    'type': 'http_call'
                })
                
        except Exception as e:
            print(f"Error reading {service_file}: {e}")
    
    return api_calls

def main():
    print("=" * 80)
    print("FLUTTER ENDPOINT DISCOVERY")
    print("=" * 80)
    
    # Extract from api_client.dart
    api_client_endpoints = extract_endpoints_from_api_client()
    print(f"\nENDPOINT CONSTANTS FROM api_client.dart: {len(api_client_endpoints)}")
    
    # Extract from service files
    service_api_calls = extract_api_calls_from_services()
    print(f"API CALLS FROM SERVICE FILES: {len(service_api_calls)}")
    
    print(f"\n{'='*80}")
    print("API CLIENT CONSTANTS:")
    print(f"{'='*80}")
    
    for endpoint in api_client_endpoints:
        print(f"{endpoint['name']:40} -> {endpoint['endpoint']}")
    
    print(f"\n{'='*80}")
    print("SERVICE API CALLS:")
    print(f"{'='*80}")
    
    for call in service_api_calls:
        print(f"{call['method']:6} {call['endpoint']:50} [{call['source']}]")
    
    print(f"\n{'='*80}")
    print("SUMMARY:")
    print(f"{'='*80}")
    print(f"Total Endpoint Constants: {len(api_client_endpoints)}")
    print(f"Total API Calls: {len(service_api_calls)}")
    print(f"Total Unique Endpoints: {len(set(e['endpoint'] for e in api_client_endpoints + service_api_calls))}")

if __name__ == "__main__":
    main()
