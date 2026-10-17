import logging

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from performance_middleware import PerformanceMiddleware


async def api_response(request):
    return JSONResponse({"ok": True})


async def static_response(request):
    return Response("console.log('ok')", media_type="application/javascript")


async def streamed_response(request):
    async def chunks():
        yield b"first-"
        yield b"second"

    return StreamingResponse(chunks(), media_type="text/plain")


async def failing_response(request):
    raise RuntimeError("intentional test exception")


def make_app(route_handlers):
    app = Starlette(routes=[Route(path, handler) for path, handler in route_handlers])
    app.add_middleware(
        PerformanceMiddleware,
        slow_threshold_ms=10_000,
        max_size_kb=1024,
    )
    return app


def test_api_response_contains_timing_size_and_no_cache_headers():
    app = make_app([("/api/records", api_response)])

    with TestClient(app) as client:
        response = client.get("/api/records")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["x-process-time"].endswith("ms")
    assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
    assert response.headers["x-response-size"].endswith("KB")


def test_static_assets_keep_public_cache_header():
    app = make_app([("/assets/app.js", static_response)])

    with TestClient(app) as client:
        response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert response.headers["x-process-time"].endswith("ms")


def test_streaming_response_is_not_buffered_and_body_is_preserved():
    app = make_app([("/download", streamed_response)])

    with TestClient(app) as client:
        response = client.get("/download")

    assert response.status_code == 200
    assert response.content == b"first-second"
    assert response.headers["x-process-time"].endswith("ms")
    # No Content-Length means the response-size header cannot be computed
    # correctly at response-start without buffering the stream.
    assert "x-response-size" not in response.headers


def test_downstream_exception_is_logged_with_request_context(caplog):
    app = make_app([("/api/fails", failing_response)])
    caplog.set_level(logging.ERROR, logger="performance_middleware")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/fails")

    assert response.status_code == 500
    assert any(
        "ASGI request failed: GET /api/fails" in record.getMessage()
        for record in caplog.records
    )
