"""ASGI entrypoint used by Render's Gunicorn command.

Schema migrations run in Render's pre-deploy command. Because Gunicorn imports
this module directly (without entering app.py's FastAPI startup lifecycle),
start the auto-checkout reconciler explicitly here.
"""
import os
os.environ["RETAIL_MIND_BOOTSTRAP_COMPLETE"] = "1"

from production_boot import _patch_routes, _ensure_shift_table, _start_attendance_auto_checkout  # noqa: E402
from app import api as app  # noqa: E402

try:
    _ensure_shift_table()
    _start_attendance_auto_checkout()
except Exception:
    import logging
    logging.getLogger(__name__).exception("Attendance auto-checkout scheduler failed to initialize")

app = _patch_routes()
api = app
