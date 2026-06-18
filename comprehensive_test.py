import os
os.environ['DATABASE_URL'] = 'postgresql://retail_mind_xxog_user:hjvmy6P7OxYlA7rec54JLx6OL0LlLocc@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog'

from fastapi.testclient import TestClient
from app import api
import random

# Disable background tasks for testing by overriding
from fastapi import BackgroundTasks
class MockBackgroundTasks(BackgroundTasks):
    def add_task(self, func, *args, **kwargs):
        pass # Do nothing so we don't hang!

api.dependency_overrides[BackgroundTasks] = lambda: MockBackgroundTasks()

client = TestClient(api)
print("Starting Comprehensive API Audit...")

# 1. Setup Auth
username = f'audit{random.randint(10000,99999)}'
email = f'audit{random.randint(10000,99999)}@test.com'
password = 'Password123!'

print("1. Registering dummy user...")
client.post('/auth/register', json={'username': username, 'email': email, 'password': password})

print("2. Logging in...")
resp = client.post('/auth/login', json={'username': username, 'password': password})
token = ""
if resp.status_code == 200:
    token = resp.json().get('access_token', '')
    print("Login OK!")
else:
    print(f"Login Failed: {resp.text}")

headers = {"Authorization": f"Bearer {token}"} if token else {}

# 3. Test GET Endpoints
errors = []
success = 0

print("3. Scanning all GET endpoints...")
for route in api.routes:
    if hasattr(route, "methods") and "GET" in route.methods:
        path = route.path
        if "{" in path:
            # fill parameters
            path = path.replace("{shop_id}", "1").replace("{product_id}", "1").replace("{customer_id}", "1").replace("{invoice_id}", "1").replace("{session_id}", "1").replace("{supplier_id}", "1").replace("{order_id}", "1").replace("{user_id}", "1")
        
        # Don't test websockets or static files
        if "ws" in path or "static" in path or "openapi.json" in path:
            continue
            
        try:
            res = client.get(path, headers=headers)
            if res.status_code == 500:
                errors.append(f"GET {path} -> 500: {res.text}")
            else:
                success += 1
        except Exception as e:
            errors.append(f"GET {path} -> Exception: {str(e)}")

print(f"\nTested {success + len(errors)} GET endpoints. Success: {success}, Errors: {len(errors)}")
if errors:
    for e in errors[:10]: # Print top 10
        print(e)
