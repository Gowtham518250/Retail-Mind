# 🏪 AI SHOP PRO - Enterprise Retail Management System

> **Production-Ready Backend for 100+ Crore Startups**
>
> Complete retail ERP system built with FastAPI, PostgreSQL, and Redis

---

## 📊 System Overview

### Core Modules (100% Functional)

| Module | Features | Endpoints |
|--------|----------|-----------|
| **🔐 Authentication** | JWT, RBAC (Owner/Customer/Worker), 2FA OTP | 8 |
| **🛍️ Inventory** | Stock tracking, batches, movements, alerts | 12 |
| **💰 Invoices & Billing** | Auto-sync, QR codes, PDF export, multiple counters | 10 |
| **📞 Customer Management** | Contacts, credit scoring, khata ledger | 9 |
| **👥 Attendance** | Check-in/out, leave requests, working hours | 14 |
| **📦 Purchase Orders** | Vendor management, order tracking, delivery | 6 |
| **💳 Khata Ledger** | Customer credit tracking, repayment history | 5 |
| **🏬 Online Store** | Order management, customer portal | 7 |
| **💼 Retail Intelligence** | P&L, expense tracking, bank reconciliation | 20+ |
| **🎁 Gift Cards & GST** | Card management, GST compliance, exports | 6 |
| **⚙️ Advanced Features** | Caching, batch ops, rate limiting | 15 |

**Total: 100+ Production-Ready Endpoints**

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Mobile/Web App │ (Flutter, React, etc.)
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────────────────────┐
│   FastAPI Backend (app.py)      │
│  ✓ JWT Authentication           │
│  ✓ RBAC Access Control          │
│  ✓ Rate Limiting                │
│  ✓ CORS Protection              │
│  ✓ Error Handling               │
└────────┬────────────────────────┘
         │
    ┌────┴──────┬──────────┬──────────┐
    ▼           ▼          ▼          ▼
┌────────┐  ┌────────┐ ┌────────┐ ┌────────┐
│  PostgreSQL │  │  Redis  │ │  S3    │ │ Email  │
│  (Primary)  │  │ (Cache) │ │(Files) │ │Service │
└────────┘  └────────┘ └────────┘ └────────┘
```

---

## ⚡ Quick Start (Local Development)

### Prerequisites
- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- Git

### 1️⃣ Clone & Setup

```bash
git clone https://github.com/your-org/ai-shop-pro.git
cd ai-shop-pro
```

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Linux/Mac:
source venv/bin/activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Configure Environment

```bash
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Minimal `.env` for local dev:**

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_shop_pro
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-min-32-chars
DEBUG=True
```

### 5️⃣ Initialize Database

```bash
# Option A: Auto-create tables
python -c "from db import engine; from models import Base; Base.metadata.create_all(bind=engine); print('✅ Tables created')"

# Option B: Using migration script
psql $DATABASE_URL < migration_production_v1.sql
```

### 6️⃣ Run Backend

```bash
uvicorn app:api --reload --host 0.0.0.0 --port 8000
```

Visit: **http://localhost:8000/docs** (Swagger UI)

### 7️⃣ Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# List all endpoints
curl http://localhost:8000/docs

# Run comprehensive tests
python test_all_endpoints.py
```

---

## 🚀 Production Deployment

### On Render (Recommended)

1. **Connect GitHub Repository**
   ```
   Dashboard → New → Web Service → Connect Repository
   ```

2. **Set Environment**
   ```
   Environment → Add Variables (from .env)
   ```

3. **Build & Start Commands**
   ```
   Build: pip install -r requirements.txt
   Start: uvicorn app:api --host 0.0.0.0 --port $PORT
   ```

4. **Deploy Database**
   ```bash
   # In Render Console
   psql $DATABASE_URL < migration_production_v1.sql
   ```

5. **Push to Deploy**
   ```bash
   git push origin main
   # Auto-deploys!
   ```

### On Railway

```bash
# Install CLI
npm i -g @railway/cli

# Deploy
railway up

# View logs
railway logs
```

---

## 📋 API Documentation

### Authentication

**Register New Shop**
```bash
POST /auth/register
Content-Type: application/json

{
  "user_name": "John Doe",
  "email": "john@shop.com",
  "password": "SecurePass123!"
}
```

**Login**
```bash
POST /auth/login
{
  "email": "john@shop.com",
  "password": "SecurePass123!"
}

Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Create Shop Profile

```bash
POST /shop/profile
Authorization: Bearer <token>
{
  "shop_name": "My Retail Store",
  "shop_type": "General",
  "phone": "9876543210",
  "email": "shop@example.com",
  "address": "123 Main St",
  "city": "Delhi",
  "gst_number": "18AABCN5055A1A0",
  "upi_id": "myshop@paytm"
}
```

### Create Product

```bash
POST /api/inventory/products
Authorization: Bearer <token>
{
  "product_name": "Laptop",
  "sku": "SKU-001",
  "unit_price": 50000,
  "current_stock": 10,
  "category": "Electronics",
  "min_stock": 2,
  "max_stock": 50
}
```

**See `/docs` for all 100+ endpoints**

---

## 🔧 Configuration Files

### `.env` - Environment Variables
- Database connection
- Redis URL
- JWT secrets
- Email SMTP
- Frontend URLs

### `requirements.txt` - Python Dependencies
- FastAPI, SQLAlchemy, PostgreSQL
- Redis, Pydantic, JWT
- QR code, Excel export
- APScheduler for tasks

### `docker-compose.yml` - Local Development
```bash
docker-compose up -d  # Start PostgreSQL + Redis
docker-compose down   # Stop services
```

### `migration_production_v1.sql` - Database Schema
- All 43 tables
- Indexes for performance
- Foreign key constraints
- Audit logging

---

## 📊 Database Schema

### Core Tables (43 Total)

```
user_details          → shop_profiles
                      → products
                      → customers
                      → invoices
                      → attendance
                      → purchase_orders
                      → ... (30+ more)
