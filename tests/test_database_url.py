from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from app import build_shop_frontend_redirect_url
from db import normalize_database_url


def test_requirements_include_gunicorn():
    requirements_path = Path(__file__).resolve().parents[1] / "requirements.txt"
    requirements_text = requirements_path.read_text(encoding="utf-8")

    assert "gunicorn" in requirements_text.lower()


def test_shop_redirect_uses_the_current_host_when_no_frontend_url_is_set(monkeypatch):
    monkeypatch.delenv("NEXTJS_FRONTEND_URL", raising=False)
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    request = SimpleNamespace(
        headers={"host": "retail-mind-vkbp.onrender.com"},
        url=SimpleNamespace(scheme="https"),
    )

    assert build_shop_frontend_redirect_url(request, "8") == "/?shop_id=8"


def test_render_host_is_normalized_with_sslmode():
    original = "postgresql://user:pass@dpg-d8pnbg4m0tmc73b2ff7g-a/retail_mind_xxog"

    normalized = normalize_database_url(original)
    parsed = urlparse(normalized)

    assert parsed.scheme == "postgresql"
    assert parsed.hostname == "dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com"
    assert "sslmode=require" in parsed.query
