from fastapi import APIRouter
import socket
import os
import logging

router = APIRouter(prefix="/_debug", tags=["Debug"])
logger = logging.getLogger(__name__)


@router.get("/test-smtp-conn")
def test_smtp_conn():
    """Attempt a TCP connection to the SMTP server/port to verify outbound networking."""
    host = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    try:
        s = socket.create_connection((host, port), timeout=10)
        s.close()
        return {"ok": True, "host": host, "port": port}
    except Exception as e:
        logger.error("SMTP connectivity test failed: %s", e)
        return {"ok": False, "error": str(e)}
