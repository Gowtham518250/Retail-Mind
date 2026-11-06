from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
import os
import time
import logging
import threading
from datetime import datetime, timezone
from urllib.parse import urlencode
from performance_middleware import setup_performance_middleware

# ========================
# LOGGING SETUP
# ========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("ai_shop_pro")


def build_shop_frontend_redirect_url(request: Request, shop_id: str) -> str:
    """Build a safe shop deep link, using the current host unless a UI URL is set."""
    shop_key = str(shop_id or "").strip()
    if not shop_key or len(shop_key) > 64:
        raise ValueError("A valid shop identifier is required.")

    configured_frontend = (
        os.getenv("NEXTJS_FRONTEND_URL")
        or os.getenv("FRONTEND_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or ""
    ).strip()
    query = urlencode({"shop_id": shop_key})
    if not configured_frontend:
        # A relative URL deliberately keeps the current request host, which
        # is important when the same app is served behind different domains.
        return f"/?{query}"

    base = configured_frontend.rstrip("/")
    if "://" not in base:
        scheme = getattr(getattr(request, "url", None), "scheme", "https") or "https"
        base = f"{scheme}://{base}"
    return f"{base}/?{query}"

# ========================
# FIREBASE ADMIN SETUP
# ========================
import firebase_admin
from firebase_admin import credentials
firebase_initialized = False
try:
    if not firebase_admin._apps:
        # 1. Try reading from Environment Variable (Render / Prod)
        firebase_env_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if firebase_env_json:
            import json
            cred_dict = json.loads(firebase_env_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            firebase_initialized = True
            logger.info("Firebase Admin SDK initialized successfully from ENV VAR.")
        # 2. Fallback to local file (Local Testing or Render Secret File)
        elif os.path.exists("firebase-adminsdk.json"):
            cred = credentials.Certificate("firebase-adminsdk.json")
            firebase_admin.initialize_app(cred)
            firebase_initialized = True
            logger.info("Firebase Admin SDK initialized successfully from file.")
        else:
            logger.warning("No Firebase credentials found! Phone authentication and push notifications will not work.")
    else:
        firebase_initialized = True
        logger.info("Firebase Admin SDK already initialized.")
except Exception as e:
    logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
    firebase_initialized = False

# ========================
# IMPORT ALL ROUTERS
# ========================
# Core Auth & Session
from auth_routes import router as authentication_router
from subscription_billing import router as subscription_billing_router
from subscription_entitlements import router as subscription_entitlements_router
from subscription_quota_middleware import SubscriptionAIQuotaMiddleware
from auth_hardening_service import router as auth_hardening_router
from session_routes import router as session_router
from logs_routes import router as logs_router

# Core ERP
from inventory import router as inventory_router
from inventory_sync_service import router as inventory_sync_router
from inventory_reconciliation_service import router as inventory_reconcile_router
from sales_restore_service import router as sales_restore_router
from attendance import router as attendance_router
from invoices_billing import router as invoices_router
from customers import router as customers_router
from shop_management import router as shop_management_router
from bill_generated import router as bill_router

# New Enterprise Modules
from shop_settings import router as shop_settings_router
from khata_ledger import router as khata_router
from khata_router import router as new_khata_engine_router
from purchase_orders import router as purchase_orders_router
from online_store import router as online_store_router
from cashfree_online_payments import router as cashfree_online_payments_router
from customer_ai_shopping import router as customer_ai_router
from growth_suite import router as growth_router, customer_router as customer_growth_router
from whatsapp_orders import router as whatsapp_orders_router
from retail_intelligence import router as intelligence_router
from gst_and_giftcards import router as gst_and_giftcards_router

# Legacy extended features (non-chatbot)
from new_feature_routers import router as new_features_router
from debug_routes import router as debug_router
from query_retrival import app as query_router

# Advanced system features
from caching_system import router as caching_router
from batch_operations import router as batch_operations_router
from security_hardening import router as security_hardening_router
from observability_service import router as observability_router
from operations_routes import router as operations_router
from realtime import router as realtime_router
from durable_sync import router as durable_sync_router
from health_routes import router as health_router

# DB initialization
from db import engine, get_db
from models import Base
from sqlalchemy.orm import Session
from models import ShopProfile, Product

# ========================
# APP CREATION
# ========================
api = FastAPI(
    title="AI Shop Pro Enterprise Backend",
    description=(
        "🏪 Complete retail ERP backend for AI Shop Pro.\n\n"
        "Modules: Auth (RBAC), Inventory, Invoices, Khata Ledger, "
        "Purchase Orders, Bank Reconciliation, Online Store, "
        "Worker Management, Expense Tracker, Enterprise P&L, Retail Intelligence."
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enforce paid entitlements on owner-only management APIs. Customer storefront and
# customer checkout routes intentionally remain outside this owner feature gate.
@api.middleware("http")
async def subscription_feature_enforcement(request: Request, call_next):
    path = request.url.path
    protected_prefixes = (
        "/store/owner/orders",
        "/store/owner/reviews",
    )
    if not path.startswith(protected_prefixes):
        return await call_next(request)

    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required."},
        )

    db_generator = get_db()
    db = next(db_generator)
    try:
        from security import decode_token
        from subscription_entitlements import require_shop_feature

        payload = decode_token(authorization.split(" ", 1)[1].strip())
        if (
            payload.get("type") == "refresh"
            or str(payload.get("role", "")).upper() != "OWNER"
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Owner access required."},
            )

        try:
            owner_user_id = int(payload.get("sub"))
            if owner_user_id <= 0:
                raise ValueError("Invalid owner ID")
        except (TypeError, ValueError):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid access token."},
            )

        require_shop_feature(db, owner_user_id, "online_orders")
    except HTTPException as exc:
        if exc.status_code == 403:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            logger.warning(
                "SUBSCRIPTION_FEATURE_DENIED path=%s shop_id=%s feature=%s "
                "current_plan=%s code=%s",
                path,
                locals().get("owner_user_id", "unknown"),
                detail.get("feature", "online_orders"),
                detail.get("current_plan", "unknown"),
                detail.get("code", "OWNER_ACCESS_REQUIRED"),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    except Exception:
        logger.exception("Subscription entitlement enforcement failed")
        return JSONResponse(
            status_code=503,
            content={"detail": "Subscription access could not be verified."},
        )
    finally:
        try:
            db_generator.close()
        except Exception:
            logger.exception("Could not close subscription entitlement DB session")

    return await call_next(request)


# Server-authoritative quota enforcement for text and direct voice AI requests.
api.add_middleware(SubscriptionAIQuotaMiddleware)

# ========================
# ATTENDANCE AUTO-CHECKOUT LIFECYCLE
# Start reconciliation for every supported ASGI launch command (including
# `uvicorn app:api`), not only when production_boot.py is executed directly.
# ========================
@api.on_event("startup")
def _start_attendance_auto_checkout_on_startup():
    try:
        from production_boot import (
            _ensure_shift_table,
            _ensure_workers_table_schema,
            _start_attendance_auto_checkout,
        )
        if os.getenv("RETAIL_MIND_BOOTSTRAP_COMPLETE", "").strip() != "1":
            # Also repair worker schema when Render launches app:api directly
            # instead of the recommended production_boot.py entrypoint.
            _ensure_workers_table_schema()
            _ensure_shift_table()
        _start_attendance_auto_checkout()
        logger.info("Attendance auto-checkout scheduler initialized")
    except Exception:
        logger.exception("Attendance auto-checkout scheduler failed to initialize")

# ========================
# GROW MY SHOP AUTOMATION WORKER
# ========================
_growth_marketing_worker_started = False


@api.on_event("startup")
def _start_growth_marketing_automation_worker():
    """Run the idempotent campaign-draft queue on one Postgres replica at a time."""
    global _growth_marketing_worker_started
    if _growth_marketing_worker_started:
        return
    if os.getenv("GROWTH_MARKETING_AUTOMATION_WORKER_ENABLED", "1").strip().lower() in {"0", "false", "no", "off"}:
        logger.info("Grow My Shop automation worker disabled by configuration")
        return
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("TESTING", "").strip() == "1":
        return

    stop_event = threading.Event()

    def _worker_loop():
        while not stop_event.is_set():
            def _process_batch():
                from db import sessionLocal
                from growth_marketing_automation import process_pending_marketing_triggers

                session = sessionLocal()
                try:
                    outcome = process_pending_marketing_triggers(session, limit=50)
                    if outcome.get("processed") or outcome.get("weekly_triggers_queued"):
                        logger.info("Grow My Shop automation batch: %s", outcome)
                except Exception:
                    session.rollback()
                    logger.exception("Grow My Shop automation batch failed")
                finally:
                    session.close()

            try:
                from distributed_job_lock import run_with_advisory_lock
                run_with_advisory_lock(
                    _process_batch,
                    lock_id=7412061106,
                )
            except Exception:
                logger.exception("Could not run Grow My Shop automation batch")
            stop_event.wait(60)

    worker = threading.Thread(
        target=_worker_loop,
        name="growth-marketing-automation",
        daemon=True,
    )
    worker.start()
    _growth_marketing_worker_started = True
    logger.info("Grow My Shop automatic draft worker initialized")


# ========================
# LEGACY SCHEMA REPAIR (DEVELOPMENT / DIRECT ASGI ONLY)
# ========================
# Production uses production_boot.py, which runs versioned Alembic migrations
# first. Do not issue dozens of DDL statements on every API module import.
if os.getenv("RETAIL_MIND_BOOTSTRAP_COMPLETE", "").strip() != "1":
    # ========================
    # DB INIT ON STARTUP
    # ========================
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database connected successfully! All database tables initialized.")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization deferred: {e}")

    # ========================
    # SAFE COLUMN MIGRATIONS
    # Run ALTER TABLE for any columns added after initial DB creation.
    # Uses IF NOT EXISTS — safe to run on every startup, never crashes.
    # ========================
    try:
        from sqlalchemy import text
        from db import sessionLocal
        _db = sessionLocal()
        safe_migrations = [
            # user_details table — new columns added after initial deploy
            "ALTER TABLE user_details ADD COLUMN IF NOT EXISTS fcm_token VARCHAR(255)",
            "ALTER TABLE user_details ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            # invoices table — due_date made nullable
            "ALTER TABLE invoices ALTER COLUMN due_date DROP NOT NULL",
            # invoice offline_id index
            "CREATE INDEX IF NOT EXISTS ix_invoices_offline_id ON invoices(offline_id)",
            # products — purchase_price added later
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS purchase_price NUMERIC(10,2) DEFAULT 0",
            # Product imagery — repair legacy production databases even when the Render service does not run Alembic.
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT",
            # customers — state/postal_code added later
            "ALTER TABLE customers ADD COLUMN IF NOT EXISTS state VARCHAR(50)",
            "ALTER TABLE customers ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20)",
            # shop_profiles — ensure table schema matches current model
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS shop_tagline VARCHAR(500)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS shop_description TEXT",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS shop_type VARCHAR(100) DEFAULT 'General'",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS phone VARCHAR(20)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS email VARCHAR(100)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS website VARCHAR(200)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS gst_number VARCHAR(50)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS logo_url VARCHAR(500)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS logo_base64 TEXT",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS logo_content_type VARCHAR(100)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS latitude FLOAT",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS longitude FLOAT",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS address TEXT",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(200)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS address_line2 VARCHAR(200)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS location VARCHAR(300)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS city VARCHAR(100)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS state VARCHAR(100)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS postal_code VARCHAR(10)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS upi_id VARCHAR(100)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS upi_ids TEXT",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS shop_categories TEXT",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS is_online_store_enabled BOOLEAN DEFAULT FALSE",
            # Marketplace ratings — added after older production databases were initialized.
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS rating_score FLOAT NOT NULL DEFAULT 0",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS rating_count INTEGER NOT NULL DEFAULT 0",
            # Online-only store configuration — source of truth for owner/customer flows.
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS online_setup_fee NUMERIC(10,2) NOT NULL DEFAULT 0",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS online_min_order NUMERIC(10,2) NOT NULL DEFAULT 0",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS online_delivery_fee NUMERIC(10,2) NOT NULL DEFAULT 0",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS online_offer_delivery BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS online_offer_pickup BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS online_accept_cod BOOLEAN NOT NULL DEFAULT TRUE",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS online_accept_online BOOLEAN NOT NULL DEFAULT FALSE",

            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS pan_number VARCHAR(50)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS registration_number VARCHAR(100)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS contact_person_name VARCHAR(100)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS contact_person_phone VARCHAR(20)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS contact_person_email VARCHAR(100)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS color_primary VARCHAR(20)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS color_secondary VARCHAR(20)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS logo_file_path VARCHAR(500)",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS logo_version INTEGER DEFAULT 0",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMP",
            "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
            "UPDATE shop_profiles SET is_active = TRUE WHERE is_active IS NULL",
            # online_customers — extra fields for delivery
            "ALTER TABLE online_customers ADD COLUMN IF NOT EXISTS phone VARCHAR(20)",
            "ALTER TABLE online_customers ADD COLUMN IF NOT EXISTS city VARCHAR(100)",
            "ALTER TABLE online_customers ADD COLUMN IF NOT EXISTS address TEXT",
            # online_orders — payment tracking must exist before customer-order queries run.
            # Safe defaults keep legacy orders unpaid; notification-confirmed UPI is never assumed paid.
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) NOT NULL DEFAULT 'COD'",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS payment_status VARCHAR(24) NOT NULL DEFAULT 'COD_DUE'",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(128)",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS payment_confirmation_source VARCHAR(50)",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS payment_detection_key VARCHAR(128)",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS payment_confirmed_at TIMESTAMP",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_online_order_shop_payment_key ON online_orders(shop_id, payment_detection_key)",
            # online_orders — idempotent checkout retries
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128)",
            "CREATE INDEX IF NOT EXISTS ix_online_orders_idempotency_key ON online_orders(idempotency_key)",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS online_setup_fee NUMERIC(10,2) NOT NULL DEFAULT 0",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS branch_id INTEGER",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS coupon_code VARCHAR(50)",
            "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(12,2) NOT NULL DEFAULT 0",
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS branch_id INTEGER",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS branch_id INTEGER",
            "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS branch_id INTEGER",
            "ALTER TABLE shop_expenses ADD COLUMN IF NOT EXISTS branch_id INTEGER",
        ]
        for migration_sql in safe_migrations:
            try:
                _db.execute(text(migration_sql))
                _db.commit()
            except Exception as col_err:
                _db.rollback()
                logger.warning(f"Migration skipped (non-critical): {col_err}")
        _db.close()
        logger.info("✅ Safe column migrations applied successfully.")
    except Exception as migration_err:
        logger.error(f"❌ Migration block failed: {migration_err}")


