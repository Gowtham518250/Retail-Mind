from urllib.parse import quote_plus, urlparse, urlunparse
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import os
import logging
import re
import time
from fastapi import HTTPException
from dotenv import load_dotenv
from sqlalchemy.engine import URL
from db_pool_config import pool_options_from_env, log_pool_budget

logger = logging.getLogger(__name__)


def _slow_db_query_threshold_ms() -> int:
    """Slow SQL logging threshold; log metadata only, never bound parameter values."""
    try:
        return min(10000, max(1, int(os.getenv("DB_SLOW_QUERY_THRESHOLD_MS", "150"))))
    except (TypeError, ValueError):
        return 150


def _sql_statement_summary(statement: str) -> str:
    """Return a low-sensitivity SQL summary without logging values or full SQL."""
    normalized = " ".join(str(statement).split())
    operation = normalized.split(" ", 1)[0].upper() if normalized else "UNKNOWN"
    tables = re.findall(
        r'\b(?:FROM|JOIN|UPDATE|INTO)\s+([A-Za-z_][\w.$"]*)',
        normalized,
        flags=re.IGNORECASE,
    )
    unique_tables = list(dict.fromkeys(table.strip('"') for table in tables))[:3]
    if unique_tables:
        return f"{operation} tables={','.join(unique_tables)}"
    return operation


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if context is not None:
        context._retail_mind_sql_started_at = time.perf_counter()


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    started = getattr(context, "_retail_mind_sql_started_at", None)
    if started is None:
        return
    elapsed_ms = (time.perf_counter() - started) * 1000
    if elapsed_ms >= _slow_db_query_threshold_ms():
        logger.warning(
            "SLOW DB STATEMENT duration_ms=%.2f summary=%s",
            elapsed_ms,
            _sql_statement_summary(statement),
        )


def _statement_timeout_ms() -> int:
    """Return the optional app-side PostgreSQL statement timeout in milliseconds.

    A positive value adds one SET LOCAL round trip to each transaction. Prefer
    a provider/database-side statement timeout for remote pooled databases.
    """
    try:
        return max(0, int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "0")))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid DB_STATEMENT_TIMEOUT_MS; app-side timeout disabled (0ms)"
        )
        return 0


def _set_postgres_statement_timeout(connection) -> None:
    """Optionally apply a per-transaction timeout without a startup parameter.

    Some hosted poolers reject statement_timeout in startup options, and
    transaction pooling can reassign a backend between client transactions.
    SET LOCAL is safe with transaction pooling but costs an additional database
    round trip per transaction. Keep it opt-in; prefer a database-side timeout
    when the provider supports it.
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

# Pool limits are per process. Keep defaults conservative and let deployment
# configuration increase them only after checking the provider connection budget.
pool_options = pool_options_from_env(os.environ)
log_pool_budget(os.environ, pool_options)

if database_url:
    database_url = normalize_database_url(database_url)
    print(f" Using provided DATABASE_URL for PostgreSQL connection.")
    engine = create_engine(
        database_url,
        future=True,
        poolclass=QueuePool,
        pool_pre_ping=True,  # Test connection before using
        **pool_options,
        pool_reset_on_return='rollback',  # Reset connection state on return
        echo=False,
        # Do not pass statement_timeout as a libpq startup option: Neon pooler
        # endpoints reject it. SET LOCAL is applied at each transaction start.
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
            **pool_options,
            pool_reset_on_return='rollback',
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

# Application-side transaction timeouts are opt-in because SET LOCAL adds a
# round trip to every transaction on remote databases. Prefer a provider-side
# statement_timeout; set DB_STATEMENT_TIMEOUT_MS=30000 to enable the app-side
# guard when a database-side timeout is unavailable.
if engine.dialect.name == "postgresql":
    event.listen(engine, "begin", _set_postgres_statement_timeout)

# Separate SQL execution time from pool/setup/commit overhead in slow requests.
# Bound parameters and full SQL text are intentionally omitted from logs.
event.listen(engine, "before_cursor_execute", _before_cursor_execute)
event.listen(engine, "after_cursor_execute", _after_cursor_execute)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
sessionLocal = SessionLocal # Alias for legacy imports
Base = declarative_base()

def get_db():
    """
    Database session dependency with proper transaction cleanup.

    Expected HTTPException responses are rolled back without being mislabeled
    as database failures. Slow commit timings are logged separately.
    """
    db: Session = SessionLocal()
    try:
        yield db
        pending_new = len(db.new)
        pending_dirty = len(db.dirty)
        pending_deleted = len(db.deleted)
        commit_started = time.perf_counter()
        db.commit()
        commit_ms = (time.perf_counter() - commit_started) * 1000
        if commit_ms >= _slow_db_query_threshold_ms():
            logger.warning(
                "SLOW DB COMMIT duration_ms=%.2f new=%s dirty=%s deleted=%s",
                commit_ms,
                pending_new,
                pending_dirty,
                pending_deleted,
            )
    except HTTPException:
        db.rollback()
        logger.debug("Expected HTTP error; database transaction rolled back")
        raise
    except Exception:
        db.rollback()
        logger.exception("Unexpected database/session failure; transaction rolled back")
        raise
    finally:
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




