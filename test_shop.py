import os
import traceback
import warnings

warnings.filterwarnings("ignore")
os.environ['DATABASE_URL'] = 'sqlite:///./test.db'

from fastapi.testclient import TestClient
from app import api
from db import Base, engine
import random

client = TestClient(api)
username = f'testuser{random.randint(10000,99999)}'
client.post('/auth/register', json={'username': username, 'password': 'Password123!', 'email': f'{username}@test.com'})
token = client.post('/auth/login', json={'username': username, 'password': 'Password123!'}).json().get('access_token', '')

try:
    res = client.get('/shop/profile', headers={"Authorization": f"Bearer {token}"})
    print("STATUS", res.status_code)
    print("BODY", res.text)
except Exception as e:
    traceback.print_exc()

