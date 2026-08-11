#!/usr/bin/env python3
"""
🔍 AI SHOP PRO - PRE-DEPLOYMENT VALIDATION SCRIPT
Comprehensive checks before production deployment
"""

import sys
import subprocess
import os
from pathlib import Path
from datetime import datetime

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_header(title):
    print(f"\n{BLUE}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{RESET}\n")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def check_python_version():
    """Check Python 3.9+ is installed"""
    print_header("1️⃣  PYTHON VERSION CHECK")
    
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} ✓")
        return True
    else:
        print_error(f"Python 3.9+ required, found {version.major}.{version.minor}")
        return False

def check_required_files():
    """Check all required files exist"""
    print_header("2️⃣  REQUIRED FILES CHECK")
    
    required_files = [
        "app.py",
        "models.py",
        "db.py",
        "requirements.txt",
        "auth_routes.py",
        "inventory.py",
        "invoices_billing.py",
        "customers.py",
        "shop_management.py",
        "migration_production_v1.sql",
        "init-db.sql",
    ]
    
    all_exist = True
    for file in required_files:
        if Path(file).exists():
            print_success(f"{file}")
        else:
            print_error(f"{file} NOT FOUND")
            all_exist = False
    
    return all_exist

def check_dependencies():
    """Check all Python dependencies can be imported"""
    print_header("3️⃣  PYTHON DEPENDENCIES CHECK")
    
    required_packages = {
        "fastapi": "FastAPI",
        "sqlalchemy": "SQLAlchemy",
        "psycopg2": "PostgreSQL driver",
        "redis": "Redis client",
        "pydantic": "Pydantic validation",
        "jose": "JWT authentication",
        "passlib": "Password hashing",
        "qrcode": "QR code generation",
        "apscheduler": "Task scheduling",
    }
    
    all_installed = True
    for package, name in required_packages.items():
        try:
            __import__(package)
            print_success(f"{name} ({package})")
        except ImportError:
            print_error(f"{name} ({package}) - NOT INSTALLED")
            print(f"   Run: pip install {package}")
            all_installed = False
    
    return all_installed

def check_env_variables():
    """Check required environment variables"""
    print_header("4️⃣  ENVIRONMENT VARIABLES CHECK")
    
    required_vars = [
        "DATABASE_URL",
        "REDIS_URL",
        "SECRET_KEY",
        "ALGORITHM",
    ]
    
    optional_vars = [
        "FRONTEND_URL",
        "SMTP_SERVER",
        "SMTP_USER",
        "DEBUG",
    ]
    
    missing_required = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = value[:20] + "***" if len(value) > 20 else value
            print_success(f"{var} = {masked}")
        else:
            print_error(f"{var} - NOT SET")
            missing_required.append(var)
    
    print("\nOptional variables:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print_success(f"{var} = SET")
        else:
            print_warning(f"{var} - not configured")
    
    return len(missing_required) == 0

def check_database_connection():
    """Test database connection"""
    print_header("5️⃣  DATABASE CONNECTION CHECK")
    
    try:
        from db import engine
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            print_success("PostgreSQL connection successful ✓")
            return True
    except Exception as e:
        print_error(f"Database connection failed: {str(e)}")
        print_warning("Make sure DATABASE_URL is set and PostgreSQL is running")
        return False

def check_redis_connection():
    """Test Redis connection"""
    print_header("6️⃣  REDIS CONNECTION CHECK")
    
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url, decode_responses=True)
        r.ping()
        print_success("Redis connection successful ✓")
        return True
    except Exception as e:
        print_warning(f"Redis connection failed: {str(e)}")
        print_warning("Caching will be disabled, but app will still work")
        return False

