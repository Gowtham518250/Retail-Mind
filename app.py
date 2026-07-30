"""
🚀 AI Shop Pro Enterprise Backend — Main Application
====================================================
Fully secured FastAPI app with:
- Role-Based Access Control (RBAC)
- Rate Limiting & Brute-Force Protection
- CORS restricted to known origins
- SQL Injection & XSS Protection
- All ERP modules registered
"""

from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
import os
import time
import logging
from performance_middleware import setup_performance_middleware

# ========================
# LOGGING SETUP
# ========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("ai_shop_pro")

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
from auth_hardening_service import router as auth_hardening_router
from session_routes import router as session_router

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
from whatsapp_orders import router as whatsapp_orders_router
from retail_intelligence import router as intelligence_router
from gst_and_giftcards import router as gst_and_giftcards_router

# Legacy extended features (non-chatbot)
from new_feature_routers import router as new_features_router

# Advanced system features
from caching_system import router as caching_router
from batch_operations import router as batch_operations_router
from security_hardening import router as security_hardening_router
from observability_service import router as observability_router
from operations_routes import router as operations_router

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
        # online_customers — extra fields for delivery
        "ALTER TABLE online_customers ADD COLUMN IF NOT EXISTS phone VARCHAR(20)",
        "ALTER TABLE online_customers ADD COLUMN IF NOT EXISTS city VARCHAR(100)",
        "ALTER TABLE online_customers ADD COLUMN IF NOT EXISTS address TEXT",
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

# ========================
# SECURITY MIDDLEWARE
# ========================

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,retail-mind-vkbp.onrender.com,retail-mind-web.onrender.com").split(",")

# CORS needs full origins (scheme + host) — browsers send e.g. "https://example.com"
# as the Origin header, which never matches a bare hostname like "example.com".
# Build proper origins from ALLOWED_HOSTS, plus explicit extra origins (e.g. the
# deployed static frontend, which may live on a different domain than the API).
_extra_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
ALLOWED_ORIGINS = [
    origin for host in ALLOWED_HOSTS
    for origin in ([f"https://{host}", f"http://{host}"] if host not in ("localhost", "127.0.0.1") else [f"http://{host}:3000", f"http://{host}:8000"])
] + [o.strip() for o in _extra_origins if o.strip()]

# 1. CORS — Restrict to known origins only (no wildcard *)
api.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
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


# Simple SEO header middleware for storefront pages
@api.middleware("http")
async def seo_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    try:
        path = request.url.path or ""
        host = request.headers.get("host", "")
        shop_id = request.query_params.get("shop_id")
        if path.startswith("/store") or shop_id:
            # canonical link header
            if shop_id:
                canonical = f"https://{host}/store?shop_id={shop_id}"
            else:
                canonical = f"https://{host}{path}"
            # only set if not present
            if "Link" not in response.headers:
                response.headers["Link"] = f'<{canonical}>; rel="canonical"'
            response.headers.setdefault("X-RetailShop-Storefront", "1")
            response.headers.setdefault("X-Robots-Tag", "index, follow")
    except Exception:
        pass
    return response

# Redirect dashboard links with shop_id to the public storefront.
@api.middleware("http")
async def dashboard_storefront_redirect(request: Request, call_next):
    if request.url.path in {"/dashboard", "/dashboard/"}:
        shop_id = request.query_params.get("shop_id")
        if shop_id:
            return RedirectResponse(url=f"/store?shop_id={shop_id}")
    return await call_next(request)

# ========================
# REGISTER ALL ROUTERS
# ========================

# Auth
api.include_router(authentication_router, prefix="/auth", tags=["Authentication"])
api.include_router(auth_hardening_router, tags=["Authentication Hardened"])
api.include_router(session_router, tags=["Session Management"])

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
api.include_router(whatsapp_orders_router)
api.include_router(intelligence_router)           # /expenses, /workers, /bank-recon, /enterprise/*, /retail/*
api.include_router(gst_and_giftcards_router)      # /gift-cards, /gst/*

# Legacy extended features
api.include_router(new_features_router, tags=["Legacy Features"])

