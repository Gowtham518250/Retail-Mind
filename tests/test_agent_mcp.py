import asyncio

import pytest

from agentic import mcp_server as mcp_module


async def _invoke_middleware(middleware, headers=(), inner_callback=None):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    async def inner(scope, receive, send):
        if inner_callback is not None:
            await inner_callback()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware.app = inner
    scope = {"type": "http", "headers": list(headers), "method": "POST", "path": "/mcp/"}
    await middleware(scope, receive, send)
    start = next(message for message in sent if message["type"] == "http.response.start")
    return start["status"]


def test_mcp_requires_both_agent_and_mcp_feature_flags(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_MCP_ENABLED", "true")
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "false")
    assert mcp_module._enabled() is False

    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "true")
    assert mcp_module._enabled() is True


def test_mcp_mount_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RETAIL_MIND_MCP_ENABLED", raising=False)
    monkeypatch.delenv("RETAIL_MIND_AGENT_ENABLED", raising=False)

    class API:
        mounted = False

        def mount(self, path, app):
            self.mounted = True

    api = API()
    assert mcp_module.mount_mcp_server(api) is False
    assert api.mounted is False


def test_mcp_requires_explicit_host_and_origin_allowlists(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_MCP_ENABLED", "true")
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "true")
    monkeypatch.delenv("RETAIL_MIND_MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("RETAIL_MIND_MCP_ALLOWED_ORIGINS", raising=False)

    class API:
        def mount(self, path, app):
            raise AssertionError("MCP must not mount without explicit allowlists")

    with pytest.raises(RuntimeError, match="ALLOWED_HOSTS"):
        mcp_module.mount_mcp_server(API())


def test_mcp_rejects_missing_bearer_token():
    middleware = mcp_module.RetailMindOwnerJWTMiddleware(lambda *_: None)
    status = asyncio.run(_invoke_middleware(middleware))
    assert status == 401


def test_mcp_rejects_customer_role(monkeypatch):
    monkeypatch.setattr(mcp_module, "decode_token", lambda token: {"sub": "7", "role": "CUSTOMER"})
    middleware = mcp_module.RetailMindOwnerJWTMiddleware(lambda *_: None)
    status = asyncio.run(
        _invoke_middleware(
            middleware,
            headers=[(b"authorization", b"Bearer customer-access-token")],
        )
    )
    assert status == 403


def test_mcp_rejects_refresh_token(monkeypatch):
    monkeypatch.setattr(
        mcp_module,
        "decode_token",
        lambda token: {"sub": "7", "role": "OWNER", "type": "refresh"},
    )
    middleware = mcp_module.RetailMindOwnerJWTMiddleware(lambda *_: None)
    status = asyncio.run(
        _invoke_middleware(
            middleware,
            headers=[(b"authorization", b"Bearer refresh-token")],
        )
    )
    assert status == 401


def test_mcp_scopes_owner_request_to_authenticated_shop(monkeypatch):
    monkeypatch.setattr(
        mcp_module,
        "decode_token",
        lambda token: {"sub": "19", "role": "OWNER", "type": "access"},
    )
    observed = []

    async def inside_request():
        observed.append(mcp_module._current_shop())

    middleware = mcp_module.RetailMindOwnerJWTMiddleware(lambda *_: None)
    status = asyncio.run(
        _invoke_middleware(
            middleware,
            headers=[(b"authorization", b"Bearer owner-access-token")],
            inner_callback=inside_request,
        )
    )
    assert status == 204
    assert observed == [19]
    with pytest.raises(PermissionError):
        mcp_module._current_shop()

def test_mcp_exposes_attendance_preview_but_never_confirmation_tool():
    assert hasattr(mcp_module, "prepare_attendance_record")
    assert not hasattr(mcp_module, "confirm_attendance_record")
