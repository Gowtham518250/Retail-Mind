from fastapi import FastAPI
from fastapi.testclient import TestClient

import health_routes


def make_client():
    app = FastAPI()
    app.include_router(health_routes.router)
    return TestClient(app)


def test_liveness_does_not_need_database(monkeypatch):
    def should_not_run():
        raise AssertionError("liveness must not contact the database")

    monkeypatch.setattr(health_routes, "_check_database_ready", should_not_run)
    response = make_client().get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_returns_200_when_database_check_succeeds(monkeypatch):
    monkeypatch.setattr(health_routes, "_check_database_ready", lambda: None)
    response = make_client().get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database"] == "connected"


def test_readiness_returns_503_without_leaking_exception(monkeypatch):
    def unavailable():
        raise RuntimeError("sensitive connection detail")

    monkeypatch.setattr(health_routes, "_check_database_ready", unavailable)
    response = make_client().get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unreachable"}
    assert "sensitive" not in response.text
