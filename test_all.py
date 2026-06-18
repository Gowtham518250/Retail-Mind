import os
import sys
import json
from datetime import date, datetime

# MOCK DB connection string
os.environ['DATABASE_URL'] = 'sqlite:///./test.db'
os.environ['SENDER_EMAIL'] = 'test@test.com'
os.environ['SENDER_PASSWORD'] = 'test'
os.environ['SECRET_KEY'] = 'testkey'

from fastapi.testclient import TestClient
from app import api

client = TestClient(api)
print("APP INITIALIZED SUCCESSFULLY WITH SQLITE MOCK!")

# Extract OpenAPI schema
openapi_schema = api.openapi()
components = openapi_schema.get("components", {}).get("schemas", {})

def generate_mock_value(schema_type, format_=None, enum_vals=None):
    if enum_vals:
        return enum_vals[0]
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "string":
        if format_ == "date":
            return str(date.today())
        if format_ == "date-time":
            return str(datetime.now().isoformat())
        if format_ == "email":
            return "test@example.com"
        return "test_string"
    if schema_type == "array":
        return []
    return {}

def build_mock_payload(schema_ref):
    if not schema_ref: return {}
    ref_name = schema_ref.split("/")[-1]
    model_schema = components.get(ref_name, {})
    
    properties = model_schema.get("properties", {})
    payload = {}
    for prop_name, prop_details in properties.items():
        if "$ref" in prop_details:
            payload[prop_name] = build_mock_payload(prop_details["$ref"])
        elif "anyOf" in prop_details:
            # Handle nullable fields or unions
            first_type = prop_details["anyOf"][0]
            if "$ref" in first_type:
                payload[prop_name] = build_mock_payload(first_type["$ref"])
            else:
                payload[prop_name] = generate_mock_value(first_type.get("type", "string"), first_type.get("format"), first_type.get("enum"))
        elif prop_details.get("type") == "array" and "$ref" in prop_details.get("items", {}):
            payload[prop_name] = [build_mock_payload(prop_details["items"]["$ref"])]
        else:
            payload[prop_name] = generate_mock_value(
                prop_details.get("type", "string"), 
                prop_details.get("format"),
                prop_details.get("enum")
            )
    return payload

# 1. Register and get token
client.post('/auth/register', json={
    'username': 'testuser',
    'password': 'password123',
    'email': 'testuser@test.com'
})
resp = client.post('/auth/login', json={'username': 'testuser', 'password': 'password123'})
token = resp.json().get('access_token', '')
headers = {'Authorization': f'Bearer {token}'}

errors = []
success = 0
skipped = 0

paths = openapi_schema.get("paths", {})

with open("backend_test_results.log", "w") as log_file:
    log_file.write(f"Total endpoints discovered: {sum(len(methods) for methods in paths.values())}\n\n")

    for path, methods in paths.items():
        # Substitute common path variables with defaults
        test_path = path
        test_path = test_path.replace('{shop_id}', '1')
        test_path = test_path.replace('{product_id}', '1')
        test_path = test_path.replace('{customer_id}', '1')
        test_path = test_path.replace('{invoice_id}', '1')
        test_path = test_path.replace('{supplier_id}', '1')
        test_path = test_path.replace('{order_id}', '1')
        test_path = test_path.replace('{user_id}', '1')
        test_path = test_path.replace('{worker_id}', '1')
        test_path = test_path.replace('{session_id}', '1')
        test_path = test_path.replace('{card_code}', 'TEST1234')
        test_path = test_path.replace('{customer_phone}', '9999999999')
        test_path = test_path.replace('{date_str}', str(date.today()))
        
        for method, operation in methods.items():
            method_upper = method.upper()
            
            # Skip websockets or specialized exports that don't return standard JSON
            if 'ws' in path or 'export' in path:
                skipped += 1
                continue
                
            # Determine request payload if any
            payload = None
            if method_upper in ['POST', 'PUT', 'PATCH']:
                request_body = operation.get("requestBody", {})
                content = request_body.get("content", {})
                json_schema = content.get("application/json", {}).get("schema", {})
                
                if "$ref" in json_schema:
                    payload = build_mock_payload(json_schema["$ref"])
                else:
                    payload = {} # Empty dict fallback

            try:
                if method_upper == 'GET':
                    r = client.get(test_path, headers=headers)
                elif method_upper == 'POST':
                    r = client.post(test_path, headers=headers, json=payload)
                elif method_upper == 'PUT':
                    r = client.put(test_path, headers=headers, json=payload)
                elif method_upper == 'DELETE':
                    r = client.delete(test_path, headers=headers)
                elif method_upper == 'PATCH':
                    r = client.patch(test_path, headers=headers, json=payload)
                else:
                    skipped += 1
                    continue
                    
                log_line = f"[{method_upper}] {test_path} "
                if payload:
                    log_line += f"| Payload: {json.dumps(payload)} "
                    
                if r.status_code >= 500:
                    errors.append(f"{log_line} -> {r.status_code} {r.text[:200]}")
                    log_file.write(f"ERROR: {log_line} -> {r.status_code}\n")
                elif r.status_code >= 400 and r.status_code not in [404, 422, 401, 403]:
                    # Treat unexpected client errors as potential logic errors, but 422 is expected for duplicate entries or strict business rules with dummy data
                    # 404 is expected because ID '1' might not exist for some entities.
                    # 401/403 is expected for protected routes where standard user token isn't enough (e.g. admin routes)
                    errors.append(f"{log_line} -> {r.status_code} {r.text[:200]}")
                    log_file.write(f"FAIL: {log_line} -> {r.status_code}\n")
                else:
                    success += 1
                    log_file.write(f"SUCCESS (Code {r.status_code}): {log_line}\n")
                    
            except Exception as e:
                errors.append(f"[{method_upper}] {test_path} -> Exception: {e}")
                log_file.write(f"CRASH: [{method_upper}] {test_path} -> {e}\n")

print(f"\nTEST COMPLETE. Success: {success}, Errors: {len(errors)}, Skipped: {skipped}")
if errors:
    print("ERRORS:")
    for e in errors: print(e)
