"""
🔒 SECURITY MODULE — AI Shop Pro Enterprise Backend
Covers:
  - Role-Based Access Control (RBAC): OWNER, CUSTOMER, WORKER
  - Secure JWT decoding and validation
  - Input sanitization (SQL injection / XSS prevention)
  - Rate limiter (in-memory, per IP)
  - Brute-force login protection
  - Sensitive data field masking utilities
"""

import os
import re
import time
import hashlib
from typing import Optional
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
import logging
import redis as redis_module

# =====================
# CONSTANTS
# =====================
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set. Refusing to start.")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
# Access tokens are intentionally short-lived. Mobile clients silently exchange
# the separately issued 7-day refresh token for a fresh access token as needed.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Roles
ROLE_OWNER = "OWNER"
ROLE_CUSTOMER = "CUSTOMER"
ROLE_WORKER = "WORKER"
VALID_ROLES = {ROLE_OWNER, ROLE_CUSTOMER, ROLE_WORKER}

# =====================
# PASSWORD HASHING
# =====================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password with bcrypt (follows best practices)"""
    return pwd_context.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash"""
    return pwd_context.verify(password, hashed_password)

# =====================
# TOKEN CREATION
# =====================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token with role embedded"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Wrapper for backward compatibility with authentication.py
def create_access_token_simple(data: dict) -> str:
    """Simple wrapper for create_access_token without expires_delta parameter"""
    return create_access_token(data)

def create_refresh_token(user_id: int, role: str) -> str:
    """Create a long-lived refresh token"""
    data = {"sub": str(user_id), "role": role, "type": "refresh"}
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    data.update({"exp": expire})
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

# =====================
# JWT BEARER EXTRACTOR
# =====================
security_scheme = HTTPBearer()

def decode_token(token: str) -> dict:
    """Decode and validate a JWT token, raise 401 on failure"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> int:
    """Extract and validate the current user from the Bearer token"""
    payload = decode_token(credentials.credentials)
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=401, detail="Refresh tokens cannot authorize API requests")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token payload missing user ID")
    return int(user_id)