else:
    logger.info("Alembic bootstrap completed; skipping import-time schema DDL")

# ========================
# SECURITY MIDDLEWARE
# ========================

from host_validation import build_allowed_hosts, build_allowed_origins

# Render can assign a new onrender.com hostname when a service is recreated.
# Keep explicit ALLOWED_HOSTS restrictions, but always add Render's authoritative
# RENDER_EXTERNAL_HOSTNAME (or hostname parsed from RENDER_EXTERNAL_URL). This
# prevents TrustedHostMiddleware from rejecting the service's own URL with 400.
ALLOWED_HOSTS = build_allowed_hosts(os.environ)
# The customer storefront at retail-mind-1.onrender.com creates online orders,
# so allow this exact HTTPS origin even when ALLOWED_ORIGINS is also configured.
# Keep any deployment-specific origins from the environment.
_EXTRA_ALLOWED_ORIGINS = ",".join(
    value
    for value in (
        os.getenv("ALLOWED_ORIGINS", "").strip(),
        "https://retail-mind-1.onrender.com",
        "https://final-production-nwkl.onrender.com",
    )
    if value
)
ALLOWED_ORIGINS = build_allowed_origins(
    ALLOWED_HOSTS,
    _EXTRA_ALLOWED_ORIGINS,
)

# 1. CORS — Restrict to known origins only (no wildcard *)
api.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # 🔧 FIX: 'flutter run' on Chrome (debug/dev mode) serves the app from
    # http://localhost:<random-port> — a different port every single
    # launch. The static allow_origins list above only ever matched
    # localhost:3000/localhost:8000 exactly, so every other debug session
    # got silently CORS-blocked by the browser (shows up client-side as a
    # generic "Failed to fetch" / "All backends unreachable" with zero
    # indication it was actually a CORS rejection, not a real outage).
    # This regex covers any localhost/127.0.0.1 port for local development
    # without loosening anything for production origins, which still go
    # through the exact allow_origins list above.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Accept-Language",
        "Content-Language",
        "X-Device-ID",
    ],
)

