import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import predeploy_db


ROOT = Path(__file__).resolve().parents[1]


def test_predeploy_refuses_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        predeploy_db.main()


def test_predeploy_runs_migrations_and_compatibility_steps_in_order(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://staging-test/db")
    steps = []

    fake_boot = SimpleNamespace(
        _run_database_migrations=lambda: steps.append("migrations"),
        _ensure_online_order_status_enum=lambda: steps.append("order_enum"),
        _ensure_sales_reference_order_id=lambda: steps.append("sales_order_id"),
        _ensure_online_delivery_payment_trigger=lambda: steps.append("payment_trigger"),
        _ensure_workers_table_schema=lambda: steps.append("workers_schema"),
        _ensure_shift_table=lambda: steps.append("shift_table"),
    )
    monkeypatch.setitem(sys.modules, "production_boot", fake_boot)

    predeploy_db.main()

    assert steps == [
        "migrations",
        "order_enum",
        "sales_order_id",
        "payment_trigger",
        "workers_schema",
        "shift_table",
    ]


def test_render_blueprint_pairs_predeploy_with_asgi_startup():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert 'preDeployCommand: "python predeploy_db.py"' in blueprint
    assert 'startCommand: "gunicorn --config gunicorn.conf.py production_app:app"' in blueprint
    assert "healthCheckPath: /health/ready" in blueprint


def test_pool_connection_ceiling_scales_by_instances_and_workers():
    from db_pool_config import estimated_connection_ceiling

    options = {"pool_size": 3, "max_overflow": 2}
    assert estimated_connection_ceiling(options, worker_count=1, instance_count=4) == 20
    assert estimated_connection_ceiling(options, worker_count=2, instance_count=4) == 40
