import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import redis

logger = logging.getLogger("retail_mind.rate_limiter")

REDIS_URL = os.getenv("REDIS_URL")
REDIS_RETRY_INTERVAL_SECONDS = 30
try:
    REDIS_RETRY_INTERVAL_SECONDS = max(
        5, int(os.getenv("REDIS_RETRY_INTERVAL_SECONDS", "30"))
    )
except (TypeError, ValueError):
    logger.warning("Invalid REDIS_RETRY_INTERVAL_SECONDS; using 30 seconds")

USE_REDIS = False
redis_client = None
_next_redis_retry_at = 0.0
_redis_retry_lock = threading.Lock()

# Redis Lua makes the first request start the fixed window. A later request
# increments the counter without moving the expiry, so active traffic cannot
# keep a rate-limit key alive indefinitely.
_REDIS_FIXED_WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
return count
"""


def _new_redis_client():
    """Build a Redis client with bounded connection and read timeouts."""
    return redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _mark_redis_unavailable(error, operation: str) -> None:
    """Use local limits temporarily and retry Redis after a bounded delay."""
    global USE_REDIS, _next_redis_retry_at
    USE_REDIS = False
    _next_redis_retry_at = time.monotonic() + REDIS_RETRY_INTERVAL_SECONDS
    # Never log REDIS_URL or full connection exceptions: they may contain
    # credentials. The exception type is enough to diagnose fallback mode.
    logger.warning(
        "Redis %s unavailable; using in-memory rate limiting (error_type=%s)",
        operation,
        type(error).__name__,
    )


def _redis_available() -> bool:
    """Return whether Redis is ready, retrying after transient startup failures."""
    global USE_REDIS, redis_client, _next_redis_retry_at
    if not REDIS_URL or not REDIS_URL.strip():
        return False
    if USE_REDIS:
        return True
    if time.monotonic() < _next_redis_retry_at:
        return False

    # Avoid a connection storm when multiple requests arrive after an outage.
    if not _redis_retry_lock.acquire(blocking=False):
        return False
    try:
        if USE_REDIS:
            return True
        now = time.monotonic()
        if now < _next_redis_retry_at:
            return False
        _next_redis_retry_at = now + REDIS_RETRY_INTERVAL_SECONDS
        try:
            if redis_client is None:
                redis_client = _new_redis_client()
            redis_client.ping()
            USE_REDIS = True
            logger.info("Redis connected; distributed rate limiting is enabled")
            return True
        except Exception as error:
            _mark_redis_unavailable(error, "reconnect")
            return False
    finally:
        _redis_retry_lock.release()


# Probe once at startup. If DNS/Redis is temporarily unavailable, the first
# retry will happen after REDIS_RETRY_INTERVAL_SECONDS instead of disabling
# distributed rate limiting until the next process restart.
if REDIS_URL:
    try:
        redis_client = _new_redis_client()
        redis_client.ping()
        USE_REDIS = True
        logger.info("Redis connected; distributed rate limiting is enabled")
    except Exception as error:
        _mark_redis_unavailable(error, "startup")

class RateLimiter:
    """
    Distributed rate limiter for API endpoints using Redis when available
    Falls back to in-memory if Redis is not available
    Limits requests based on client IP and endpoint
    """
    
    def __init__(self):
        # Store request timestamps: {ip: {endpoint: [timestamp1, timestamp2, ...]}}
        self.requests = defaultdict(lambda: defaultdict(list))
        # Limits are defaults only. Endpoint decorators pass their explicit
        # per-route request/window limits to is_allowed().
        self.limits = {
            'login': 5,
            'register': 3,
            'forgot_password': 3,
            'default': 30,
        }
        self.window = 60
        self.endpoint_windows = defaultdict(lambda: self.window)
        self.redis_prefix = "rate_limit"
    
    def _get_redis_key(self, ip: str, endpoint: str) -> str:
        """Generate Redis key for rate limiting"""
        return f"{self.redis_prefix}:{ip}:{endpoint}"
    
    def is_allowed(
        self,
        ip: str,
        endpoint: str,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> tuple[bool, int]:
        """
        Check a request against the route's actual limit and window.
        Returns (allowed, remaining_requests). Explicit decorator settings take
        precedence over endpoint defaults.
        """
        # 🛡️ FIX: this method both reads USE_REDIS (below) and assigns to
        # it in the except block further down. Without declaring it global,
        # Python scopes USE_REDIS as local to this entire function (that's
        # how Python resolves scope -- based on whether a name is assigned
        # anywhere in the function body, not on runtime execution order),
        # so the read below always raised UnboundLocalError regardless of
        # the actual module-level value. This was crashing every single
        # rate-limited request in production, including login.
        global USE_REDIS
        now = time.time()
        route_limit = max_requests if max_requests is not None else self.limits.get(endpoint, self.limits['default'])
        route_window = max(1, int(window_seconds if window_seconds is not None else self.window))
        self.endpoint_windows[endpoint] = max(self.endpoint_windows[endpoint], route_window)
        
        # Prefer shared Redis counters, but keep serving requests if Redis is
        # unavailable. The Lua script increments and assigns expiry atomically.
        if _redis_available():
            try:
                key = self._get_redis_key(ip, endpoint)
                current_count = int(
                    redis_client.eval(
                        _REDIS_FIXED_WINDOW_SCRIPT, 1, key, route_window
                    )
                )
                if current_count <= route_limit:
                    return True, route_limit - current_count
                return False, 0
            except Exception as error:
                _mark_redis_unavailable(error, "request counter")
        
        # In-memory fallback
        timestamps = self.requests[ip][endpoint]
        
        # Remove timestamps outside this route's configured window.
        timestamps[:] = [t for t in timestamps if now - t < route_window]
        
        # Check if under the route's configured limit.
        if len(timestamps) < route_limit:
            timestamps.append(now)
            remaining = route_limit - len(timestamps)
            return True, remaining
        
        # Rate limit exceeded
        return False, 0
    
    def get_remaining_requests(self, ip: str, endpoint: str) -> int:
        """Get remaining requests for this IP and endpoint"""
        max_requests = self.limits.get(endpoint, self.limits['default'])
        
        # Read the shared counter whenever Redis is healthy. A connection
        # failure disables it temporarily and schedules a later retry.
        if _redis_available():
            try:
                key = self._get_redis_key(ip, endpoint)
                current_count = redis_client.get(key)
                if current_count:
                    return max(0, max_requests - int(current_count))
                return max_requests
            except Exception as error:
                _mark_redis_unavailable(error, "remaining-count lookup")
        
        # In-memory fallback
        now = time.time()
        timestamps = self.requests[ip][endpoint]
        
        # Count requests within window
        valid_timestamps = [t for t in timestamps if now - t < self.window]
        return max(0, max_requests - len(valid_timestamps))
    
    def cleanup_old_requests(self):
        """Clean up old request timestamps to prevent memory bloat"""
        # Redis handles TTL automatically, no cleanup needed
        if _redis_available():
            return
            
        # In-memory cleanup
        now = time.time()
        for ip in list(self.requests.keys()):
            for endpoint in list(self.requests[ip].keys()):
                timestamps = self.requests[ip][endpoint]
                window = self.endpoint_windows[endpoint]
                timestamps[:] = [t for t in timestamps if now - t < window]
                if not timestamps:
                    del self.requests[ip][endpoint]
            if not self.requests[ip]:
                del self.requests[ip]

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit_endpoint(
    max_requests: int | None = None,
    window_seconds: int | None = None,
):
    """
    Decorator for rate limiting API endpoints
    Works with both sync and async functions
    Usage:
        @rate_limit_endpoint(max_requests=5, window_seconds=60)
        async def login_endpoint(request: Request):
            ...
    """
    def decorator(func):
        def _extract_request(args, kwargs) -> Request:
            # 🛡️ FIX: previously both wrappers below declared `request:
            # Request` as their own first positional parameter, then called
            # `func(request, *args, **kwargs)` -- reinjecting it
            # positionally. That's only safe if the wrapped endpoint's own
            # first parameter is also `request`. FastAPI actually calls the
            # wrapper with resolved parameters as keyword arguments matching
            # the ENDPOINT's real signature (e.g. login(user, request, db)
            # gets called as wrapper(user=..., request=..., db=...)), so for
            # any endpoint where `request` isn't first (like login, where
            # `user` is), the positional reinjection collided with the
            # wrapped function's own first parameter -- "got multiple values
            # for argument 'user'" in production. Look up `request` by
            # keyword first (matches how FastAPI actually calls this), fall
            # back to scanning positional args for a Request instance.
            if 'request' in kwargs:
                return kwargs['request']
            for a in args:
                if isinstance(a, Request):
                    return a
            raise TypeError(
                "rate_limit_endpoint could not find a 'request: Request' "
                "parameter on the wrapped endpoint"
            )

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request = _extract_request(args, kwargs)
            # Get client IP
            ip = request.client.host if request.client else "unknown"
            endpoint = request.url.path.split('/')[-1] or "default"
            
            # Use the configured per-route limit/window; resolve defaults only
            # when the decorator did not provide an explicit value.
            resolved_limit = (
                max_requests
                if max_requests is not None
                else rate_limiter.limits.get(endpoint, rate_limiter.limits["default"])
            )
            resolved_window = window_seconds if window_seconds is not None else rate_limiter.window
            allowed, remaining = rate_limiter.is_allowed(
                ip, endpoint, resolved_limit, resolved_window
            )

            headers = {
                "X-RateLimit-Limit": str(resolved_limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time()) + resolved_window),
            }
            
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too many requests", "message": f"Rate limit exceeded. Try again in {resolved_window} seconds."},
                    headers=headers
                )
            
            # Clean up old requests periodically
            if int(time.time()) % 300 == 0:  # Every 5 minutes
                rate_limiter.cleanup_old_requests()
            
            # Call the wrapped function with the exact args/kwargs FastAPI
            # gave us -- no repositioning.
            response = await func(*args, **kwargs)
            
            # Add rate limit headers to response
            if hasattr(response, 'headers'):
                response.headers.update(headers)
            
            return response
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            request = _extract_request(args, kwargs)
            # Get client IP
            ip = request.client.host if request.client else "unknown"
            endpoint = request.url.path.split('/')[-1] or "default"
            
            # Use the configured per-route limit/window; resolve defaults only
            # when the decorator did not provide an explicit value.
            resolved_limit = (
                max_requests
                if max_requests is not None
                else rate_limiter.limits.get(endpoint, rate_limiter.limits["default"])
            )
            resolved_window = window_seconds if window_seconds is not None else rate_limiter.window
            allowed, remaining = rate_limiter.is_allowed(
                ip, endpoint, resolved_limit, resolved_window
            )

            headers = {
                "X-RateLimit-Limit": str(resolved_limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time()) + resolved_window),
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
            response = func(*args, **kwargs)
            
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