```

**Key Relationships:**
- Shop → Products → Stock Movements
- Customer → Invoices → Payments
- Employee → Attendance → Leave Requests

---

## 🔐 Security Features

- ✅ **JWT Authentication** - RBAC (Owner/Customer/Worker)
- ✅ **Password Hashing** - bcrypt with salt
- ✅ **SQL Injection Protection** - SQLAlchemy ORM
- ✅ **XSS Prevention** - Input validation
- ✅ **CORS** - Restricted to known origins
- ✅ **Rate Limiting** - Redis-based, distributed
- ✅ **HTTPS** - TLS encryption in transit
- ✅ **Audit Logging** - Track all changes
- ✅ **Data Isolation** - Per-shop data separation

---

## 📈 Performance Optimization

### Caching Strategy
- **Redis Cache** - Query results, 1-hour TTL
- **Browser Cache** - Static assets, 30-day TTL
- **Database Indexes** - On frequently searched columns

### Query Optimization
- Lazy loading for relationships
- Batch operations for bulk inserts
- Connection pooling (20 connections)

### Monitoring
```bash
# Check slow queries
SELECT query, calls, total_time FROM pg_stat_statements 
ORDER BY total_time DESC LIMIT 10;

# Check cache hit rate
redis-cli INFO stats
```

---

## 🧪 Testing

### Run All Tests

```bash
# Comprehensive test suite
python test_all_endpoints.py

# Specific module
python -m pytest test_shop.py -v

# Coverage report
pytest --cov=. --cov-report=html
```

### Pre-Deployment Validation

```bash
# Run validation script
python validate_production.py

# Output:
# ✅ Python Version: 3.11
# ✅ Dependencies: All installed
# ✅ Database: Connected
# ✅ Redis: Connected
# ✅ All checks passed!
```

---

## 📚 Project Structure

```
.
├── app.py                          # Main FastAPI application
├── models.py                       # 43 SQLAlchemy models
├── db.py                          # Database configuration
├── auth_routes.py                 # Authentication & JWT
├── inventory.py                   # Product management
├── invoices_billing.py            # Invoice system
├── customers.py                   # Customer management
├── shop_management.py             # Shop settings
├── khata_ledger.py               # Credit tracking
├── purchase_orders.py             # Purchase orders
├── online_store.py                # E-commerce
├── retail_intelligence.py         # Analytics & reports
├── attendance.py                  # HR management
├── caching_system.py              # Redis caching
├── batch_operations.py            # Bulk operations
├── rate_limiting.py               # API protection
├── requirements.txt               # Dependencies
├── migration_production_v1.sql     # Database schema
├── init-db.sql                   # Initial setup
├── DEPLOYMENT_GUIDE.md            # Production guide
├── validate_production.py          # Validation script
└── test_*.py                      # Test suites
```

---

## 🐛 Troubleshooting

### Database Issues

**Error: `column "gst_number" does not exist`**
```sql
ALTER TABLE shop_profiles ADD COLUMN gst_number VARCHAR(50);
```

**Error: Port 5432 already in use**
```bash
# Find and kill process
lsof -i :5432
kill -9 <PID>
```

### Redis Issues

**Error: Connection refused**
```bash
# Restart Redis
redis-cli ping
# Should return: PONG
```

### App Startup Issues

**Error: `ModuleNotFoundError`**
```bash
pip install --upgrade -r requirements.txt
```

---

## 📞 Support & Documentation

| Resource | Link |
|----------|------|
| API Docs (Swagger) | `/docs` |
| Database Schema | `DEPLOYMENT_GUIDE.md` |
| Quick Start | This README |
| Troubleshooting | `DEPLOYMENT_GUIDE.md#troubleshooting` |
| GitHub Issues | github.com/.../issues |

---

## 🎯 Roadmap

- [ ] v3.1 - Mobile app offline sync
- [ ] v3.2 - Advanced reporting (AI-powered)
- [ ] v3.3 - Multi-language support
- [ ] v3.4 - Blockchain invoicing
- [ ] v3.5 - WhatsApp integration

---

## 📄 License

Proprietary - All Rights Reserved

---

## 👥 Team

- **Backend Architect**: Your Name
- **Database Design**: Your Name
- **DevOps**: Your Name

---

## ✨ Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.0.0 | 2026-06-18 | ✅ Production ready, all 100+ endpoints |
| 2.5.0 | 2026-06-10 | Added advanced features |
| 2.0.0 | 2026-05-01 | MVP release |

---

**Last Updated:** 2026-06-18
**Status:** ✅ Production Ready
**Environment:** All (Local, Staging, Production)
