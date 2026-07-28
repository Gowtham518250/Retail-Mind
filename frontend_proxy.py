"""
Reverse proxy from the FastAPI backend to the frontend-web Next.js server.

Why this exists: the customer wants ONE public domain (retail-mind-vkbp.onrender.com)
serving both the API and the storefront UI. Next.js runs as its own server
process (needed for on-demand rendering of arbitrary shop IDs — see
frontend-web/next.config.mjs for why a static export doesn't work here).
Render doesn't support two independently-deployed services sharing one exact
domain natively, so the FastAPI app — which already owns the public domain —
proxies frontend-facing requests through to the internal Next.js service.

Configure via env var:
  FRONTEND_ORIGIN = internal URL of the frontend-web Render service,
                     e.g. http://retail-mind-web:10000 (Render private
                     networking) or its public onrender.com URL as a fallback.
"""
import os
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")

router = APIRouter()

# Headers that must never be forwarded as-is between hops (hop-by-hop headers).
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-encoding", "content-length",
}


async def _proxy(request: Request, path: str) -> Response:
    if not FRONTEND_ORIGIN:
        return Response(
            content=(
                "<h1>Storefront is not configured.</h1>"
                "<p>Set the FRONTEND_ORIGIN environment variable to the "
                "frontend-web service URL.</p>"
            ),
            status_code=503,
            media_type="text/html",
        )

    target_url = f"{FRONTEND_ORIGIN}/{path}"
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", *_HOP_BY_HOP)
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            upstream = await client.request(
                request.method,
                target_url,
                params=request.query_params,
                headers=forward_headers,
                content=await request.body(),
                follow_redirects=False,
            )
        except httpx.RequestError:
            return Response(
                content="<h1>Storefront is temporarily unavailable.</h1>",
                status_code=502,
                media_type="text/html",
            )

    response_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )


# Next.js build assets — must be proxied exactly as-is (JS/CSS chunks).
@router.get("/_next/{path:path}", tags=["Storefront Proxy"], include_in_schema=False)
async def proxy_next_assets(request: Request, path: str):
    return await _proxy(request, f"_next/{path}")


# The customer storefront — any shop ID, any sub-page (checkout, product, etc).
@router.get("/shop/{path:path}", tags=["Storefront Proxy"], include_in_schema=False)
async def proxy_shop(request: Request, path: str):
    return await _proxy(request, f"shop/{path}")


# Customer account pages served by the same Next.js app.
@router.get("/auth", tags=["Storefront Proxy"], include_in_schema=False)
async def proxy_auth(request: Request):
    return await _proxy(request, "auth")


@router.get("/orders", tags=["Storefront Proxy"], include_in_schema=False)
async def proxy_orders(request: Request):
    return await _proxy(request, "orders")


@router.get("/profile", tags=["Storefront Proxy"], include_in_schema=False)
async def proxy_profile(request: Request):
    return await _proxy(request, "profile")


# PWA / static assets served from frontend-web/public.
@router.get("/manifest.json", tags=["Storefront Proxy"], include_in_schema=False)
async def proxy_manifest(request: Request):
    return await _proxy(request, "manifest.json")


@router.get("/sw.js", tags=["Storefront Proxy"], include_in_schema=False)
async def proxy_service_worker(request: Request):
    return await _proxy(request, "sw.js")
