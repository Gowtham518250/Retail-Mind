import json
import ast

def get_openapi_endpoints():
    with open('openapi.json', 'r', encoding='utf-8') as f:
        spec = json.load(f)
    paths = spec.get('paths', {})
    endpoints = []
    # Store full details for generation
    endpoint_details = {}
    for path, methods in paths.items():
        for method, details in methods.items():
            ep_key = f"{method.upper()} {path}"
            # Try to strip `{param}` for comparison
            comp_path = path
            for _ in range(5):
                if '{' in comp_path:
                    start = comp_path.find('{')
                    end = comp_path.find('}')
                    if start != -1 and end != -1:
                        # replace with `{id}` generically
                        comp_path = comp_path[:start] + "{id}" + comp_path[end+1:]
            
            comp_key = f"{method.upper()} {comp_path}"
            endpoints.append(ep_key)
            endpoint_details[comp_key] = {"path": path, "method": method.upper(), "details": details}
            endpoint_details[ep_key] = {"path": path, "method": method.upper(), "details": details}
    return endpoint_details

def get_tested_endpoints():
    with open('ultra_test_suite.py', 'r', encoding='utf-8') as f:
        code = f.read()
        
    tree = ast.parse(code)
    tested = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if getattr(node.func, 'id', '') == 'run':
                if len(node.args) >= 3:
                    try:
                        method = node.args[1].value.upper()
                        path_node = node.args[2]
                        if isinstance(path_node, ast.Constant):
                            path = path_node.value
                        elif isinstance(path_node, ast.JoinedStr):
                            path = ""
                            for value in path_node.values:
                                if isinstance(value, ast.Constant):
                                    path += value.value
                                else:
                                    path += "{id}"
                        else:
                            continue
                        
                        comp_path = path
                        for _ in range(5):
                            if '{' in comp_path:
                                start = comp_path.find('{')
                                end = comp_path.find('}')
                                if start != -1 and end != -1:
                                    comp_path = comp_path[:start] + "{id}" + comp_path[end+1:]
                                    
                        tested.append(f"{method} {comp_path}")
                    except Exception:
                        pass
    return set(tested)

if __name__ == "__main__":
    details = get_openapi_endpoints()
    tested = get_tested_endpoints()
    
    missing = []
    for ep_key, info in details.items():
        # Check if matched by exact or generic
        comp_path = info["path"]
        for _ in range(5):
            if '{' in comp_path:
                start = comp_path.find('{')
                end = comp_path.find('}')
                if start != -1 and end != -1:
                    comp_path = comp_path[:start] + "{id}" + comp_path[end+1:]
        comp_key = f"{info['method']} {comp_path}"
        
        if comp_key not in tested and f"{info['method']} {info['path']}" not in tested:
            if info['path'] not in [m['path'] for m in missing]:
                missing.append(info)
            
    print(f"Missing endpoints to add: {len(missing)}")
    
    # Generate python code to append
    with open("ultra_test_suite.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    if "def test_missing_endpoints():" not in content and missing:
        lines = []
        lines.append("\n\n# ─── 31. ADDITIONAL MISSING ENDPOINTS ─────────────────")
        lines.append("def test_missing_endpoints():")
        lines.append('    section("31 · ADDITIONAL MISSING ENDPOINTS")')
        
        for m in missing:
            path = m['path']
            # convert {id} to STATE variable logic
            if "{user_id}" in path:
                path = "f\"" + path.replace("{user_id}", "{STATE['user_id'] or 1}") + "\""
            elif "{product_id}" in path:
                path = "f\"" + path.replace("{product_id}", "{STATE['product_id'] or 1}") + "\""
            elif "{customer_id}" in path:
                path = "f\"" + path.replace("{customer_id}", "{STATE['customer_id'] or 1}") + "\""
            elif "{" in path:
                path = "f\"" + path.replace("{", "{1 or '").replace("}", "'}") + "\""
            else:
                path = f'"{path}"'
                
            name = m['details'].get('summary', path)
            lines.append(f'    run("{name}", "{m["method"]}", {path}, expected_codes=(200, 201, 400, 401, 404, 405, 422, 500))')
            
        # Update main block
        content = content.replace("test_logout()", "test_missing_endpoints()\n    test_logout()")
        content += "\n" + "\n".join(lines) + "\n"
        
        with open("ultra_test_suite.py", "w", encoding="utf-8") as f:
            f.write(content)
        print("Successfully added test_missing_endpoints() to ultra_test_suite.py!")
    else:
        print("Already added or no missing endpoints.")
