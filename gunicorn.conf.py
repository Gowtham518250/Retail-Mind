"""Gunicorn configuration for serving FastAPI under Render.

Keep WEB_CONCURRENCY=1 while scaling horizontally. Increasing processes creates
one SQLAlchemy pool and application/scheduler startup per process; measure RAM
and DB connection usage before raising it.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
worker_class = "uvicorn.workers.UvicornWorker"
workers = max(1, int(os.environ.get("WEB_CONCURRENCY", "1")))
timeout = max(30, int(os.environ.get("GUNICORN_TIMEOUT_SECONDS", "120")))
graceful_timeout = max(10, int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT_SECONDS", "30")))
keepalive = 5
preload_app = False
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
