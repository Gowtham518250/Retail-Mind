import os
import sys
import warnings

warnings.filterwarnings("ignore")

# Use external PostgreSQL database for testing
os.environ['DATABASE_URL'] = 'postgresql://retail_mind_xxog_user:hjvmy6P7OxYlA7rec54JLx6OL0LlLocc@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog?sslmode=require'

from fastapi.testclient import TestClient
from app import api
import random
from email_notifications import EmailNotificationService

EmailNotificationService.send_email = lambda *args, **kwargs: True

# Skip table creation - schema already exists from Alembic migration
# from db import Base, engine
# Base.metadata.create_all(bind=engine)

client = TestClient(api)
print("Starting SQLite Comprehensive Endpoint Test...")

username = f'testuser{random.randint(10000,99999)}'
email = f'test{random.randint(10000,99999)}@test.com'
password = 'Password123!'

resp_reg = client.post('/auth/register', json={'username': username, 'email': email, 'password': password})
print(f"Register: {resp_reg.status_code}")

resp_login = client.post('/auth/login', json={'username': username, 'password': password})
print(f"Login: {resp_login.status_code}")
token = resp_login.json().get('access_token', '') if resp_login.status_code == 200 else ""

headers = {"Authorization": f"Bearer {token}"} if token else {}

errors_500 = []
tested_count = 0

for route in api.routes:
    if hasattr(route, "methods"):
        path = route.path
        if not path.startswith("/"): continue
        
        test_path = path.replace("{shop_id}", "1").replace("{product_id}", "1").replace("{customer_id}", "1").replace("{invoice_id}", "1").replace("{session_id}", "1").replace("{phone}", "9999999999").replace("{tx_id}", "1").replace("{module_name}", "auth")
        
        for method in route.methods:
            if method in ["GET", "POST", "PUT", "DELETE"]:
                try:
                    res = None
                    if method == "GET":
                        res = client.get(test_path, headers=headers)
                    elif method == "POST":
                        res = client.post(test_path, headers=headers, json={})
                    elif method == "PUT":
                        res = client.put(test_path, headers=headers, json={})
                    elif method == "DELETE":
                        res = client.delete(test_path, headers=headers)
                    
                    tested_count += 1
                    
                    if res and res.status_code >= 500:
                        errors_500.append(f"{method} {path} returned {res.status_code}: {res.text}")
                except Exception as e:
                    errors_500.append(f"{method} {path} CRASHED: {str(e)}")

print(f"\nTested {tested_count} endpoints.")
if errors_500:
    print(f"CRITICAL: Found {len(errors_500)} endpoints with 500 Errors!")
    for err in errors_500[:10]:
        print(f"  -> {err}")
else:
    print(f"SUCCESS: ZERO 500 Internal Server Errors found across all endpoints!")