# Advanced System Features
api.include_router(caching_router, prefix="/cache", tags=["Caching System"])
api.include_router(batch_operations_router, tags=["Batch Operations"])
api.include_router(security_hardening_router, tags=["Security Hardening"])
api.include_router(observability_router, tags=["Observability"])
api.include_router(operations_router, prefix="/api", tags=["Operations"])

# 🚀 PERFORMANCE: Setup performance monitoring middleware
setup_performance_middleware(api)

# ========================
# ROOT & HEALTH ENDPOINTS
# ========================
@api.get("/", tags=["System"])
async def root(request: Request):
    shop_id = request.query_params.get("shop_id")
    if shop_id:
        web_out_index = os.path.join(os.path.dirname(__file__), "frontend-web", "out", "index.html")
        vite_dist_index = os.path.join(os.path.dirname(__file__), "frontend", "dist", "index.html")

        target_index = None
        if os.path.exists(web_out_index):
            target_index = web_out_index
        elif os.path.exists(vite_dist_index):
            target_index = vite_dist_index

        if target_index and os.path.exists(target_index):
            with open(target_index, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())

        return HTMLResponse(
            content="<h1>Storefront frontend not found. Please build the web frontend.</h1>",
            status_code=404
        )

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

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


def build_shop_frontend_redirect_url(request: Request, shop_id: str) -> str:
    """Resolve the frontend URL that should render the public shop page."""
    configured_frontend_url = (
        os.getenv("NEXTJS_FRONTEND_URL")
        or os.getenv("FRONTEND_URL")
        or os.getenv("PUBLIC_BASE_URL")
    )

    if configured_frontend_url:
        return f"{configured_frontend_url.rstrip('/')}/?shop_id={shop_id}"

    # Prefer a same-origin storefront route for public shop links.
    return f"/store?shop_id={shop_id}"


@api.get("/shop/{shop_id}", tags=["Online Store Frontend"])
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

# Mount static asset folders for both Next.js (_next) and Vite (assets)
frontend_web_out = os.path.join(os.path.dirname(__file__), "frontend-web", "out")
frontend_vite_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")

next_assets_path = os.path.join(frontend_web_out, "_next")
if os.path.exists(next_assets_path):
    api.mount("/_next", StaticFiles(directory=next_assets_path), name="next_assets")

vite_assets_path = os.path.join(frontend_vite_dist, "assets")
if os.path.exists(vite_assets_path):
    api.mount("/assets", StaticFiles(directory=vite_assets_path), name="vite_assets")


