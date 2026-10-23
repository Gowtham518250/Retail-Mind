"""ASGI entrypoint used by Render's Gunicorn command.

Database migrations and compatibility DDL run in Render's pre-deploy command.
Start the attendance reconciler here as a guarded fallback for this entrypoint.
"""
import os

os.environ["RETAIL_MIND_BOOTSTRAP_COMPLETE"] = "1"

from production_boot import _patch_routes, _start_attendance_auto_checkout  # noqa: E402
from app import api as app  # noqa: E402

try:
    # The startup hook may also request this; the helper is idempotent per process.
    _start_attendance_auto_checkout()
except Exception:
    import logging
    logging.getLogger(__name__).exception("Attendance auto-checkout scheduler failed to initialize")

app = _patch_routes()
api = app
