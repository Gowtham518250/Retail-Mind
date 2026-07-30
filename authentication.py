# 🔒 SECURITY FIX: Consolidated auth module
# This module now delegates to security.py to prevent drift and ensure consistency
# Import from security.py for all auth functions
from security import (
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    hash_password,
    verify_password,
    create_access_token_simple as create_access_token
)

# Re-export for backward compatibility
__all__ = [
    'SECRET_KEY',
    'ALGORITHM', 
    'ACCESS_TOKEN_EXPIRE_MINUTES',
    'hash_password',
    'verify_password',
    'create_access_token'
]

