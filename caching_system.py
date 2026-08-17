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
from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)

from security import get_current_user


class CacheManager:
    """Redis-based cache manager"""
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.prefix = "app_cache:"
        self.enabled = False

        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=False)
            self.enabled = True
        except Exception as e:
            logger.warning(
                f"Redis initialization failed for REDIS_URL={redis_url}: {e}. "
                "Cache functionality is disabled until a valid Redis URL is provided."
            )
            self.redis_client = None
            self.enabled = False

    def _get_key(self, key: str) -> str:
        """Generate cache key with prefix"""
        return f"{self.prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled or self.redis_client is None:
            return None
        try:
            value = self.redis_client.get(self._get_key(key))
            if value:
                try:
                    return json.loads(value)
                except:
                    return pickle.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache"""
        if not self.enabled or self.redis_client is None:
            return False
        try:
            try:
                serialized = json.dumps(value)
            except:
                serialized = pickle.dumps(value)
            self.redis_client.setex(self._get_key(key), ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        if not self.enabled or self.redis_client is None:
            return False
        try:
            self.redis_client.delete(self._get_key(key))
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.enabled or self.redis_client is None:
            return 0
        try:
            keys = self.redis_client.keys(f"{self.prefix}{pattern}*")
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete_pattern error: {e}")
            return 0
    
    def clear_all(self) -> bool:
        """Clear all cache entries"""
        if not self.enabled or self.redis_client is None:
            return False
        try:
            keys = self.redis_client.keys(f"{self.prefix}*")
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            logger.warning(f"Cache clear_all error: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled or self.redis_client is None:
            return {}
        try:
            info = self.redis_client.info()
            keys = self.redis_client.keys(f"{self.prefix}*")
            return {
                "total_keys": len(keys),
                "memory_used_mb": info.get('used_memory_mb', 0),
                "connected_clients": info.get('connected_clients', 0),
                "hits": info.get('keyspace_hits', 0),
                "misses": info.get('keyspace_misses', 0),
            }
        except Exception as e:
            logger.warning(f"Cache stats error: {e}")
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


from db import get_db
from sqlalchemy.orm import Session

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
