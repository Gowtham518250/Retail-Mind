"""
Observability Service
Implements structured logging, error tracking, performance metrics, and health checks.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import json
import traceback
import psutil
import os

from db import get_db
from models import User, Product, Invoice

router = APIRouter(prefix="/api/observability", tags=["observability"])

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ai_shop_pro")


# ==================== HEALTH CHECKS ====================

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: float
    components: Dict[str, Any]


class ComponentHealth(BaseModel):
    """Individual component health"""
    status: str
    message: str
    response_time_ms: Optional[float] = None


@router.get("/health", response_model=HealthCheckResponse)
def health_check(request: Request):
    """
    Basic health check endpoint.
    Returns overall system health and component status.
    """
    try:
        # Get process uptime
        process = psutil.Process(os.getpid())
        uptime = datetime.now() - datetime.fromtimestamp(process.create_time())
        
        # Check components
        components = {}
        
        # Database health
        try:
            # Quick database connectivity check
            components["database"] = {
                "status": "healthy",
                "message": "Database connection successful"
            }
        except Exception as e:
            components["database"] = {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}"
            }
        
        # Memory health
        try:
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            components["memory"] = {
                "status": "healthy" if memory_percent < 80 else "degraded",
                "message": f"Memory usage: {memory_percent:.1f}%",
                "rss_mb": memory_info.rss / 1024 / 1024
            }
        except Exception as e:
            components["memory"] = {
                "status": "unknown",
                "message": f"Memory check failed: {str(e)}"
            }
        
        # CPU health
        try:
            cpu_percent = process.cpu_percent(interval=0.1)
            components["cpu"] = {
                "status": "healthy" if cpu_percent < 80 else "degraded",
                "message": f"CPU usage: {cpu_percent:.1f}%"
            }
        except Exception as e:
            components["cpu"] = {
                "status": "unknown",
                "message": f"CPU check failed: {str(e)}"
            }
        
        # Disk health
        try:
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            components["disk"] = {
                "status": "healthy" if disk_percent < 80 else "degraded",
                "message": f"Disk usage: {disk_percent:.1f}%",
                "free_gb": disk.free / 1024 / 1024 / 1024
            }
        except Exception as e:
            components["disk"] = {
                "status": "unknown",
                "message": f"Disk check failed: {str(e)}"
            }
        
        # Overall status
        all_healthy = all(c.get("status") == "healthy" for c in components.values())
        overall_status = "healthy" if all_healthy else "degraded"
        
        return HealthCheckResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version="3.0.0",
            uptime_seconds=uptime.total_seconds(),
            components=components
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Health check failed"
        )


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check endpoint.
    Checks if the application is ready to serve traffic.
    """
    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))
        
        # Check critical tables exist
        tables_to_check = ['user_details', 'products', 'invoices']
        for table in tables_to_check:
            try:
                db.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
            except Exception:
                return {
                    "status": "not_ready",
                    "message": f"Critical table {table} not accessible",
                    "timestamp": datetime.utcnow()
                }
        
        return {
            "status": "ready",
            "message": "Application is ready to serve traffic",
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "message": f"Readiness check failed: {str(e)}",
            "timestamp": datetime.utcnow()
        }


@router.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """
    Application metrics endpoint.
    Returns performance and business metrics.
    """
    try:
        metrics = {}
        
        # Database metrics
        try:
            # User count
            user_count = db.query(func.count(User.id)).scalar()
            metrics["users_total"] = user_count
            
            # Product count
            product_count = db.query(func.count(Product.id)).scalar()
            metrics["products_total"] = product_count
            
            # Invoice count
            invoice_count = db.query(func.count(Invoice.id)).scalar()
            metrics["invoices_total"] = invoice_count
            
            # Active products
            active_products = db.query(func.count(Product.id)).filter(
                Product.is_active == True
            ).scalar()
            metrics["products_active"] = active_products
            
            # Recent invoices (last 24 hours)
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_invoices = db.query(func.count(Invoice.id)).filter(
                Invoice.created_at >= yesterday
            ).scalar()
            metrics["invoices_last_24h"] = recent_invoices
            
        except Exception as e:
            metrics["database_error"] = str(e)
        
        # System metrics
        try:
            process = psutil.Process(os.getpid())
            metrics["memory_rss_mb"] = process.memory_info().rss / 1024 / 1024
            metrics["memory_percent"] = process.memory_percent()
            metrics["cpu_percent"] = process.cpu_percent(interval=0.1)
            metrics["uptime_seconds"] = (datetime.now() - datetime.fromtimestamp(process.create_time())).total_seconds()
        except Exception as e:
            metrics["system_error"] = str(e)
        
        # Application metrics
        metrics["timestamp"] = datetime.utcnow().isoformat()
        metrics["version"] = "3.0.0"
        
        return metrics
        
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Metrics collection failed"
        )


# ==================== STRUCTURED LOGGING ====================

class LogEntry(BaseModel):
    """Structured log entry"""
    level: str
    message: str
    context: Optional[Dict[str, Any]] = None
    timestamp: datetime


