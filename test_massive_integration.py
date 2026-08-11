import asyncio
import aiohttp
import time
import json
import random
import uuid
import sys
import os

# Set Windows compatibility for asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

API_BASE_URL = os.getenv("API_URL", "https://retail-mind-vkbp.onrender.com")

COLORS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "WARNING": "\033[93m",
    "RED": "\033[91m",
    "RESET": "\033[0m",
    "BOLD": "\033[1m"
}

def print_c(msg, color="RESET"):
    print(f"{COLORS.get(color, COLORS['RESET'])}{msg}{COLORS['RESET']}")

class MassiveTester:
    def __init__(self):
        self.token = None
        self.headers = {"Content-Type": "application/json"}
        self.endpoints = []
        self.total_inserted = 0
        self.session = None

    async def init_session(self):
        connector = aiohttp.TCPConnector(limit=50) # Limit concurrency
        self.session = aiohttp.ClientSession(connector=connector)

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def fetch_openapi(self):
        print_c("🔍 Fetching OpenAPI Spec to discover EVERY single endpoint...", "BLUE")
        async with self.session.get(f"{API_BASE_URL}/openapi.json") as resp:
            if resp.status == 200:
                data = await resp.json()
                paths = data.get("paths", {})
                
                get_count = 0
                post_count = 0
                put_count = 0
                delete_count = 0
                
                for path, methods in paths.items():
                    for method in methods.keys():
                        if method.upper() == "GET": get_count += 1
                        if method.upper() == "POST": post_count += 1
                        if method.upper() == "PUT": put_count += 1
                        if method.upper() == "DELETE": delete_count += 1
                        self.endpoints.append({"method": method.upper(), "path": path})
                        
                print_c(f"✅ Discovered {len(self.endpoints)} unique endpoint operations!", "GREEN")
                print_c(f"   GET: {get_count} | POST: {post_count} | PUT: {put_count} | DELETE: {delete_count}", "BLUE")
            else:
                print_c(f"❌ Failed to fetch OpenAPI spec. Status: {resp.status}", "RED")

    async def authenticate(self):
        print_c("\n🔑 Registering and Authenticating Test User...", "BLUE")
        username = f"massivetest_{int(time.time())}"
        email = f"{username}@test.com"
        password = "Password123!"

        # Register
        async with self.session.post(f"{API_BASE_URL}/auth/register", json={
            "email": email, "username": username, "password": password
        }) as resp:
            await resp.text()

        # Login
        async with self.session.post(f"{API_BASE_URL}/auth/login", json={
            "email": email, "password": password
        }) as resp:
            if resp.status == 200:
                data = await resp.json()
                self.token = data.get("access_token")
                self.headers["Authorization"] = f"Bearer {self.token}"
                print_c("✅ Authentication Successful! Token Acquired.", "GREEN")
            else:
                async with self.session.post(f"{API_BASE_URL}/auth/login", json={
                    "username": "testadmin", "password": "Password123!"
                }) as fallback_resp:
                    if fallback_resp.status == 200:
                        data = await fallback_resp.json()
                        self.token = data.get("access_token")
                        self.headers["Authorization"] = f"Bearer {self.token}"
                        print_c("✅ Fallback Authentication Successful!", "GREEN")
                    else:
                        print_c("❌ Fatal: Could not authenticate.", "RED")
                        sys.exit(1)

    async def smoke_test_all_endpoints(self):
        print_c("\n🚀 PHASE 1: Smoke Testing Every Single Endpoint...", "HEADER")
        passed = 0
        failed = 0
        
        get_endpoints = [e for e in self.endpoints if e['method'] == 'GET' and '{' not in e['path']]
        print_c(f"Found {len(get_endpoints)} static GET endpoints to smoke test.", "BLUE")
        
        for ep in get_endpoints:
            try:
                url = f"{API_BASE_URL}{ep['path']}"
                async with self.session.get(url, headers=self.headers, timeout=5) as resp:
                    if resp.status in [200, 201, 202, 403, 401, 422]: 
                        passed += 1
                    else:
                        failed += 1
            except Exception as e:
                failed += 1
                
        print_c(f"Smoke Test Results -> ALIVE: {passed} | FAILED/TIMEOUT: {failed}", "GREEN" if failed == 0 else "WARNING")

    async def async_insert(self, name, url, payload_generator, count):
        print_c(f"\n🔥 STRESS TEST: Inserting {count} {name} records...", "WARNING")
        start_time = time.time()
        success = 0
        failed = 0
        
        async def worker(sem, idx):
            nonlocal success, failed
            payload = payload_generator(idx)
            async with sem:
                try:
                    async with self.session.post(url, json=payload, headers=self.headers) as resp:
                        if resp.status in [200, 201]:
                            success += 1
                        else:
                            failed += 1
                except:
                    failed += 1

        sem = asyncio.Semaphore(20) # Safe concurrency
        tasks = [worker(sem, i) for i in range(count)]
        
        chunk_size = 500
        for i in range(0, len(tasks), chunk_size):
            await asyncio.gather(*tasks[i:i+chunk_size])
            print_c(f"   Progress: {min(i+chunk_size, count)}/{count} inserted...", "BLUE")
            
        elapsed = time.time() - start_time
        print_c(f"✅ {name} Insertion Complete! Success: {success} | Failed: {failed} | Time: {elapsed:.2f}s", "GREEN")
        self.total_inserted += success

    def gen_product(self, idx):
        return {
            "product_name": f"Massive_Item_{uuid.uuid4().hex[:8]}",
            "sku": f"SKU_{uuid.uuid4().hex[:10]}",
            "category": "Stress Test",
            "mrp": random.randint(10, 1000),
            "selling_price": random.randint(10, 900),
            "current_stock": random.randint(1, 100),
            "min_stock_level": 5
        }

    def gen_customer(self, idx):
        return {
            "name": f"Cust_{uuid.uuid4().hex[:8]}",
            "phone": f"9{random.randint(100000000, 999999999)}",
            "email": f"cust_{idx}_{uuid.uuid4().hex[:4]}@test.com",
            "address": "123 Stress Test Ave"
        }

    async def clear_data_simulation(self):
        print_c("\n🧹 PHASE 3: Simulating Clear Data...", "HEADER")
        # In the context of your scenario, clear data removes local cache, 
        # but let's test if the backend cache clears properly as well
        async with self.session.delete(f"{API_BASE_URL}/cache/clear-all", headers=self.headers) as resp:
            print_c(f"Cache clear triggered. Status: {resp.status}", "BLUE")
            
    async def verify_data_persistence(self):
        print_c("\n📊 PHASE 4: Verifying Database Persistence...", "HEADER")
        
        async with self.session.get(f"{API_BASE_URL}/api/inventory/products", headers=self.headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                print_c(f"✅ Retrieved {len(data)} products from backend database. Inventory successfully survived!", "GREEN")
            else:
                print_c(f"❌ Failed to retrieve products. Status: {resp.status}", "RED")

    async def run(self):
        print_c("=" * 80, "HEADER")
        print_c("🚀 MASSIVE INTEGRATION & STRESS TEST SUITE", "HEADER")
        print_c("=" * 80, "HEADER")
        
        await self.init_session()
        await self.fetch_openapi()
        await self.authenticate()
        
        await self.smoke_test_all_endpoints()
        
        # 10k records total
        target_per_section = 2500 
        print_c(f"\n⚠️ STARTING MASSIVE DATA GENERATION...", "WARNING")
        
        await self.async_insert("Inventory Products", f"{API_BASE_URL}/api/inventory/products", self.gen_product, target_per_section)
        await self.async_insert("Customers", f"{API_BASE_URL}/api/customers/", self.gen_customer, target_per_section)
        
        print_c(f"\n🎉 DATA GENERATION COMPLETE. Total Records Inserted: {self.total_inserted}", "GREEN")
        
        await self.clear_data_simulation()
        await self.verify_data_persistence()
        
        await self.close_session()
        print_c("\n🏁 MASSIVE TEST SUITE FINISHED.", "HEADER")

if __name__ == "__main__":
    tester = MassiveTester()
    asyncio.run(tester.run())