# 2. Trusted Host — prevent Host header injection attacks
api.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)  # Set to ALLOWED_HOSTS in production

# 2b. Security response headers — these were previously only exposed via an
# informational GET endpoint (/security-headers) and never actually attached
# to real responses. Attach them for real here.
@api.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# 3. Request Logging & Timing Middleware
@api.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)

    # Mask sensitive paths in logs

    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"{request.method} {path} -> {response.status_code} [{duration_ms}ms] from {client_ip}")
    response.headers["X-Response-Time"] = f"{duration_ms}ms"
    return response

# 4. Global Exception Handler — never leak stack traces to clients
@api.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # TODO: Integrate sentry_sdk.capture_exception(exc) here
    logger.error(f"CRITICAL: Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error. Our team has been notified.",
            "path": request.url.path,
            "incident_id": str(time.time())  # Provide a trace ID for support
        }
    )


# ========================
# REGISTER ALL ROUTERS
# ========================

# Auth
api.include_router(authentication_router, prefix="/auth", tags=["Authentication"])
api.include_router(subscription_billing_router, tags=["Subscription Billing"])
api.include_router(subscription_entitlements_router, tags=["Subscription Entitlements"])
api.include_router(auth_hardening_router, tags=["Authentication Hardened"])
api.include_router(session_router, tags=["Session Management"])
api.include_router(logs_router, tags=["Client Logging"])

