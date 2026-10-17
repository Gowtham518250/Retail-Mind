"""Lightweight liveness and dependency readiness probes for deployment platforms."""
import logging
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])


def _check_database_ready() -> None:
    """Raise if the configured database cannot execute a minimal read query."""
    from db import engine

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


@router.get("/health/live")
def liveness():
    """Process liveness only; intentionally does not call external services."""
    return {"status": "alive", "timestamp": time.time()}


@router.get("/health/ready")
def readiness():
    """Readiness probe. Redis is intentionally optional because the app has a fallback."""
    try:
        _check_database_ready()
    except Exception as error:
        logger.warning(
            "Readiness database probe failed (error_type=%s)",
            type(error).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unreachable"},
        )

    return {
        "status": "ready",
        "database": "connected",
        "timestamp": time.time(),
    }
