"""ASGI-native performance middleware for FastAPI.

Use a pure ASGI wrapper rather than BaseHTTPMiddleware. Stacked
BaseHTTPMiddleware.call_next layers can turn a downstream cancellation or an
early disconnect into repeated, context-free "No response returned" errors.
This middleware preserves streaming and logs the request context when the
downstream application raises.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from fastapi.middleware.gzip import GZipMiddleware

logger = logging.getLogger(__name__)

ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGIApp = Callable[[dict[str, Any], ASGIReceive, ASGISend], Awaitable[None]]


class PerformanceMiddleware:
    """Add response timing/cache headers and observe body sizes without buffering."""

    def __init__(
        self,
        app: ASGIApp,
        slow_threshold_ms: int = 500,
        max_size_kb: int = 1024,
    ) -> None:
        self.app = app
        self.slow_threshold_ms = slow_threshold_ms
        self.max_size_kb = max_size_kb

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        response_started = False
        response_completed = False
        status_code: int | None = None
        response_bytes = 0

        def replace_header(
            headers: list[tuple[bytes, bytes]],
            name: bytes,
            value: bytes,
        ) -> list[tuple[bytes, bytes]]:
            lower_name = name.lower()
            return [(key, val) for key, val in headers if key.lower() != lower_name] + [
                (name, value)
            ]

        async def send_with_metrics(message: dict[str, Any]) -> None:
            nonlocal response_started, response_completed, status_code, response_bytes

            message_type = message.get("type")
            if message_type == "http.response.start":
                response_started = True
                status_code = int(message.get("status", 0))
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                headers = list(message.get("headers", []))
                headers = replace_header(
                    headers, b"x-process-time", f"{elapsed_ms:.2f}ms".encode("ascii")
                )

                lowered_path = path.lower()
                if lowered_path.endswith(
                    (".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp")
                ):
                    headers = replace_header(
                        headers, b"cache-control", b"public, max-age=86400"
                    )
                elif path.startswith("/api/"):
                    headers = replace_header(
                        headers, b"cache-control", b"no-cache, no-store, must-revalidate"
                    )

                # A size response header is only accurate without buffering when
                # Content-Length is already known. Streaming bodies are measured
                # below and large streams are logged when the final chunk arrives.
                content_length = next(
                    (
                        value
                        for key, value in headers
                        if key.lower() == b"content-length"
                    ),
                    None,
                )
                if content_length is not None:
                    try:
                        size_kb = int(content_length) / 1024
                        headers = replace_header(
                            headers,
                            b"x-response-size",
                            f"{size_kb:.2f}KB".encode("ascii"),
                        )
                    except (TypeError, ValueError):
                        logger.debug(
                            "Ignoring invalid Content-Length for %s %s",
                            method,
                            path,
                        )

                message = {**message, "headers": headers}
                await send(message)
                return

            if message_type == "http.response.body":
                response_bytes += len(message.get("body", b""))
                await send(message)
                if not message.get("more_body", False):
                    response_completed = True
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    if elapsed_ms > self.slow_threshold_ms:
                        logger.warning(
                            "SLOW REQUEST: %s %s returned %s in %.2fms",
                            method,
                            path,
                            status_code,
                            elapsed_ms,
                        )
                    size_kb = response_bytes / 1024
                    if size_kb > self.max_size_kb:
                        logger.warning(
                            "LARGE RESPONSE: %s %s returned %.2fKB",
                            method,
                            path,
                            size_kb,
                        )
                return

            await send(message)

        try:
            await self.app(scope, receive, send_with_metrics)
        except Exception:
            # Preserve the original exception; do not replace the actual failure
            # with a generic middleware error or an unhelpful response-less trace.
            logger.exception(
                "ASGI request failed: %s %s (response_started=%s, completed=%s)",
                method,
                path,
                response_started,
                response_completed,
            )
            raise
        else:
            if not response_started:
                # An ASGI HTTP app should send http.response.start before returning.
                # This should be rare, but recording context is more useful than
                # silently allowing a client to wait for a response forever.
                logger.error(
                    "ASGI application returned without starting a response: %s %s",
                    method,
                    path,
                )


def setup_performance_middleware(app: Any) -> None:
    """Install one ASGI metrics layer and retain gzip compression."""
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(PerformanceMiddleware, slow_threshold_ms=500, max_size_kb=1024)
    logger.info("Performance middleware setup complete (ASGI-native)")