# Core ERP
api.include_router(bill_router, prefix="/bill", tags=["Bill Generation"])
api.include_router(inventory_router, tags=["Inventory Management"])
api.include_router(inventory_sync_router, tags=["Inventory Sync Service"])
api.include_router(inventory_reconcile_router, tags=["Inventory Reconciliation"])
api.include_router(sales_restore_router, tags=["Sales Restoration"])
api.include_router(attendance_router, tags=["Attendance Management"])
api.include_router(invoices_router, tags=["Invoices & Billing"])
api.include_router(customers_router, tags=["Customer Management"])
api.include_router(shop_management_router, tags=["Shop Management"])

# Enterprise Modules
api.include_router(shop_settings_router)          # /shop/*
api.include_router(khata_router)                  # /khata/*
api.include_router(new_khata_engine_router)          # /api/khata/*
api.include_router(purchase_orders_router)        # /purchase-orders/*
api.include_router(online_store_router)           # /store/*
api.include_router(cashfree_online_payments_router)  # /store/* Cashfree PG checkout/webhook
api.include_router(customer_ai_router)              # /store/customer-ai
api.include_router(growth_router)                   # /growth/*
api.include_router(customer_growth_router)           # /store/customer growth
api.include_router(whatsapp_orders_router)
api.include_router(intelligence_router)           # /expenses, /workers, /bank-recon, /enterprise/*, /retail/*
api.include_router(gst_and_giftcards_router)      # /gift-cards, /gst/*

