"""
🚀 Performance Middleware for FastAPI Backend
Focuses on response compression, caching, and query optimization
"""

from fastapi import Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging
from typing import Callable
import json

logger = logging.getLogger(__name__)

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor API response times and log slow requests
    """
    
    def __init__(self, app, slow_threshold_ms: int = 500):
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms
    
    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = (time.time() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        # Log slow requests
        if process_time > self.slow_threshold_ms:
            logger.warning(f"⚠️ SLOW REQUEST: {request.method} {request.url.path} took {process_time:.2f}ms")
        
        return response


class CacheControlMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add cache control headers for static content
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        
        # Add cache headers for static assets
        if request.url.path.endswith(('.js', '.css', '.png', '.jpg', '.jpeg', '.svg', '.ico')):
            response.headers["Cache-Control"] = "public, max-age=86400"  # 1 day
        elif request.url.path.startswith('/api/'):
            # Don't cache API responses by default
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        
        return response


class ResponseSizeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor response sizes and log large responses
    """
    
    def __init__(self, app, max_size_kb: int = 1024):  # 1MB default
        super().__init__(app)
        self.max_size_kb = max_size_kb
    
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        
        # If response has body, check size
        if hasattr(response, 'body'):
            body_size = len(response.body) / 1024  # KB
            response.headers["X-Response-Size"] = f"{body_size:.2f}KB"
            
            if body_size > self.max_size_kb:
                logger.warning(f"⚠️ LARGE RESPONSE: {request.url.path} is {body_size:.2f}KB")
        
        return response


def setup_performance_middleware(app):
    """
    Setup all performance middleware in the correct order
    """
    # Add GZip compression first (outermost)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Add performance monitoring
    app.add_middleware(PerformanceMonitoringMiddleware, slow_threshold_ms=500)
    
    # Add cache control
    app.add_middleware(CacheControlMiddleware)
    
    # Add response size monitoring
    app.add_middleware(ResponseSizeMiddleware, max_size_kb=1024)
    
    logger.info("✅ Performance middleware setup complete")