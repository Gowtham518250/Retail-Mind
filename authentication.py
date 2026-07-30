import os
import hashlib
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt

# ===== ENV =====
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set. Refusing to start.")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

# =========================
# TOKEN
# =========================
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# =========================
# PASSWORD (CONSOLIDATED)
# =========================
# 🔒 FIX: Consolidated to use direct bcrypt (same as security.py)
# This ensures consistency across all auth endpoints
def hash_password(password: str) -> str:
    """Hash password with bcrypt directly (no SHA-256 pre-hashing)"""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash"""
    return pwd_context.verify(password, hashed_password)