# Legacy extended features
api.include_router(new_features_router, tags=["Legacy Features"])

# Debug routes are disabled in production by default. Enable explicitly with
# ENABLE_DEBUG_ROUTES=true for controlled diagnostics.
if os.getenv("ENABLE_DEBUG_ROUTES", "false").strip().lower() == "true":
    api.include_router(debug_router)
api.include_router(query_router, tags=["Query Retrieval"])

# Advanced System Features
api.include_router(caching_router,tags=["Caching System"])
api.include_router(batch_operations_router, tags=["Batch Operations"])
api.include_router(security_hardening_router, tags=["Security Hardening"])
api.include_router(observability_router, tags=["Observability"])
api.include_router(operations_router, prefix="/api", tags=["Operations"])
api.include_router(realtime_router)
api.include_router(durable_sync_router)
api.include_router(health_router)

# 🚀 PERFORMANCE: Setup performance monitoring middleware
setup_performance_middleware(api)

# ========================
# ROOT & HEALTH ENDPOINTS
# ========================
@api.api_route("/", methods=["GET", "HEAD"], tags=["System"])
async def root(request: Request):
    # Render and other platform probes may issue HEAD / before GET /. Return
    # a body-less success response so that probe traffic does not get a 405.
    if request.method == "HEAD":
        return Response(status_code=200, headers={"Cache-Control": "no-store"})

    return {
        "status": "operational",
        "app": "AI Shop Pro Enterprise Backend",
        "version": "3.0.0",
        "modules": [
            "Authentication (RBAC: OWNER/CUSTOMER/WORKER)",
            "Shop Settings & UPI QR",
            "Inventory Management",
            "Invoices & Billing (with auto-sync)",
            "Khata Ledger",
            "Purchase Orders",
            "Expense Tracker",
            "Worker Management",
            "Bank Reconciliation",
            "Online Store",
            "Enterprise P&L Tracker",
            "Retail Intelligence",
            "Attendance Management",
        ],
        "security": [
            "JWT RBAC enforced",
            "Rate limiting active",
            "Brute-force login protection",
            "SQL injection blocking",
            "XSS input sanitization",
            "CORS restricted",
            "No data leakage across shops",
        ]
    }

