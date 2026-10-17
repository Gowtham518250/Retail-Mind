"""Build strict host/CORS allowlists that follow Render-assigned service URLs."""

from __future__ import annotations

from typing import Mapping
from urllib.parse import urlsplit


DEFAULT_ALLOWED_HOSTS = (
    "localhost",
    "127.0.0.1",
    "retail-mind-vkbp.onrender.com",
    "retail-mind-hpx3.onrender.com",
    "retail-mind-web.onrender.com",
)


def _hostname(value: str | None) -> str:
    """Extract a hostname from either a bare host or a URL."""
    candidate = (value or "").strip()
    if not candidate:
        return ""
    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    return (parsed.hostname or "").strip().lower().rstrip(".")


def build_allowed_hosts(env: Mapping[str, str]) -> list[str]:
    """Use configured hosts and always trust this service's Render hostname.

    ALLOWED_HOSTS may accidentally retain a previous onrender.com hostname when
    Render assigns a new service URL. RENDER_EXTERNAL_HOSTNAME is platform-set
    and is the authoritative hostname for the currently running web service.
    """
    configured = env.get("ALLOWED_HOSTS", "")
    source = configured.split(",") if configured.strip() else list(DEFAULT_ALLOWED_HOSTS)

    hosts: list[str] = []
    for value in source:
        host = _hostname(value)
        if host and host not in hosts:
            hosts.append(host)

    render_host = _hostname(env.get("RENDER_EXTERNAL_HOSTNAME"))
    if not render_host:
        render_host = _hostname(env.get("RENDER_EXTERNAL_URL"))
    if render_host and render_host not in hosts:
        hosts.append(render_host)

    return hosts


def build_allowed_origins(
    allowed_hosts: list[str],
    extra_origins: str = "",
) -> list[str]:
    """Build exact browser origins from the allowed hosts and extra origins."""
    origins: list[str] = []
    for host in allowed_hosts:
        if host in {"localhost", "127.0.0.1"}:
            candidates = [f"http://{host}:3000", f"http://{host}:8000"]
        else:
            candidates = [f"https://{host}", f"http://{host}"]
        for origin in candidates:
            if origin not in origins:
                origins.append(origin)

    for origin in extra_origins.split(","):
        origin = origin.strip()
        if origin and origin not in origins:
            origins.append(origin)

    return origins
