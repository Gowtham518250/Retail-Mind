import logging

import pytest

from performance_middleware import (
    CacheControlMiddleware,
    PerformanceMonitoringMiddleware,
    ResponseSizeMiddleware,
)


async def _run_asgi(app, path="/assets/app.js"):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
        "extensions": {},
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    return messages


def _response_headers(messages):
    start = next(message for message in messages if message["type"] == "http.response.start")
    return {key.lower(): value for key, value in start.get("headers", [])}


@pytest.mark.asyncio
async def test_asgi_middleware_adds_timing_cache_and_known_size(caplog):
    async def endpoint(scope, receive, send):
        body = b"x" * 2048
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain"), (b"content-length", b"2048")],
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})

    app = ResponseSizeMiddleware(
        CacheControlMiddleware(
            PerformanceMonitoringMiddleware(endpoint, slow_threshold_ms=10000)
        ),
        max_size_kb=1,
    )

    with caplog.at_level(logging.WARNING, logger="performance_middleware"):
        messages = await _run_asgi(app)

    headers = _response_headers(messages)
    assert headers[b"x-process-time"].endswith(b"ms")
    assert headers[b"cache-control"] == b"public, max-age=86400"
    assert headers[b"x-response-size"] == b"2.00KB"
    assert "LARGE RESPONSE: /assets/app.js is 2.00KB" in caplog.text


@pytest.mark.asyncio
async def test_api_response_gets_no_store_cache_control():
    async def endpoint(scope, receive, send):
        body = b"ok"
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-length", str(len(body)).encode("ascii"))],
        })
        await send({"type": "http.response.body", "body": body, "more_body": False})

    app = CacheControlMiddleware(endpoint)
    messages = await _run_asgi(app, path="/api/health")
    headers = _response_headers(messages)

    assert headers[b"cache-control"] == b"no-cache, no-store, must-revalidate"


@pytest.mark.asyncio
async def test_downstream_exception_is_preserved_not_replaced_by_no_response_error():
    async def endpoint(scope, receive, send):
        raise LookupError("original endpoint failure")

    app = ResponseSizeMiddleware(
        CacheControlMiddleware(PerformanceMonitoringMiddleware(endpoint))
    )

    with pytest.raises(LookupError, match="original endpoint failure"):
        await _run_asgi(app, path="/api/test")