@api.get("/api/time", tags=["System"])
async def api_time():
    """Return UTC server time for client clock-drift checks."""
    return {"timestamp": datetime.now(timezone.utc).isoformat()}

@api.get("/health", tags=["System"])
async def health_check():
    from db import sessionLocal
    from sqlalchemy import text
    db_ok = False
    try:
        db = sessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        pass
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "timestamp": time.time(),
    }

@api.get("/shop/{shop_id}", tags=["Online Store API"])
async def serve_shop_frontend(request: Request, shop_id: str):
    """Return shop data as JSON - frontend handles rendering."""
    from db import sessionLocal
    from models import ShopProfile
    from sqlalchemy import text
    
    try:
        db = sessionLocal()
        shop = db.query(ShopProfile).filter(ShopProfile.id == int(shop_id)).first()
        db.close()
        
        if shop:
            return {
                "shop_id": shop.id,
                "shop_name": shop.shop_name,
                "address": shop.address,
                "phone": shop.phone,
                "upi_id": getattr(shop, 'upi_id', None),
                "is_online": getattr(shop, 'is_online_store_enabled', False),
                "message": "Shop data retrieved successfully"
            }
        else:
            return {"error": "Shop not found", "shop_id": shop_id}, 404
    except Exception as e:
        return {"error": "Failed to retrieve shop data", "details": str(e)}, 500

# Adobe Express Creative Studio is a separate app route and directory.
# Keep it isolated from the existing /static asset mount below.
@api.get("/creative-studio", include_in_schema=False)
async def serve_creative_studio():
    page_path = os.path.join(
        os.path.dirname(__file__),
        "creative_studio",
        "index.html",
    )
    if not os.path.isfile(page_path):
        raise HTTPException(status_code=404, detail="Creative Studio page is not installed.")
    return FileResponse(page_path, media_type="text/html")


@api.get("/api/creative-studio/config", tags=["Creative Studio"])
async def get_creative_studio_config():
    # The Embed SDK Client ID is a public client identifier, not a client secret.
    client_id = os.getenv("ADOBE_EXPRESS_CLIENT_ID", "").strip()
    app_name = (
        os.getenv("ADOBE_EXPRESS_APP_NAME", "Retail Mind Creative Studio").strip()
        or "Retail Mind Creative Studio"
    )
    return {
        "configured": bool(client_id),
        "client_id": client_id or None,
        "app_name": app_name,
    }


# Serve backend-managed media such as uploaded shop logos.
static_root = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_root, exist_ok=True)
api.mount("/static", StaticFiles(directory=static_root), name="static")


@api.get("/shop/{shop_id}/ssr", tags=["Online Store API"])
async def serve_shop_frontend_ssr(request: Request, shop_id: str, db: Session = Depends(get_db)):
    """Return shop data as JSON - frontend handles rendering (SSR endpoint)."""
    from models import ShopProfile
    
    try:
        shop = db.query(ShopProfile).filter(ShopProfile.id == int(shop_id)).first()
        
        if shop:
            return {
                "shop_id": shop.id,
                "shop_name": shop.shop_name,
                "address": shop.address,
                "phone": shop.phone,
                "upi_id": getattr(shop, 'upi_id', None),
                "is_online": getattr(shop, 'is_online_store_enabled', False),
                "message": "Shop data retrieved successfully"
            }
        else:
            return {"error": "Shop not found", "shop_id": shop_id}, 404
    except Exception as e:
        return {"error": "Failed to retrieve shop data", "details": str(e)}, 500

