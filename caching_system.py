"""
Caching System for Performance
Redis-based caching with TTL, invalidation, and cache warming
"""

import redis
import json
import os
from datetime import timedelta
from typing import Optional, Any, List
from functools import wraps
import hashlib
import pickle
import logging
import threading
import time
from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)

from security import get_current_user
from db import get_db
from sqlalchemy.orm import Session


class CacheManager:
    """Redis cache with bounded connection retries and safe local fallback."""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "").strip()
        self.redis_client = None
        self.enabled = False
        self.prefix = "app_cache:"
        self.retry_interval_seconds = 30
        try:
            self.retry_interval_seconds = max(
                5, int(os.getenv("REDIS_RETRY_INTERVAL_SECONDS", "30"))
            )
        except (TypeError, ValueError):
            logger.warning("Invalid REDIS_RETRY_INTERVAL_SECONDS for cache; using 30 seconds")
        self._retry_after = 0.0
        self._connection_lock = threading.Lock()
        # Verify connectivity at startup. Failure disables cache use temporarily
        # instead of allowing every request to repeatedly hit a broken endpoint.
        self._ensure_available()

    def _build_client(self):
        if not self.redis_url:
            return None
        return redis.from_url(
            self.redis_url,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    def _mark_unavailable(self, error, operation: str) -> None:
        self.enabled = False
        self._retry_after = time.monotonic() + self.retry_interval_seconds
        # Never include the URL or exception message: either may reveal details.
        logger.warning(
            "Redis cache %s unavailable; bypassing cache "
            "(error_type=%s, reason=%s)",
            operation,
            type(error).__name__,
            _redis_failure_reason(error),
        )

    def _ensure_available(self) -> bool:
        if not self.redis_url:
            return False
        if self.enabled and self.redis_client is not None:
            return True
        now = time.monotonic()
        if now < self._retry_after or not self._connection_lock.acquire(blocking=False):
            return False
        try:
            if self.enabled and self.redis_client is not None:
                return True
            if self.redis_client is None:
                self.redis_client = self._build_client()
            if self.redis_client is None:
                return False
            self.redis_client.ping()
            was_enabled = self.enabled
            self.enabled = True
            self._retry_after = 0.0
            if not was_enabled:
                logger.info("Redis cache connected and enabled")
            return True
        except Exception as error:
            self._mark_unavailable(error, "connection")
            return False
        finally:
            self._connection_lock.release()

    def _mark_operation_failure(self, error, operation: str) -> None:
        self._mark_unavailable(error, operation)

    def _get_key(self, key: str) -> str:
        """Generate cache key with prefix."""
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Return cached data, or None when cache is unavailable or misses."""
        if not self._ensure_available():
            return None
        try:
            value = self.redis_client.get(self._get_key(key))
            if value is None:
                return None
            try:
                return json.loads(value)
            except (ValueError, TypeError, UnicodeDecodeError):
                return pickle.loads(value)
        except Exception as error:
            self._mark_operation_failure(error, "get")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Cache data with a finite TTL. Cache errors never fail business requests."""
        if not self._ensure_available():
            return False
        try:
            try:
                serialized = json.dumps(value)
            except (TypeError, ValueError):
                serialized = pickle.dumps(value)
            self.redis_client.setex(self._get_key(key), max(1, int(ttl)), serialized)
            return True
        except Exception as error:
            self._mark_operation_failure(error, "set")
            return False

    def delete(self, key: str) -> bool:
        """Delete a single cache entry."""
        if not self._ensure_available():
            return False
        try:
            self.redis_client.delete(self._get_key(key))
            return True
        except Exception as error:
            self._mark_operation_failure(error, "delete")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete matching entries incrementally; avoid Redis' blocking KEYS command."""
        if not self._ensure_available():
            return 0
        deleted = 0
        batch = []
        try:
            for key in self.redis_client.scan_iter(
                match=f"{self.prefix}{pattern}*", count=500
            ):
                batch.append(key)
                if len(batch) >= 500:
                    deleted += int(self.redis_client.delete(*batch) or 0)
                    batch.clear()
            if batch:
                deleted += int(self.redis_client.delete(*batch) or 0)
            return deleted
        except Exception as error:
            self._mark_operation_failure(error, "pattern delete")
            return deleted

    def clear_all(self) -> bool:
        """Clear application cache keys using an incremental scan."""
        if not self._ensure_available():
            return False
        self.delete_pattern("")
        # delete_pattern returns a count for callers, while clear_all's public
        # contract is boolean. Its failure path disables the cache manager.
        return self.enabled

    def get_stats(self) -> dict:
        """Return cache stats without allocating a full key list."""
        if not self._ensure_available():
            return {}
        try:
            info = self.redis_client.info()
            total_keys = sum(
                1 for _ in self.redis_client.scan_iter(
                    match=f"{self.prefix}*", count=500
                )
            )
            return {
                "total_keys": total_keys,
                "memory_used_mb": info.get("used_memory_mb", 0),
                "connected_clients": info.get("connected_clients", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
            }
        except Exception as error:
            self._mark_operation_failure(error, "stats")
            return {}


cache_manager = CacheManager()


def cache_result(ttl: int = 3600, key_prefix: str = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = key_prefix or func.__name__
            args_str = str(args) + str(kwargs)
            args_hash = hashlib.md5(args_str.encode()).hexdigest()
            cache_key = f"{func_name}:{args_hash}"
            cached = cache_manager.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cache set: {cache_key}")
            return result
        return wrapper
    return decorator


def cache_invalidate(*patterns):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            for pattern in patterns:
                count = cache_manager.delete_pattern(pattern)
                logger.debug(f"Invalidated {count} cache entries: {pattern}")
            return result
        return wrapper
    return decorator


class CacheWarmer:
    """Cache warming strategies for frequently accessed data"""
    
    @staticmethod
    def warm_product_cache(db):
        """Pre-load product data into cache"""
        from models import Product
        try:
            products = db.query(Product).limit(1000).all()
            for product in products:
                cache_key = f"product:{product.id}"
                cache_manager.set(
                    cache_key,
                    {
                        "id": product.id,
                        "name": product.product_name,
                        "sku": product.sku,
                        "stock": product.current_stock,
                        "price": float(product.unit_price)
                    },
                    ttl=86400
                )
            logger.info(f"Warmed cache with {len(products)} products")
            return len(products)
        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            return 0
    
    @staticmethod
    def warm_analytics_cache(db):
        """Pre-calculate and cache analytics"""
        from models import sales
        from sqlalchemy import func
        try:
            today_sales = db.query(func.sum(sales.total)).filter(
                sales.sale_date == func.current_date()
            ).scalar() or 0
            cache_manager.set("analytics:today_sales", float(today_sales), ttl=3600)
            monthly_sales = db.query(func.sum(sales.total)).scalar() or 0
            cache_manager.set("analytics:monthly_sales", float(monthly_sales), ttl=86400)
            logger.info("Analytics cache warmed")
            return True
        except Exception as e:
            logger.error(f"Analytics cache warming failed: {e}")
            return False


router = APIRouter(prefix="/api/cache", tags=["Cache Management"])


@router.get("/stats")
async def get_cache_stats(current_user_id: int = Depends(get_current_user)):
    """Get cache statistics (requires authentication)."""
    return cache_manager.get_stats()


@router.post("/warm/products")
async def warm_product_cache(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user),
):
    """Pre-warm product cache (requires authentication)."""
    count = CacheWarmer.warm_product_cache(db)
    return {"status": "success", "products_cached": count}


@router.post("/warm/analytics")
async def warm_analytics_cache(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user),
):
    """Pre-warm analytics cache (requires authentication)."""
    success = CacheWarmer.warm_analytics_cache(db)
    return {"status": "success" if success else "failed"}


@router.delete("/clear/{pattern}")
async def clear_cache_pattern(
    pattern: str,
    current_user_id: int = Depends(get_current_user)
):
    """Clear cache entries by pattern (requires authentication)"""
    count = cache_manager.delete_pattern(pattern)
    return {"status": "success", "cleared": count}


@router.delete("/clear-all")
async def clear_all_cache(
    current_user_id: int = Depends(get_current_user)
):
    """Clear entire cache (requires authentication)"""
    success = cache_manager.clear_all()
    return {"status": "success" if success else "failed"}


class CachedQueries:
    """Common cached database queries"""
    
    @staticmethod
    @cache_result(ttl=3600)
    def get_top_products(db, limit: int = 10):
        """Get top selling products (cached 1 hour)"""
        from models import Product
        return db.query(Product).limit(limit).all()
    
    @staticmethod
    @cache_result(ttl=86400)
    def get_categories(db):
        """Get unique product categories (cached 24 hours)"""
        from models import Product
        return db.query(Product.category).distinct().all()
    
    @staticmethod
    @cache_result(ttl=3600)
    def get_dashboard_summary(db):
        """Get dashboard summary data (cached 1 hour)"""
        from models import sales, Product
        from sqlalchemy import func
        return {
            "total_sales": float(db.query(func.sum(sales.total)).scalar() or 0),
            "total_products": db.query(Product).count(),
            "low_stock_count": db.query(Product).filter(
                Product.current_stock < Product.min_stock
            ).count()
        }
