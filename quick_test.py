#!/usr/bin/env python3
"""
⚡ AI SHOP PRO - QUICK TEST RUNNER
One-liner to test all endpoints
"""

import subprocess
import sys
import os

# Load environment
import os
from dotenv import load_dotenv
if os.path.exists('.env.local'):
    load_dotenv('.env.local')
    test_mode = "LOCAL SQLite"
else:
    load_dotenv('.env.production')
    test_mode = "PRODUCTION Render"

print(f"""
╔════════════════════════════════════════════════════════════════╗
║          🧪 AI SHOP PRO ENDPOINT TEST LAUNCHER                ║
║    Complete Endpoint Validation Suite v1.0 ({test_mode})      ║
╚════════════════════════════════════════════════════════════════╝

📋 TESTS INCLUDED (36+):
  ✅ Health & System Checks
  ✅ Authentication (Register, Login, Token Refresh)
  ✅ Shop Management (Create, Read, Update, List)
  ✅ Inventory (Products, Stock, Batches)
  ✅ Customer Management (CRUD, Search)
  ✅ Invoicing (Create, List, Get)
  ✅ Khata Ledger (Balance, Credit, History)
  ✅ Attendance (Check-in, History)
  ✅ Advanced Features (Cache, Batch, Rate Limiting)
  ✅ Error Handling (404, 401, 422)

⏱️  ESTIMATED RUNTIME: 30-60 seconds

🚀 STARTING TESTS...\n
""")

# Check if backend is running
print("1️⃣  Checking backend connectivity...")
try:
    import requests
    response = requests.get("http://localhost:8000/health", timeout=5)
    if response.status_code == 200:
        print("✅ Backend running at http://localhost:8000\n")
    else:
        print("⚠️  Backend responded with status: " + str(response.status_code))
except requests.exceptions.ConnectionError:
    print("⚠️  WARNING: Backend not running at http://localhost:8000")
    print("   Start it with: uvicorn app:api --reload --port 8000")
    print("   Or set API_URL environment variable for production URL\n")
except Exception as e:
    print(f"⚠️  Could not verify backend: {str(e)}\n")

# Check dependencies
print("2️⃣  Checking dependencies...")
try:
    import requests
    import dotenv
    print("✅ All dependencies available\n")
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# Run tests
print("3️⃣  Running endpoint tests...\n")
print("="*70 + "\n")

result = subprocess.run([sys.executable, "test_all_endpoints_comprehensive.py"])

print("\n" + "="*70)
print("\n📊 TEST EXECUTION COMPLETE!\n")

if result.returncode == 0:
    print("""
    ✅ ALL TESTS PASSED!
    
    📈 Your API is production-ready!
    
    📊 Check test_report_*.json for detailed results
    📱 Ready to connect mobile app
    🚀 Ready for production deployment
    """)
else:
    print("""
    ⚠️  Some tests failed
    
    📋 Review test_report_*.json for details
    🔍 Common issues:
       - Backend not running
       - Database not accessible
       - Auth token not acquired
       - Missing endpoints
    
    💡 Run: python test_all_endpoints_comprehensive.py
    """)

sys.exit(result.returncode)
