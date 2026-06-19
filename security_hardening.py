"""
Security Hardening Service
Implements rate limiting, input sanitization, CSRF protection, SQL injection prevention, XSS protection.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, validator
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import re
import html
import logging
import hashlib

from db import get_db
from models import User

router = APIRouter(prefix="/api/security", tags=["security"])
logger = logging.getLogger(__name__)

# ==================== RATE LIMITING ====================

class RateLimiter:
    """In-memory rate limiter using sliding window algorithm"""
    
    def __init__(self):
        self.requests = defaultdict(list)
        self.max_requests = 100  # per minute
        self.window_seconds = 60
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed based on rate limit"""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ]
        
        # Check if under limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for client"""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ]
        
        return max(0, self.max_requests - len(self.requests[client_id]))

rate_limiter = RateLimiter()


# ==================== INPUT SANITIZATION ====================

class InputSanitizer:
    """Input sanitization to prevent SQL injection and XSS"""
    
    @staticmethod
    def sanitize_string(input_str: str) -> str:
        """Sanitize string input"""
        if not input_str:
            return ""
        
        # Remove potential SQL injection patterns
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|UNION|SCRIPT)\b)",
            r"(;|\-\-|\/\*|\*\/)",
            r"(\bOR\b|\bAND\b)\s*\d+\s*=\s*\d+",
            r"(\bWHERE\b\s*\d+\s*=\s*\d+)"
        ]
        
        sanitized = input_str
        for pattern in sql_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
        
        # HTML encode to prevent XSS
        sanitized = html.escape(sanitized)
        
        return sanitized
    
    @staticmethod
    def sanitize_email(email: str) -> str:
        """Sanitize email input"""
        if not email:
            return ""
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")
        
        return email.lower().strip()
    
    @staticmethod
    def sanitize_phone(phone: str) -> str:
        """Sanitize phone input"""
        if not phone:
            return ""
        
        # Remove all non-digit characters
        sanitized = re.sub(r'[^\d]', '', phone)
        
        # Validate length (10-15 digits)
        if len(sanitized) < 10 or len(sanitized) > 15:
            raise ValueError("Invalid phone number")
        
        return sanitized
    
    @staticmethod
    def sanitize_numeric(value: str, min_val: int = 0, max_val: int = 999999999) -> int:
        """Sanitize numeric input"""
        try:
            num = int(float(value))
            if num < min_val or num > max_val:
                raise ValueError(f"Value out of range [{min_val}, {max_val}]")
            return num
        except (ValueError, TypeError):
            raise ValueError("Invalid numeric value")

input_sanitizer = InputSanitizer()


# ==================== SECURITY MIDDLEWARE ====================

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    client_id = request.client.host if request.client else "unknown"
    
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(rate_limiter.max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(rate_limiter.window_seconds)
            }
        )
    
    response = await call_next(request)
    
    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.max_requests)
    response.headers["X-RateLimit-Remaining"] = str(rate_limiter.get_remaining(client_id))
    
    return response


# ==================== SECURITY ENDPOINTS ====================

class SecurityCheckRequest(BaseModel):
    """Request for security check"""
    input_data: str
    check_type: str  # 'sql_injection', 'xss', 'email', 'phone', 'numeric'


class SecurityCheckResponse(BaseModel):
    """Response from security check"""
    is_safe: bool
    sanitized_value: Optional[str] = None
    error_message: Optional[str] = None
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'


@router.post("/check-input", response_model=SecurityCheckResponse)
def check_input_security(request: SecurityCheckRequest):
    """
    Check input for security vulnerabilities.
    Returns sanitized value and risk assessment.
    """
    try:
        risk_level = "LOW"
        is_safe = True
        sanitized_value = None
        error_message = None
        
        try:
            if request.check_type == 'sql_injection':
                sanitized_value = input_sanitizer.sanitize_string(request.input_data)
                # Check for SQL patterns
                sql_patterns = [
                    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|UNION|SCRIPT)\b)",
                    r"(;|\-\-|\/\*|\*\/)"
                ]
                for pattern in sql_patterns:
                    if re.search(pattern, request.input_data, re.IGNORECASE):
                        risk_level = "HIGH"
                        is_safe = False
                        break
            
            elif request.check_type == 'xss':
                sanitized_value = input_sanitizer.sanitize_string(request.input_data)
                # Check for XSS patterns
                xss_patterns = [
                    r"<script.*?>.*?</script>",
                    r"javascript:",
                    r"on\w+\s*=",
                    r"<iframe"
                ]
                for pattern in xss_patterns:
                    if re.search(pattern, request.input_data, re.IGNORECASE):
                        risk_level = "HIGH"
                        is_safe = False
                        break
            
            elif request.check_type == 'email':
                sanitized_value = input_sanitizer.sanitize_email(request.input_data)
            
            elif request.check_type == 'phone':
                sanitized_value = input_sanitizer.sanitize_phone(request.input_data)
            
            elif request.check_type == 'numeric':
                sanitized_value = str(input_sanitizer.sanitize_numeric(request.input_data))
            
            else:
                error_message = "Unknown check type"
                is_safe = False
            
        except ValueError as e:
            error_message = str(e)
            is_safe = False
            risk_level = "MEDIUM"
        
        return SecurityCheckResponse(
            is_safe=is_safe,
            sanitized_value=sanitized_value,
            error_message=error_message,
            risk_level=risk_level
        )
        
    except Exception as e:
        logger.error(f"Security check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Security check failed"
        )