def get_current_user_dict(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> dict:
    """Extract and validate the current user from the Bearer token (Returns full dict)"""
    payload = decode_token(credentials.credentials)
    if payload.get("type") == "refresh":
        raise HTTPException(status_code=401, detail="Refresh tokens cannot authorize API requests")
    user_id = payload.get("sub")
    role = payload.get("role", ROLE_OWNER)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token payload missing user ID")
    return {"user_id": int(user_id), "role": role, "payload": payload}

# =====================
# RBAC GUARDS
# =====================
def require_role(*allowed_roles: str):
    """Factory: creates a dependency that blocks any role NOT in allowed_roles"""
    def _check(current_user: dict = Depends(get_current_user_dict)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {allowed_roles}. Your role: {current_user['role']}"
            )
        return current_user
    return _check

# Convenience guards
def owner_only(current_user: dict = Depends(require_role(ROLE_OWNER))):
    return current_user

def customer_only(current_user: dict = Depends(require_role(ROLE_CUSTOMER))):
    return current_user

def worker_or_owner(current_user: dict = Depends(require_role(ROLE_OWNER, ROLE_WORKER))):
    return current_user

def resolve_shop_id(current_user) -> int:
    """Extract integer shop/user id from RBAC dependency result."""
    if isinstance(current_user, dict):
        uid = current_user.get("user_id") or current_user.get("sub")
        if uid is None:
            raise HTTPException(status_code=401, detail="Invalid user context")
        return int(uid)
    return int(current_user)

# =====================
# RATE LIMITER (Redis-backed with local fallback)
# =====================
logger = logging.getLogger(__name__)

# These maps remain a safe local fallback for development/test environments or
# during a Redis outage. In production, set REDIS_URL so workers share limits.
_rate_limit_store: dict = defaultdict(list)  # {ip: [timestamp, ...]}
_login_fail_store: dict = defaultdict(int)   # {ip: fail_count}
_login_lockout: dict = defaultdict(float)    # {ip: unlock_timestamp}
_security_redis_client = None

RATE_LIMIT_CALLS = int(os.getenv("RATE_LIMIT_CALLS", 100))
RATE_LIMIT_WINDOW_SECS = int(os.getenv("RATE_LIMIT_WINDOW_SECS", 60))
LOGIN_MAX_FAILS = int(os.getenv("LOGIN_MAX_FAILS", 5))
LOGIN_LOCKOUT_SECS = int(os.getenv("LOGIN_LOCKOUT_SECS", 300))


def _get_security_redis_client():
    """Create a lazy Redis client when REDIS_URL is configured."""
    global _security_redis_client
    if _security_redis_client is not None:
        return _security_redis_client
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        _security_redis_client = redis_module.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
    except Exception as exc:
        # A malformed/missing Redis endpoint should not make authentication
        # routes unavailable; callers will use the bounded in-memory fallback.
        logger.warning("Unable to configure shared security limiter (%s)", type(exc).__name__)
        return None
    return _security_redis_client


def _security_ip_key(ip: str) -> str:
    # Avoid writing raw IP addresses into Redis key names.
    return hashlib.sha256((ip or "unknown").encode("utf-8")).hexdigest()[:32]


def check_rate_limit(request: Request):
    """Block over-limit IPs using a shared Redis counter when configured."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = max(1, RATE_LIMIT_WINDOW_SECS)
    redis_client = _get_security_redis_client()

    if redis_client is not None:
        bucket = int(now // window)
        key = f"retail_mind:security:rate:{bucket}:{_security_ip_key(ip)}"
        try:
            current_count = int(redis_client.incr(key))
            # Refresh TTL on every hit so a transient EXPIRE failure on the first
            # increment cannot leave a permanent counter behind. The bucket is
            # part of the key, so this does not merge adjacent windows.
            redis_client.expire(key, window * 2)
            if current_count > RATE_LIMIT_CALLS:
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Limit: {RATE_LIMIT_CALLS} per {window}s. Slow down!",
                )
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Shared request rate limiter unavailable; using local fallback (%s)", type(exc).__name__)

    window_start = now - window
    _rate_limit_store[ip] = [timestamp for timestamp in _rate_limit_store[ip] if timestamp > window_start]
    if len(_rate_limit_store[ip]) >= RATE_LIMIT_CALLS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Limit: {RATE_LIMIT_CALLS} per {window}s. Slow down!",
        )
    _rate_limit_store[ip].append(now)


def check_login_lockout(ip: str):
    """Raise 429 when the shared/local failed-login lockout is active."""
    redis_client = _get_security_redis_client()
    if redis_client is not None:
        lockout_key = f"retail_mind:security:login-lockout:{_security_ip_key(ip)}"
        try:
            if redis_client.get(lockout_key):
                ttl = int(redis_client.ttl(lockout_key) or 0)
                secs_remaining = ttl if ttl > 0 else LOGIN_LOCKOUT_SECS
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many failed login attempts. Try again in {secs_remaining} seconds.",
                )
            # Also honor any local lockout created while Redis was unavailable.
            # Successful authentication clears local and shared state together.
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Shared login lockout unavailable; using local fallback (%s)", type(exc).__name__)

    if _login_lockout[ip] > time.time():
        secs_remaining = max(1, int(_login_lockout[ip] - time.time()))
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {secs_remaining} seconds.",
        )


def record_login_failure(ip: str):
    """Track failed logins in Redis so the threshold is shared across workers."""
    redis_client = _get_security_redis_client()
    if redis_client is not None:
        failures_key = f"retail_mind:security:login-failures:{_security_ip_key(ip)}"
        lockout_key = f"retail_mind:security:login-lockout:{_security_ip_key(ip)}"
        try:
            failures = int(redis_client.incr(failures_key))
            # Expire the failure count so old attempts do not persist forever.
            redis_client.expire(failures_key, max(1, LOGIN_LOCKOUT_SECS))
            if failures >= LOGIN_MAX_FAILS:
                redis_client.set(lockout_key, "1", ex=max(1, LOGIN_LOCKOUT_SECS))
                redis_client.delete(failures_key)
            return
        except Exception as exc:
            logger.warning("Shared login failure counter unavailable; using local fallback (%s)", type(exc).__name__)

    _login_fail_store[ip] += 1
    if _login_fail_store[ip] >= LOGIN_MAX_FAILS:
        _login_lockout[ip] = time.time() + LOGIN_LOCKOUT_SECS
        _login_fail_store[ip] = 0


def record_login_success(ip: str):
    """Clear failed-login and lockout state from the shared/local stores."""
    redis_client = _get_security_redis_client()
    if redis_client is not None:
        try:
            redis_client.delete(
                f"retail_mind:security:login-failures:{_security_ip_key(ip)}",
                f"retail_mind:security:login-lockout:{_security_ip_key(ip)}",
            )
        except Exception as exc:
            logger.warning("Shared login success reset unavailable (%s)", type(exc).__name__)
    _login_fail_store[ip] = 0
    _login_lockout[ip] = 0

# =====================
# INPUT SANITIZATION
# =====================
_SQL_INJECTION_PATTERN = re.compile(
    r"(--|;|/\*|\*/|xp_|EXEC|DROP|INSERT|UPDATE|DELETE|SELECT|UNION|ALTER|CREATE|TRUNCATE)",
    re.IGNORECASE,
)
_XSS_PATTERN = re.compile(r"(<script|</script|javascript:|on\w+=)", re.IGNORECASE)

def sanitize_input(value: str, field_name: str = "input") -> str:
    """Block SQL injection and XSS in string inputs"""
    if not isinstance(value, str):
        return value
    if _SQL_INJECTION_PATTERN.search(value):
        raise HTTPException(
            status_code=400,
            detail=f"Malicious SQL pattern detected in field '{field_name}'. Request blocked."
        )
    if _XSS_PATTERN.search(value):
        raise HTTPException(
            status_code=400,
            detail=f"Malicious script pattern detected in field '{field_name}'. Request blocked."
        )
    return value.strip()

# =====================
# DATA MASKING UTILITIES
# =====================
def mask_phone(phone: str) -> str:
    """Mask phone number for logs: 9876543210 → 98****3210"""
    if not phone or len(phone) < 6:
        return "****"
    return phone[:2] + "*" * (len(phone) - 4) + phone[-4:]

def mask_upi(upi_id: str) -> str:
    """Mask UPI ID for logs: user@bank → us**@bank"""
    if not upi_id or "@" not in upi_id:
        return "****"
    parts = upi_id.split("@")
    return parts[0][:2] + "**@" + parts[1]

def mask_email(email: str) -> str:
    """Mask email for logs: user@example.com → us**@example.com"""
    if not email or "@" not in email:
        return "****"
    parts = email.split("@")
    return parts[0][:2] + "**@" + parts[1]
