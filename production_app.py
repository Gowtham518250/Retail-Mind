"""ASGI application entrypoint for Render's multi-instance web service.

Database migrations and legacy compatibility DDL are handled by predeploy_db.py
through Render's pre-deploy command. Importing this module must not run schema
mutations: every serving instance should only import and serve the prepared app.
"""
import os

# app.py contains a legacy development-only schema repair path. In this
# production entrypoint, schema preparation is the responsibility of the
# configured Render pre-deploy command.
os.environ["RETAIL_MIND_BOOTSTRAP_COMPLETE"] = "1"

from production_boot import _patch_routes  # noqa: E402

app = _patch_routes()
# Retain the alias used by older tooling and tests that refer to api.
api = app