@router.get("/rate-limit-status")
def get_rate_limit_status(request: Request):
    """Get current rate limit status for client"""
    client_id = request.client.host if request.client else "unknown"
    
    return {
        "client_id": client_id,
        "max_requests": rate_limiter.max_requests,
        "remaining_requests": rate_limiter.get_remaining(client_id),
        "window_seconds": rate_limiter.window_seconds,
        "reset_in_seconds": rate_limiter.window_seconds
    }


@router.post("/validate-password")
def validate_password_strength(password: str):
    """
    Validate password strength according to security requirements.
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """
    try:
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters")
        
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        # Check for common passwords
        common_passwords = [
            "password", "12345678", "qwerty", "abc123", "password123",
            "admin", "welcome", "monkey", "dragon", "master"
        ]
        if password.lower() in common_passwords:
            errors.append("Password is too common")
        
        is_strong = len(errors) == 0
        
        return {
            "is_strong": is_strong,
            "errors": errors,
            "strength_score": max(0, 5 - len(errors))  # 0-5 score
        }
        
    except Exception as e:
        logger.error(f"Password validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password validation failed"
        )


@router.get("/security-headers")
def get_security_headers():
    """
    Get recommended security headers for the application.
    """
    return {
        "security_headers": {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        },
        "description": "These headers should be configured in your web server or reverse proxy"
    }


@router.post("/sanitize-batch")
def sanitize_batch_inputs(inputs: Dict[str, Any]):
    """
    Sanitize multiple inputs at once.
    Useful for form submissions with multiple fields.
    """
    try:
        sanitized = {}
        errors = []
        
        for field_name, field_value in inputs.items():
            try:
                if isinstance(field_value, str):
                    # Auto-detect type and sanitize
                    if '@' in field_value and '.' in field_value:
                        sanitized[field_name] = input_sanitizer.sanitize_email(field_value)
                    elif re.match(r'^[\d\s\-\+\(\)]+$', field_value):
                        sanitized[field_name] = input_sanitizer.sanitize_phone(field_value)
                    else:
                        sanitized[field_name] = input_sanitizer.sanitize_string(field_value)
                elif isinstance(field_value, (int, float)):
                    sanitized[field_name] = field_value
                else:
                    sanitized[field_name] = field_value
            except Exception as e:
                errors.append(f"{field_name}: {str(e)}")
                sanitized[field_name] = field_value  # Keep original if sanitization fails
        
        return {
            "success": len(errors) == 0,
            "sanitized": sanitized,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Batch sanitization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch sanitization failed"
        )


@router.get("/csrf-token")
def get_csrf_token():
    """
    Generate a CSRF token for form protection.
    In production, this should be stored in session and validated on form submission.
    """
    import secrets
    token = secrets.token_urlsafe(32)
    
    return {
        "csrf_token": token,
        "expires_in": 3600,  # 1 hour
        "usage": "Include this token in your forms as a hidden field and validate on submission"
    }


# ==================== DATABASE SECURITY ====================

@router.get("/check-sql-injection")
def check_sql_injection_pattern(query: str):
    """
    Check if a query contains SQL injection patterns.
    For educational and security testing purposes only.
    """
    try:
        dangerous_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|UNION|SCRIPT)\b)",
            r"(;|\-\-|\/\*|\*\/)",
            r"(\bOR\b|\bAND\b)\s*\d+\s*=\s*\d+",
            r"(\bWHERE\b\s*\d+\s*=\s*\d+)",
            r"(\'\s*OR\s*\'.*\')",
            r"(\"\s*OR\s*\".*\")"
        ]
        
        detected_patterns = []
        for pattern in dangerous_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches:
                detected_patterns.extend(matches)
        
        is_suspicious = len(detected_patterns) > 0
        
        return {
            "is_suspicious": is_suspicious,
            "detected_patterns": detected_patterns,
            "recommendation": "Use parameterized queries to prevent SQL injection"
        }
        
    except Exception as e:
        logger.error(f"SQL injection check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SQL injection check failed"
        )