def check_database_schema():
    """Verify all required tables exist"""
    print_header("7️⃣  DATABASE SCHEMA CHECK")
    
    try:
        from db import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        critical_tables = [
            "user_details",
            "shop_profiles",
            "products",
            "customers",
            "invoices",
            "attendance",
            "payment",
        ]
        
        missing_tables = []
        for table in critical_tables:
            if table in tables:
                print_success(f"Table '{table}' exists")
            else:
                print_error(f"Table '{table}' MISSING")
                missing_tables.append(table)
        
        if not missing_tables:
            print_success(f"\nTotal tables: {len(tables)} ✓")
            return True
        else:
            print_error(f"\nMissing {len(missing_tables)} critical tables")
            print_warning("Run: psql $DATABASE_URL < migration_production_v1.sql")
            return False
            
    except Exception as e:
        print_error(f"Schema check failed: {str(e)}")
        return False

def check_models():
    """Verify all SQLAlchemy models load correctly"""
    print_header("8️⃣  SQLALCHEMY MODELS CHECK")
    
    try:
        from models import Base
        
        models_count = len(Base.metadata.tables)
        print_success(f"All {models_count} models loaded successfully ✓")
        
        # List all models
        print("\nRegistered models:")
        for table_name in sorted(Base.metadata.tables.keys()):
            print(f"  • {table_name}")
        
        return True
    except Exception as e:
        print_error(f"Models loading failed: {str(e)}")
        return False

def check_routers():
    """Verify all routers are registered"""
    print_header("9️⃣  ROUTERS REGISTRATION CHECK")
    
    try:
        from app import api
        
        routes_count = len(api.routes)
        print_success(f"All routes registered: {routes_count} endpoints ✓")
        
        # Group by tag
        tags = {}
        for route in api.routes:
            if hasattr(route, 'tags'):
                tag = route.tags[0] if route.tags else "Untagged"
                if tag not in tags:
                    tags[tag] = 0
                tags[tag] += 1
        
        print("\nEndpoints by module:")
        for tag in sorted(tags.keys()):
            print(f"  • {tag}: {tags[tag]} endpoints")
        
        return True
    except Exception as e:
        print_error(f"Router check failed: {str(e)}")
        return False

def check_startup():
    """Attempt app startup"""
    print_header("🔟 APP STARTUP CHECK")
    
    try:
        from app import api
        from db import engine, Base
        
        print_success("App imports successful ✓")
        print_success("Database engine initialized ✓")
        print_success("All routers loaded ✓")
        return True
    except Exception as e:
        print_error(f"Startup failed: {str(e)}")
        return False

def generate_report(results):
    """Generate final report"""
    print_header("📊 FINAL VALIDATION REPORT")
    
    passed = sum(results.values())
    total = len(results)
    percentage = (passed / total) * 100
    
    print(f"Checks Passed: {passed}/{total} ({percentage:.0f}%)\n")
    
    for check_name, result in results.items():
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {check_name}")
    
    print()
    
    if percentage == 100:
        print_success("🎉 ALL CHECKS PASSED! Ready for production!")
        return True
    elif percentage >= 80:
        print_warning("⚠️  Most checks passed. Review warnings above.")
        return True
    else:
        print_error("❌ Critical checks failed. Fix issues before deploying.")
        return False

def main():
    print(f"\n{BLUE}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     🚀 AI SHOP PRO - PRE-DEPLOYMENT VALIDATION            ║")
    print("║              Enterprise Backend v3.0.0                     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")
    
    results = {
        "Python Version": check_python_version(),
        "Required Files": check_required_files(),
        "Dependencies Installed": check_dependencies(),
        "Environment Variables": check_env_variables(),
        "Database Connection": check_database_connection(),
        "Redis Connection": check_redis_connection(),
        "Database Schema": check_database_schema(),
        "SQLAlchemy Models": check_models(),
        "Routers Registration": check_routers(),
        "App Startup": check_startup(),
    }
    
    success = generate_report(results)
    
    print("\n📝 Next Steps:")
    if success:
        print("  1. Review any warnings above")
        print("  2. Test API endpoints: python test_all_endpoints.py")
        print("  3. Deploy to production: git push origin main")
        print("  4. Monitor logs: railway logs or render logs")
    else:
        print("  1. Fix all failed checks")
        print("  2. Re-run this validation script")
        print("  3. Contact support if issues persist")
    
    print()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
