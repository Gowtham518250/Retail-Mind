"""
Flutter API Discovery Script
Analyzes Flutter project to identify API services and endpoint usage
"""

import os
import re
from typing import List, Dict, Any

FLUTTER_LIB_PATH = r'd:\AI_Shop_Latest_Source_June1\lib'

def extract_api_calls_from_dart(filepath: str) -> List[Dict[str, Any]]:
    """Extract API calls from a Dart file"""
    api_calls = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find API client method calls
        api_patterns = [
            r'ApiClient\.\w+\(',
            r'await client\.(get|post|put|delete|patch)\(',
            r'http\.(get|post|put|delete|patch)\(',
            r'ApiClient\.\w+Endpoint',
            r'\.get\(',
            r'\.post\(',
            r'\.put\(',
            r'\.delete\(',
        ]
        
        for pattern in api_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                api_calls.append({
                    'file': os.path.basename(filepath),
                    'pattern': match.group(0),
                    'line': content[:match.start()].count('\n') + 1
                })
                
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    
    return api_calls

def find_service_files():
    """Find all service files in Flutter project"""
    service_files = []
    
    for root, dirs, files in os.walk(FLUTTER_LIB_PATH):
        for file in files:
            if file.endswith('.dart') and ('service' in file.lower() or 'api' in file.lower()):
                service_files.append(os.path.join(root, file))
    
    return service_files

def main():
    print("=" * 80)
    print("FLUTTER API DISCOVERY")
    print("=" * 80)
    
    # Find service files
    service_files = find_service_files()
    print(f"\nFound {len(service_files)} service/API files:")
    
    for file in service_files:
        print(f"  {os.path.basename(file)}")
    
    # Analyze main API client
    api_client_path = os.path.join(FLUTTER_LIB_PATH, 'api_client.dart')
    if os.path.exists(api_client_path):
        print(f"\nAnalyzing main API client: api_client.dart")
        
        with open(api_client_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract endpoint constants
        endpoint_pattern = r'static const String (\w+) = [\'"]([^\'"]+)[\'"]'
        endpoints = re.findall(endpoint_pattern, content)
        
        print(f"\nFound {len(endpoints)} endpoint constants in api_client.dart:")
        for name, path in endpoints:
            print(f"  {name}: {path}")
    
    # Analyze service files
    print(f"\nAnalyzing service files for API usage patterns...")
    total_api_calls = 0
    
    for service_file in service_files:
        api_calls = extract_api_calls_from_dart(service_file)
        if api_calls:
            print(f"\n{os.path.basename(service_file)}: {len(api_calls)} API calls")
            total_api_calls += len(api_calls)
    
    print(f"\nTotal API calls found across service files: {total_api_calls}")

if __name__ == "__main__":
    main()
