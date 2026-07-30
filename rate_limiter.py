import time
import os
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import os

# 🔒 SECURITY FIX: Use Redis for distributed rate limiting in production
import os
import redis

global USE_REDIS

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise ValueError("Redis url not provided")


# Try to import Redis, fall back to in-memory if not available
try:

    redis_client=redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    # Test Redis connection
    redis_client.ping()
    USE_REDIS = True
    print("✅ Using Redis for distributed rate limiting")
except Exception as e:
    print(f"⚠️ Redis not available, falling back to in-memory rate limiting: {e}")
    USE_REDIS = False

class RateLimiter:
    """
    Distributed rate limiter for API endpoints using Redis when available
    Falls back to in-memory if Redis is not available
    Limits requests based on client IP and endpoint
    """
    
    def __init__(self):
        # Store request timestamps: {ip: {endpoint: [timestamp1, timestamp2, ...]}}
        self.requests = defaultdict(lambda: defaultdict(list))
        # Limits: {endpoint: max_requests_per_minute}
        self.limits = {
            'login': 5,           # 5 login attempts per minute
            'register': 3,        # 3 registration attempts per minute
            'forgot_password': 3, # 3 password reset attempts per minute
            'default': 30,        # 30 requests per minute for other endpoints
        }
        # Window size in seconds
        self.window = 60
        
        # Redis key prefix
        self.redis_prefix = "rate_limit"
    
    def _get_redis_key(self, ip: str, endpoint: str) -> str:
        """Generate Redis key for rate limiting"""
        return f"{self.redis_prefix}:{ip}:{endpoint}"
    
    def is_allowed(self, ip: str, endpoint: str) -> tuple[bool, int]:
        """
        Check if request is allowed based on rate limit
        Returns (allowed, remaining_requests)
        """
        now = time.time()
        max_requests = self.limits.get(endpoint, self.limits['default'])
        
        # Use Redis if available (distributed rate limiting)
        if USE_REDIS:
            try:
                key = self._get_redis_key(ip, endpoint)
                # Use Redis pipeline to get and increment atomically
                with redis_client.pipeline() as pipe:
                    # Get current count
                    pipe.multi()
                    pipe.incr(key)
                    pipe.expire(key, self.window)
                    results = pipe.execute()
                
                current_count = results[0]
                
                if current_count <= max_requests:
                    remaining = max_requests - current_count
                    return True, remaining
                else:
                    return False, 0
            except Exception as e:
                print(f"⚠️ Redis rate limiting failed, falling back to in-memory: {e}")
                # Fall back to in-memory
                USE_REDIS = False
        
        # In-memory fallback
        timestamps = self.requests[ip][endpoint]
        
        # Remove timestamps outside the window
        timestamps[:] = [t for t in timestamps if now - t < self.window]
        
        # Check if under limit
        if len(timestamps) < max_requests:
            timestamps.append(now)
            remaining = max_requests - len(timestamps)
            return True, remaining
        
        # Rate limit exceeded
        return False, 0
    
    def get_remaining_requests(self, ip: str, endpoint: str) -> int:
        """Get remaining requests for this IP and endpoint"""
        max_requests = self.limits.get(endpoint, self.limits['default'])
        
        # Use Redis if available
        if USE_REDIS:
            try:
                key = self._get_redis_key(ip, endpoint)
                current_count = redis_client.get(key)
                if current_count:
                    return max(0, max_requests - int(current_count))
                return max_requests
            except Exception:
                pass
        
        # In-memory fallback
        now = time.time()
        timestamps = self.requests[ip][endpoint]
        
        # Count requests within window
        valid_timestamps = [t for t in timestamps if now - t < self.window]
        return max(0, max_requests - len(valid_timestamps))
    
    def cleanup_old_requests(self):
        """Clean up old request timestamps to prevent memory bloat"""
        # Redis handles TTL automatically, no cleanup needed
        if USE_REDIS:
            return
            
        # In-memory cleanup
        now = time.time()
        for ip in list(self.requests.keys()):
            for endpoint in list(self.requests[ip].keys()):
                timestamps = self.requests[ip][endpoint]
                timestamps[:] = [t for t in timestamps if now - t < self.window]
                if not timestamps:
                    del self.requests[ip][endpoint]
            if not self.requests[ip]:
                del self.requests[ip]

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit_endpoint(max_requests: int = 30, window_seconds: int = 60):
    """
    Decorator for rate limiting API endpoints
    Works with both sync and async functions
    Usage:
        @rate_limit_endpoint(max_requests=5, window_seconds=60)
        async def login_endpoint(request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(request: Request, *args, **kwargs):
            # Get client IP
            ip = request.client.host if request.client else "unknown"
            endpoint = request.url.path.split('/')[-1] or "default"
            
            # Check rate limit
            allowed, remaining = rate_limiter.is_allowed(ip, endpoint)
            
            # Add rate limit headers
            headers = {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time()) + window_seconds),
            }
            
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too many requests", "message": f"Rate limit exceeded. Try again in {window_seconds} seconds."},
                    headers=headers
                )
            
            # Clean up old requests periodically
            if int(time.time()) % 300 == 0:  # Every 5 minutes
                rate_limiter.cleanup_old_requests()
            
            # Call the async function with headers
            response = await func(request, *args, **kwargs)
            
            # Add rate limit headers to response
            if hasattr(response, 'headers'):
                response.headers.update(headers)
            
            return response
        
        @wraps(func)
        def sync_wrapper(request: Request, *args, **kwargs):
            # Get client IP
            ip = request.client.host if request.client else "unknown"
            endpoint = request.url.path.split('/')[-1] or "default"
            
            # Check rate limit
            allowed, remaining = rate_limiter.is_allowed(ip, endpoint)
            
            # Add rate limit headers
            headers = {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time()) + window_seconds),
            }
            
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too many requests", "message": f"Rate limit exceeded. Try again in {window_seconds} seconds."},
                    headers=headers
                )
            
            # Clean up old requests periodically
            if int(time.time()) % 300 == 0:  # Every 5 minutes
                rate_limiter.cleanup_old_requests()
            
            # Call the sync function with headers
            response = func(request, *args, **kwargs)
            
            # Add rate limit headers to response
            if hasattr(response, 'headers'):
                response.headers.update(headers)
            
            return response
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    if request.client:
        return request.client.host
    elif request.headers.get("X-Forwarded-For"):
        # Handle proxy forwarding
        return request.headers.get("X-Forwarded-For").split(',')[0].strip()
    else:
        return "unknown"

class IPRateLimiter:
    """
    IP-based rate limiter for brute force protection
    Temporarily blocks IPs that exceed limits
    """
    
    def __init__(self):
        self.blocked_ips = {}  # {ip: blocked_until_timestamp}
        self.failed_attempts = defaultdict(int)  # {ip: failed_attempts}
        self.max_attempts = 5  # Max failed attempts before blocking
        self.block_duration = 300  # Block for 5 minutes
    
    def is_blocked(self, ip: str) -> bool:
        """Check if IP is currently blocked"""
        if ip in self.blocked_ips:
            if time.time() < self.blocked_ips[ip]:
                return True
            else:
                # Block duration expired
                del self.blocked_ips[ip]
                self.failed_attempts[ip] = 0
                return False
        return False
    
    def record_failure(self, ip: str):
        """Record a failed attempt and block if necessary"""
        self.failed_attempts[ip] += 1
        
        if self.failed_attempts[ip] >= self.max_attempts:
            # Block the IP
            self.blocked_ips[ip] = time.time() + self.block_duration
            return True
        return False
    
    def record_success(self, ip: str):
        """Record a successful attempt and reset counter"""
        if ip in self.failed_attempts:
            self.failed_attempts[ip] = 0

# Global IP rate limiter
ip_rate_limiter = IPRateLimiter()