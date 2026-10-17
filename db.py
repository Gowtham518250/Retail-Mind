from urllib.parse import quote_plus, urlparse, urlunparse
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import os
import logging
from dotenv import load_dotenv
from sqlalchemy.engine import URL

logger = logging.getLogger(__name__)

def _statement_timeout_ms() -> int:
    """Return the configured PostgreSQL statement timeout in milliseconds."""
    try:
        return max(0, int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000")))
    except (TypeError, ValueError):
        logger.warning("Invalid DB_STATEMENT_TIMEOUT_MS; using 30000ms")
        return 30000


def _set_postgres_statement_timeout(connection) -> None:
    """Apply a per-transaction timeout without a libpq startup parameter.

    Neon poolers reject statement_timeout in connection startup options, and
    transaction pooling can reassign a backend between client transactions.
    SET LOCAL applies only to the active transaction, so it works with pooled
    endpoints and is reset automatically at transaction end.
    """
    timeout_ms = _statement_timeout_ms()
    if timeout_ms <= 0:
        return

    # timeout_ms is parsed and constrained to a non-negative integer above.
    connection.exec_driver_sql(
        f"SET LOCAL statement_timeout = '{timeout_ms}ms'"
    )


def normalize_database_url(url: str) -> str:
    """
    Normalize Render database URL:
    - Convert postgres:// scheme to postgresql://
    - Add sslmode=require parameter if not present
    - Add full .oregon-postgres.render.com suffix to short Render hostnames
    """
    if not url:
        return url
    
    parsed = urlparse(url)
    
    # Handle Render short hostnames like dpg-xxx-a
    netloc = parsed.netloc
    if parsed.hostname and parsed.hostname.startswith("dpg-") and "." not in parsed.hostname:
        new_hostname = f"{parsed.hostname}.oregon-postgres.render.com"
        # Reconstruct netloc with new hostname and existing port/userinfo
        if parsed.port:
            netloc = f"{parsed.username}:{parsed.password}@{new_hostname}:{parsed.port}" if parsed.username else f"{new_hostname}:{parsed.port}"
        else:
            netloc = f"{parsed.username}:{parsed.password}@{new_hostname}" if parsed.username else new_hostname
    
    # Handle scheme conversion first
    scheme = parsed.scheme
    if scheme == "postgres":
        scheme = "postgresql"
    
    # Handle sslmode - only add if not present
    from urllib.parse import parse_qs, urlencode
    params = parse_qs(parsed.query)
    if "sslmode" not in params:
        params["sslmode"] = ["require"]
    # Convert params back to query string
    query = urlencode(params, doseq=True)
    
    # Rebuild URL
    new_parsed = parsed._replace(
        scheme=scheme,
        netloc=netloc,
        query=query
    )
    
    return urlunparse(new_parsed)

# Load environment vars from .env files ONLY if not already set in the environment.
# CRITICAL: override=False ensures that real env vars (set by Render/Railway/etc.)
# always take priority over any .env files committed to the repo.
# Without this, a stale DATABASE_URL in a .env file silently overwrites
# Render's injected DATABASE_URL causing "host not found" errors.
if os.path.exists('.env.local'):
    load_dotenv('.env.local', override=False)
    print("Loaded .env.local (override=False — real env vars take priority)")
elif os.path.exists('.env.production'):
    load_dotenv('.env.production', override=False)
    print("Loaded .env.production (override=False — real env vars take priority)")
else:
    load_dotenv(override=False)
    print("Loaded .env (override=False — real env vars take priority)")


# Get database configuration from environment variables
# Render/Railway typically provides 'DATABASE_URL' automatically
database_url = os.getenv("DATABASE_URL")

if database_url:
    database_url = normalize_database_url(database_url)
    print(f" Using provided DATABASE_URL for PostgreSQL connection.")
    engine = create_engine(
        database_url,
        future=True,
        poolclass=QueuePool,
        pool_pre_ping=True,  # Test connection before using
        pool_size=25,         # 🚀 PERFORMANCE: Increased from 10 to 25 for better concurrency
        max_overflow=40,      # 🚀 PERFORMANCE: Increased from 20 to 40 for peak loads
        pool_timeout=30,      # Timeout for getting connection from pool
        pool_recycle=3600,    # 🚀 PERFORMANCE: Increased to 1 hour to reduce connection churn
        pool_reset_on_return='commit',  # Reset connection state on return
        echo=False,
        # Do not pass statement_timeout as a libpq startup option: Neon pooler
        # endpoints reject it. It is set with set_config after connection.
        connect_args={
            'connect_timeout': 10,
        }
    )
else:
    # Fallback to Render Database if DATABASE_URL is not provided
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "postgres")

    # Redact password from logs
    safe_host = f"{db_host}:{db_port}"
    safe_user = db_user if db_user else "postgres"
    print(f" PostgreSQL Configuration fallback:\n  Host: {safe_host}\n  User: {safe_user}\n  Database: {db_name}")
    # Never log password

    # Build connection URL
    url = URL.create(
        drivername="postgresql",
        username=db_user,
        password=db_password,  # Password only used in connection string
        host=db_host,
        port=db_port,
        database=db_name
    )

    try:
        engine = create_engine(
            url,
            future=True,
            poolclass=QueuePool,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
            pool_reset_on_return='commit',
            echo=False,
            # Add additional connection validation
            connect_args={
                'connect_timeout': 10,
            }
        )
    except Exception as e:
        # Redact credentials from error messages
        safe_error = str(e).replace(db_password, "***") if db_password else str(e)
        print(f"Database connection failed: {safe_error}")
        raise

# Preserve the 30-second query guard without sending statement_timeout in the
# connection startup packet (incompatible with Neon pooled connection URLs).
# SET LOCAL runs at transaction start and is safe with transaction pooling.
if engine.dialect.name == "postgresql":
    event.listen(engine, "begin", _set_postgres_statement_timeout)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
sessionLocal = SessionLocal # Alias for legacy imports
Base = declarative_base()

def get_db():
    """
    Database session dependency with proper session management.
    Ensures transactions are properly committed or rolled back.
    """
    db: Session = SessionLocal()
    try:
        yield db
        # Commit if no exception occurred
        db.commit()
    except Exception as e:
        # Rollback on any exception
        db.rollback()
        logger.error(f"Database session error, transaction rolled back: {e}")
        raise
    finally:
        # Always close the session
        db.close()

@contextmanager
def get_db_context():
    """
    Context manager for database sessions.
    Useful for background tasks or non-FastAPI contexts.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database context error, transaction rolled back: {e}")
        raise
    finally:
        db.close()

# Add health check function
def check_database_health():
    """Check if database connection is healthy"""
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False

def dispose_engine():
    """
    Properly dispose of the database engine and connection pool.
    Should be called on application shutdown.
    """
    try:
        logger.info("Disposing database engine and connection pool...")
        engine.dispose()
        logger.info("Database engine disposed successfully")
    except Exception as e:
        logger.error(f"Error disposing database engine: {e}")