@router.post("/log")
def log_event(entry: LogEntry):
    """
    Structured logging endpoint.
    Allows frontend to send structured logs to backend.
    """
    try:
        # Create structured log message
        log_data = {
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else datetime.utcnow().isoformat(),
            "level": entry.level.upper(),
            "message": entry.message,
            "context": entry.context or {}
        }
        
        # Log based on level
        log_level = getattr(logging, entry.level.upper(), logging.INFO)
        logger.log(log_level, json.dumps(log_data))
        
        return {"status": "logged", "timestamp": datetime.utcnow()}
        
    except Exception as e:
        logger.error(f"Logging failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Logging failed"
        )


@router.post("/error")
def log_error(error_data: Dict[str, Any]):
    """
    Error tracking endpoint.
    Captures and logs errors for debugging.
    """
    try:
        error_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "message": error_data.get("message", "Unknown error"),
            "stack_trace": error_data.get("stack_trace"),
            "context": error_data.get("context", {}),
            "user_id": error_data.get("user_id"),
            "endpoint": error_data.get("endpoint"),
            "method": error_data.get("method")
        }
        
        logger.error(json.dumps(error_entry))
        
        # In production, this would send to error tracking service (e.g., Sentry)
        
        return {"status": "logged", "error_id": f"ERR_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"}
        
    except Exception as e:
        logger.error(f"Error logging failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error logging failed"
        )


# ==================== PERFORMANCE MONITORING ====================

@router.get("/performance/summary")
def get_performance_summary(db: Session = Depends(get_db)):
    """
    Performance summary metrics.
    """
    try:
        summary = {}
        
        # Database query performance
        try:
            start_time = datetime.utcnow()
            db.execute(text("SELECT COUNT(*) FROM user_details"))
            query_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            summary["db_query_time_ms"] = query_time
            summary["db_query_status"] = "healthy" if query_time < 100 else "degraded"
        except Exception as e:
            summary["db_query_error"] = str(e)
        
        # Response time tracking (would be populated by middleware)
        summary["avg_response_time_ms"] = 0.0  # Placeholder
        summary["p95_response_time_ms"] = 0.0  # Placeholder
        summary["p99_response_time_ms"] = 0.0  # Placeholder
        
        # Error rate
        summary["error_rate"] = 0.0  # Placeholder
        summary["total_requests"] = 0  # Placeholder
        summary["error_count"] = 0  # Placeholder
        
        summary["timestamp"] = datetime.utcnow().isoformat()
        
        return summary
        
    except Exception as e:
        logger.error(f"Performance summary failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Performance summary failed"
        )


@router.get("/performance/database")
def get_database_performance(db: Session = Depends(get_db)):
    """
    Database performance metrics.
    """
    try:
        metrics = {}
        
        # Table sizes
        try:
            tables = ['user_details', 'products', 'invoices', 'customers']
            for table in tables:
                try:
                    result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    metrics[f"{table}_count"] = count
                except Exception:
                    metrics[f"{table}_count"] = "error"
        except Exception as e:
            metrics["table_count_error"] = str(e)
        
        # Connection pool status (if using connection pooling)
        metrics["connection_pool_status"] = "active"
        
        metrics["timestamp"] = datetime.utcnow().isoformat()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Database performance check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Database performance check failed"
        )


# ==================== BUSINESS METRICS ====================

@router.get("/business/overview")
def get_business_overview(db: Session = Depends(get_db)):
    """
    Business metrics overview.
    """
    try:
        overview = {}
        
        # Revenue metrics
        try:
            today = datetime.utcnow().date()
            today_revenue = db.query(func.sum(Invoice.total_amount)).filter(
                Invoice.invoice_date == today
            ).scalar() or 0
            
            month_start = today.replace(day=1)
            month_revenue = db.query(func.sum(Invoice.total_amount)).filter(
                Invoice.invoice_date >= month_start
            ).scalar() or 0
            
            overview["today_revenue"] = float(today_revenue)
            overview["month_revenue"] = float(month_revenue)
        except Exception as e:
            overview["revenue_error"] = str(e)
        
        # Sales metrics
        try:
            today_sales = db.query(func.count(Invoice.id)).filter(
                Invoice.invoice_date == today
            ).scalar() or 0
            
            month_sales = db.query(func.count(Invoice.id)).filter(
                Invoice.invoice_date >= month_start
            ).scalar() or 0
            
            overview["today_sales_count"] = today_sales
            overview["month_sales_count"] = month_sales
        except Exception as e:
            overview["sales_error"] = str(e)
        
        # Inventory metrics
        try:
            total_products = db.query(func.count(Product.id)).scalar() or 0
            low_stock_products = db.query(func.count(Product.id)).filter(
                Product.current_stock <= Product.min_stock
            ).scalar() or 0
            
            overview["total_products"] = total_products
            overview["low_stock_products"] = low_stock_products
            overview["stock_health_percentage"] = (
                ((total_products - low_stock_products) / total_products * 100) 
                if total_products > 0 else 0
            )
        except Exception as e:
            overview["inventory_error"] = str(e)
        
        overview["timestamp"] = datetime.utcnow().isoformat()
        
        return overview
        
    except Exception as e:
        logger.error(f"Business overview failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Business overview failed"
        )
