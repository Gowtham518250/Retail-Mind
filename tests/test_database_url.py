from urllib.parse import urlparse

from db import normalize_database_url


def test_render_host_is_normalized_with_sslmode():
    original = "postgresql://user:pass@dpg-d8pnbg4m0tmc73b2ff7g-a/retail_mind_xxog"

    normalized = normalize_database_url(original)
    parsed = urlparse(normalized)

    assert parsed.scheme == "postgresql"
    assert parsed.hostname == "dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com"
    assert "sslmode=require" in parsed.query
