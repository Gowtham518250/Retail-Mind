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

def test_neon_statement_timeout_is_set_after_connection_not_at_startup(monkeypatch):
    from db import _set_postgres_statement_timeout

    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "30000")

    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.closed = False

        def execute(self, statement, params):
            self.calls.append((statement, params))

        def close(self):
            self.closed = True

    class FakeConnection:
        def __init__(self):
            self.created_cursor = FakeCursor()

        def cursor(self):
            return self.created_cursor

    connection = FakeConnection()
    _set_postgres_statement_timeout(connection, None)

    assert connection.created_cursor.calls == [
        (
            "SELECT set_config('statement_timeout', %s, false)",
            ("30000ms",),
        )
    ]
    assert connection.created_cursor.closed is True


def test_neon_statement_timeout_can_be_disabled(monkeypatch):
    from db import _set_postgres_statement_timeout

    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "0")

    class FakeConnection:
        def cursor(self):
            raise AssertionError("No cursor should be opened when timeout is disabled")

    _set_postgres_statement_timeout(FakeConnection(), None)
\n