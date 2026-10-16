"""ASGI-native performance middleware for the Retail Mind API."""

import logging
import time
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


def _set_header(headers, name: bytes, value: bytes):
    name = name.lower()
    return [(k, v) for k, v in headers if k.lower() != name] + [(name, value)]


def _http(scope: Scope) -> bool:
    return scope.get("type") == "http"


class PerformanceMonitoringMiddleware:
    """Add elapsed time to response headers without BaseHTTPMiddleware."""

    def __init__(self, app: ASGIApp, slow_threshold_ms: int = 500):
        self.app = app
        self.slow_threshold_ms = slow_threshold_ms

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _http(scope):
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        method, path = scope.get("method", "UNKNOWN"), scope.get("path", "/")

        async def send_wrapper(message: Message):
            if message["type"] == "http.response.start":
                elapsed = (time.perf_counter() - started) * 1000
                message = dict(message)
                message["headers"] = _set_header(
                    list(message.get("headers", [])),
                    b"x-process-time",
                    f"{elapsed:.2f}ms".encode("ascii"),
                )
                if elapsed > self.slow_threshold_ms:
                    logger.warning("SLOW REQUEST: %s %s took %.2fms", method, path, elapsed)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class CacheControlMiddleware:
    """Set cache headers using response-start messages."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _http(scope):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")

        async def send_wrapper(message: Message):
            if message["type"] == "http.response.start":
                value = None
                if path.endswith((".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico")):
                    value = b"public, max-age=86400"
                elif path.startswith("/api/"):
                    value = b"no-cache, no-store, must-revalidate"
                if value is not None:
                    message = dict(message)
                    message["headers"] = _set_header(
                        list(message.get("headers", [])), b"cache-control", value
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)


class ResponseSizeMiddleware:
    """Expose known Content-Length and log large streamed or buffered bodies."""

    def __init__(self, app: ASGIApp, max_size_kb: int = 1024):
        self.app = app
        self.max_size_bytes = max_size_kb * 1024

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _http(scope):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        body_size = 0

        async def send_wrapper(message: Message):
            nonlocal body_size
            if message["type"] == "http.response.start":
                length = None
                for key, val in message.get("headers", []):
                    if key.lower() == b"content-length":
                        try:
                            length = int(val)
                        except (TypeError, ValueError):
                            pass
                        break
                if length is not None and length >= 0:
                    message = dict(message)
                    message["headers"] = _set_header(
                        list(message.get("headers", [])),
                        b"x-response-size",
                        f"{length / 1024:.2f}KB".encode("ascii"),
                    )
            elif message["type"] == "http.response.body":
                body_size += len(message.get("body", b""))
                final_chunk = not message.get("more_body", False)
                await send(message)
                if final_chunk and body_size > self.max_size_bytes:
                    logger.warning("LARGE RESPONSE: %s is %.2fKB", path, body_size / 1024)
                return
            await send(message)

        await self.app(scope, receive, send_wrapper)


def setup_performance_middleware(app) -> None:
    """Register ASGI middleware; Starlette makes the last-added middleware outermost."""
    from fastapi.middleware.gzip import GZipMiddleware

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(PerformanceMonitoringMiddleware, slow_threshold_ms=500)
    app.add_middleware(CacheControlMiddleware)
    app.add_middleware(ResponseSizeMiddleware, max_size_kb=1024)
    logger.info("Performance middleware setup complete")