@api.get("/dashboard", tags=["Web UI"])
async def serve_dashboard(request: Request):
    """Serve the React Web Dashboard index.html directly."""
    shop_id = request.query_params.get("shop_id")
    if shop_id:
        return RedirectResponse(url=f"/store?shop_id={shop_id}")

    web_out_index = os.path.join(frontend_web_out, "index.html")
    vite_dist_index = os.path.join(frontend_vite_dist, "index.html")

    target_index = None
    if os.path.exists(web_out_index):
        target_index = web_out_index
    elif os.path.exists(vite_dist_index):
        target_index = vite_dist_index

    if target_index and os.path.exists(target_index):
        with open(target_index, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return HTMLResponse(
        content="<h1>Dashboard frontend not found. Please build the web frontend.</h1>",
        status_code=404
    )


store_web_out = os.path.join(os.path.dirname(__file__), "frontend-web", "out")
store_vite_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")


# Serve storefront index at /store and inject per-shop metadata for SEO when `?shop_id=` is present.
@api.get("/store", tags=["Storefront"])
async def serve_storefront(request: Request):
    from db import sessionLocal
    from models import ShopProfile
    import html as _html

    shop_id = request.query_params.get("shop_id")
    # Choose built index: storefront build in frontend-web/out should be preferred.
    index_path = None
    if os.path.exists(store_web_out):
        index_path = os.path.join(store_web_out, "index.html")
    elif os.path.exists(store_vite_dist):
        index_path = os.path.join(store_vite_dist, "index.html")

    if not index_path or not os.path.exists(index_path):
        return HTMLResponse(content="<h1>Storefront not found. Please build the customer storefront web frontend.</h1>", status_code=404)

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        # initialize cache container if missing
        try:
            _storefront_cache
        except NameError:
            _storefront_cache = {}
        CACHE_TTL = int(os.getenv('STOREFRONT_CACHE_TTL', '60'))

        # Serve cached HTML when available and fresh
        if shop_id:
            cache_key = f"store:{shop_id}"
            cached = _storefront_cache.get(cache_key)
            now = time.time()
            if cached and cached[1] > now:
                resp = HTMLResponse(content=cached[0])
                resp.headers['X-Cache'] = 'HIT'
                return resp

        if shop_id:
            try:
                db = sessionLocal()
                from sqlalchemy import text
                row = db.execute(text("SELECT id, shop_name, shop_description, logo_url FROM shop_profiles WHERE id = :id LIMIT 1"), {"id": int(shop_id)}).fetchone()
                db.close()
            except Exception:
                row = None

            if row:
                shop_name = row[1] or ''
                shop_description = row[2] or ''
                logo = row[3] or None
                title = _html.escape(f"{shop_name} — RetailShop")
                description = _html.escape(shop_description or shop_name)
                canonical = f"https://{request.headers.get('host', '')}/store?shop_id={shop_id}"
                meta = (
                    f"<title>{title}</title>\n"
                    f"<meta name=\"description\" content=\"{description}\"/>\n"
                    f"<meta property=\"og:title\" content=\"{title}\"/>\n"
                    f"<meta property=\"og:description\" content=\"{description}\"/>\n"
                    f"<meta property=\"og:url\" content=\"{canonical}\"/>\n"
                )
                if logo:
                    meta += f"<meta property=\"og:image\" content=\"{_html.escape(logo)}\"/>\n"

                # inject meta into <head>
                import re
                html = re.sub(r"(<head[^>]*>)([\s\S]*?)", lambda m: m.group(1) + "\n" + meta + m.group(2), html, count=1)

                # cache the rendered HTML
                _storefront_cache[cache_key] = (html, time.time() + CACHE_TTL)

        resp = HTMLResponse(content=html)
        if shop_id:
            resp.headers['X-Cache'] = 'MISS'
        return resp
    except Exception as e:
        return HTMLResponse(content=f"<h1>Failed to render storefront: {e}</h1>", status_code=500)

# Keep existing /dashboard static mount for owner admin UI if present
if os.path.exists(frontend_web_out):
    api.mount("/dashboard", StaticFiles(directory=frontend_web_out, html=True), name="dashboard")
elif os.path.exists(frontend_vite_dist):
    api.mount("/dashboard", StaticFiles(directory=frontend_vite_dist, html=True), name="dashboard")



templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@api.get("/shop/{shop_id}/ssr", tags=["Online Store Frontend"])
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


@api.get("/login", tags=["Web UI"])
async def serve_login_page():
    file_path = os.path.join(os.path.dirname(__file__), "login.html")
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>Login page not found.</h1>", status_code=404)
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@api.get("/signup", tags=["Web UI"])
async def serve_signup_page():
    file_path = os.path.join(os.path.dirname(__file__), "signup.html")
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>Signup page not found.</h1>", status_code=404)
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@api.get("/reset-password", tags=["Web UI"])
async def serve_reset_password_page():
    file_path = os.path.join(os.path.dirname(__file__), "reset_password.html")
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>Reset password page not found.</h1>", status_code=404)
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@api.get("/orders", tags=["Web UI"])
async def serve_orders_page():
    file_path = os.path.join(os.path.dirname(__file__), "orders.html")
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>Orders page not found.</h1>", status_code=404)
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@api.get("/cart", tags=["Web UI"])
async def serve_cart_page():
    file_path = os.path.join(os.path.dirname(__file__), "cart.html")
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>Cart page not found.</h1>", status_code=404)
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@api.get("/product/{product_id}", tags=["Web UI"])
async def serve_product_detail_page(product_id: str):
    file_path = os.path.join(os.path.dirname(__file__), "product_detail.html")
    if not os.path.exists(file_path):
        return HTMLResponse(content="<h1>Product detail page not found.</h1>", status_code=404)
    with open(file_path, "r", encoding="utf-8") as f:
        # inject product_id into HTML for client-side fetch
        content = f.read().replace("{{PRODUCT_ID}}", str(product_id))
    return HTMLResponse(content=content)

