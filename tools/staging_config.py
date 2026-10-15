"""Safety checks for any test helper that can mutate a deployed environment."""
from __future__ import annotations

from urllib.parse import urlparse


_BLOCKED_PRODUCTION_HOSTS = {
    "retail-mind-vkbp.onrender.com",
    "retail-mind-ikhi.onrender.com",
    "retail-mind-web.onrender.com",
}


def validate_staging_base_url(raw_url: str | None) -> str:
    """Validate a user-supplied staging URL; never accept known production hosts."""
    value = str(raw_url or "").strip().rstrip("/")
    if not value:
        raise ValueError("STAGING_BASE_URL is required.")
    parsed = urlparse(value)
    if not parsed.hostname:
        raise ValueError("STAGING_BASE_URL must be an absolute URL with a hostname.")
    if parsed.username or parsed.password:
        raise ValueError("Do not put credentials in STAGING_BASE_URL.")
    if parsed.query or parsed.fragment:
        raise ValueError("STAGING_BASE_URL must not contain a query string or fragment.")

    host = parsed.hostname.casefold().rstrip(".")
    if host in _BLOCKED_PRODUCTION_HOSTS:
        raise ValueError(
            "Refusing to run staging tests against a known production Retail Mind host."
        )
    if parsed.scheme != "https" and host not in {"localhost", "127.0.0.1"}:
        raise ValueError("STAGING_BASE_URL must use HTTPS; HTTP is only allowed for localhost.")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("STAGING_BASE_URL must use HTTP or HTTPS.")
    return value
