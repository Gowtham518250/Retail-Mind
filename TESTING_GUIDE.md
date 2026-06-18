# 🧪 AI SHOP PRO - ENDPOINT TESTING GUIDE

## 🔐 Security First!

**NEVER share your production credentials in code or messages!**

✅ Use `.env.production` file (local only, don't commit)  
✅ Set environment variables on production server  
✅ Use different credentials for each environment  

---

## 📋 Quick Start

### Step 1: Create `.env.production` (One Time)

Already created! Check the file: [.env.production](.env.production)

**Contains:**
```
DATABASE_URL=your-database-url
REDIS_URL=redis://localhost:6379
SECRET_KEY=prod-secure-key-1a2b3c4d5e6f7g8h9i
SENDER_EMAIL=your-email@gmail.com
PORT=10000
```

### Step 2: Ensure Backend is Running

**Option A: Local Development**
```bash
# Terminal 1: Start backend
uvicorn app:api --reload --host 0.0.0.0 --port 8000
```

**Option B: Production (Render/Railway)**
```bash
# Skip - your API is already running at:
# https://your-api.railway.app or https://your-api.render.com
```

### Step 3: Run Tests

#### On Windows:
```bash
# Double-click or run:
run_tests.bat

# Or manual:
python test_all_endpoints_comprehensive.py
```

#### On Linux/Mac:
```bash
# Make script executable (one time)
chmod +x run_tests.sh

# Run tests
./run_tests.sh

# Or manual:
python3 test_all_endpoints_comprehensive.py
```

---

## 📊 What Gets Tested

### Test Categories

1. **Health & System** (4 tests)
   - Root endpoint `/`
   - Health check `/health`
   - API docs `/docs`
   - ReDoc `/redoc`

2. **Authentication** (3 tests)
   - Register new user
   - Login with credentials
   - Refresh token

3. **Shop Management** (5 tests)
   - Create shop profile
   - Get shop profile
   - Update shop profile
   - List shops

4. **Inventory** (6 tests)
   - Create product
   - Get products list
   - Get product by ID
   - Update product
   - Get stock levels

5. **Customer Management** (4 tests)
   - Create customer
   - Get customers list
   - Get customer by ID
   - Search customers

6. **Invoicing** (3 tests)
   - Create invoice
   - Get invoices list
   - Get invoice by ID

7. **Khata Ledger** (3 tests)
   - Get balance
   - Add credit
   - Get history

8. **Attendance** (2 tests)
   - Check in
   - Get today's attendance

9. **Advanced Features** (3 tests)
   - Cache statistics
   - Batch operations status
   - Rate limiting info

10. **Error Handling** (3 tests)
    - 404 errors
    - 401 unauthorized
    - 422 invalid data

**Total: 36+ Critical Tests**

---

## 🚀 Running Tests

### Full Test Suite
```bash
python test_all_endpoints_comprehensive.py
```

**Expected Output:**
```
═══════════════════════════════════════════════════════════════
  🧪 AI SHOP PRO - ENDPOINT TESTING SUITE
  Comprehensive API Validation
═══════════════════════════════════════════════════════════════

ℹ️  API Base URL: http://localhost:8000
ℹ️  Test Start Time: 2026-06-18 10:30:45

1️⃣  HEALTH & SYSTEM ENDPOINTS

✅ Root Endpoint | GET / | 200 | 45.23ms
✅ Health Check | GET /health | 200 | 12.15ms
✅ API Docs | GET /docs | 200 | 8.92ms
✅ ReDoc | GET /redoc | 200 | 6.54ms

... more tests ...

📊 TEST SUMMARY REPORT
Total Tests: 36
Passed: 36
Failed: 0
Success Rate: 100.0%

✅ Report saved to: test_report_20260618_103045.json
✅ ALL TESTS PASSED!
```

---

## 📈 Test Report

Each test run generates a JSON report: `test_report_YYYYMMDD_HHMMSS.json`

**Contains:**
```json
{
  "timestamp": "20260618_103045",
  "api_url": "http://localhost:8000",
  "summary": {
    "total": 36,
    "passed": 36,
    "failed": 0,
    "success_rate": "100.0%"
  },
  "errors": [],
  "details": [
    {
      "method": "GET",
      "endpoint": "/",
      "name": "Root Endpoint",
      "status": 200,
      "expected": 200,
      "elapsed_ms": 45.23,
      "success": true
    }
    ... more endpoints ...
  ]
}
```

---

## 🔍 Analyzing Results

### If All Tests Pass ✅
```
Success Rate: 100.0%
✅ ALL TESTS PASSED!
```
→ Your API is fully functional!

### If Some Tests Fail ❌
```
Failed: 3
Success Rate: 91.7%
⚠️  Some tests failed - check test_report_*.json
```

**Check the report:**
1. Open `test_report_*.json` 
2. Find entries with `"success": false`
3. Review the endpoint and error
4. Fix the issue
5. Re-run tests

**Common Issues:**

| Issue | Fix |
|-------|-----|
| Connection refused | Start backend first |
| 401 Unauthorized | Auth token not acquired |
| 404 Not Found | Endpoint doesn't exist |
| 422 Invalid Data | Request data malformed |
| Timeout | API too slow or network issue |

---

## 🎯 Testing Against Production Database

### Using Your Render Database

Your `.env.production` already has:
```
DATABASE_URL=postgresql://retail_mind_xxog_user:...@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog
```

**To test against production:**

1. **Update API_URL in test script** (if not using localhost):
   ```bash
   # Edit test_all_endpoints_comprehensive.py
   API_BASE_URL = "https://your-api.railway.app"  # or render URL
   ```

2. **Or set via environment:**
   ```bash
   export API_URL=https://your-api.railway.app
   python test_all_endpoints_comprehensive.py
   ```

3. **Run tests:**
   ```bash
   python test_all_endpoints_comprehensive.py
   ```

---

## 📊 Performance Monitoring

The test script records timing for each endpoint:

**Response Time Metrics:**
```
Endpoint                    Time (ms)
────────────────────────────────────
GET /                       45.23 ms  ✅ Good
GET /health                 12.15 ms  ✅ Excellent
POST /auth/login            87.45 ms  ✅ Good
POST /api/invoices/create   245.32 ms ⚠️ Slow (>200ms)
```

**Target Response Times:**
- GET endpoints: <100ms
- POST endpoints: <200ms
- Complex queries: <500ms

If slow, check:
1. Database query performance
2. Redis cache hit rate
3. Server CPU/memory
4. Network latency

---

## 🔄 Running Tests Regularly

### Recommended Schedule

| Frequency | Purpose |
|-----------|---------|
| Before deployment | Verify all endpoints work |
| Daily | Regression testing |
| Weekly | Performance benchmarking |
| After each change | Validation |

### Automated Testing (Optional)

**Add to cron (Linux/Mac):**
```bash
# Run tests daily at 2 AM
0 2 * * * /path/to/run_tests.sh >> /var/log/api_tests.log
```

**Add to GitHub Actions (optional):**
```yaml
name: API Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pip install -r requirements.txt
      - run: python test_all_endpoints_comprehensive.py
```

---

## 🛠️ Troubleshooting

### Test Script Won't Run

**Error: `ModuleNotFoundError: No module named 'requests'`**
```bash
pip install requests python-dotenv
```

**Error: `.env.production` not found**
```bash
# Create it with your database URL
echo "DATABASE_URL=your-url" > .env.production
```

### API Connection Issues

**Error: `ConnectionError: Connection refused`**
```bash
# Make sure API is running
uvicorn app:api --host 0.0.0.0 --port 8000
```

**Error: `Timeout: Request timeout`**
```bash
# API is too slow - check:
# 1. Server CPU/memory
# 2. Database queries
# 3. Network latency
```

### Authentication Failures

**Error: `401 Unauthorized`**
```
# Auth token not acquired during registration/login
# Check:
# 1. Secret key correct in .env
# 2. Password requirements met (must contain uppercase, number, special char)
```

---

## 📝 Example Test Output

```
════════════════════════════════════════════════════════════════
  🧪 AI SHOP PRO - ENDPOINT TESTING SUITE
  Comprehensive API Validation
════════════════════════════════════════════════════════════════

ℹ️  API Base URL: http://localhost:8000
ℹ️  Test Start Time: 2026-06-18 10:30:45

1️⃣  HEALTH & SYSTEM ENDPOINTS

✅ Root Endpoint | GET / | 200 | 45.23ms
✅ Health Check | GET /health | 200 | 12.15ms
✅ API Docs | GET /docs | 200 | 8.92ms
✅ ReDoc | GET /redoc | 200 | 6.54ms

2️⃣  AUTHENTICATION ENDPOINTS

✅ Register User | POST /auth/register | 200 | 234.56ms
✅ Login User | POST /auth/login | 200 | 156.78ms
Auth token acquired: eyJhbGciOiJIUzI1NiIsInR5cCI...
✅ Refresh Token | POST /refresh-token | 200 | 87.34ms

3️⃣  SHOP MANAGEMENT ENDPOINTS

✅ Create Shop Profile | POST /shop/profile | 201 | 167.89ms
✅ Get Shop Profile | GET /shop/profile/1 | 200 | 45.23ms
✅ Update Shop Profile | PUT /shop/profile/1 | 200 | 98.76ms
✅ List Shops | GET /shop/list | 200 | 67.45ms

... more test results ...

📊 TEST SUMMARY REPORT

Total Tests: 36
Passed: 36
Failed: 0
Success Rate: 100.0%

✅ Report saved to: test_report_20260618_103045.json
✅ ALL TESTS PASSED!

Test End Time: 2026-06-18 10:35:12
```

---

## 💡 Tips & Best Practices

1. **Run tests before committing code**
   ```bash
   python test_all_endpoints_comprehensive.py && git commit
   ```

2. **Keep test reports for comparison**
   ```bash
   mkdir test_reports
   cp test_report_*.json test_reports/
   ```

3. **Test with clean data**
   ```bash
   # Reset test database before critical tests
   psql $DATABASE_URL < init-db.sql
   ```

4. **Monitor test trends**
   - Track success rate over time
   - Monitor response time changes
   - Identify slow endpoints

5. **Use test data that matches production**
   - Create realistic test scenarios
   - Use similar data volumes
   - Test edge cases

---

## 📞 Need Help?

If tests are failing:

1. Check test report: `test_report_*.json`
2. Review API logs: `railway logs` or `render logs`
3. Test individual endpoint manually
4. Check database connection
5. Verify environment variables

---

**Last Updated:** 2026-06-18  
**Status:** ✅ Ready to Test  
**Next:** Run `python test_all_endpoints_comprehensive.py`
