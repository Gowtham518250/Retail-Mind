import json
import ast

def get_openapi_endpoints():
    with open('openapi.json', 'r', encoding='utf-8') as f:
        spec = json.load(f)
    paths = spec.get('paths', {})
    endpoints = []
    for path, methods in paths.items():
        for method in methods.keys():
            # Standardize path
            standard_path = path.replace('{', '').replace('}', '')
            endpoints.append(f"{method.upper()} {path}")
    return set(endpoints)

def get_tested_endpoints():
    with open('ultra_test_suite.py', 'r', encoding='utf-8') as f:
        code = f.read()
        
    tree = ast.parse(code)
    tested = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == 'run':
                # signature: run(label, method, path, ...)
                if len(node.args) >= 3:
                    try:
                        method = node.args[1].value.upper()
                        # path could be f-string or string
                        path_node = node.args[2]
                        if isinstance(path_node, ast.Constant):
                            path = path_node.value
                        elif isinstance(path_node, ast.JoinedStr):
                            # extract static parts
                            path = ""
                            for value in path_node.values:
                                if isinstance(value, ast.Constant):
                                    path += value.value
                                else:
                                    path += "{var}"
                        else:
                            continue
                            
                        # Try to match generalized path
                        tested.append(f"{method} {path}")
                    except Exception:
                        pass
    return set(tested)

if __name__ == "__main__":
    try:
        import requests
        resp = requests.get("https://retail-mind-vkbp.onrender.com/openapi.json")
        with open('openapi.json', 'w') as f:
            json.dump(resp.json(), f)
    except:
        pass

    openapi = get_openapi_endpoints()
    tested = get_tested_endpoints()
    
    # Simple matching (this is heuristic because of path vars)
    print(f"Total OpenAPI endpoints: {len(openapi)}")
    print(f"Total Tested endpoints found in script: {len(tested)}")
    
    # Let's list a few openapi endpoints that might be missed
    print("\n--- OPENAPI ENDPOINTS ---")
    for ep in sorted(list(openapi)):
        print(ep)
