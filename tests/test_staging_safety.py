import pytest

from tools.staging_config import validate_staging_base_url


@pytest.mark.parametrize(
    "url",
    [
        "https://retail-mind-vkbp.onrender.com",
        "https://retail-mind-ikhi.onrender.com",
        "https://retail-mind-web.onrender.com",
    ],
)
def test_staging_url_rejects_known_production_services(url):
    with pytest.raises(ValueError, match="production"):
        validate_staging_base_url(url)


def test_staging_url_requires_explicit_value():
    with pytest.raises(ValueError, match="required"):
        validate_staging_base_url(None)


def test_staging_url_rejects_insecure_nonlocal_urls():
    with pytest.raises(ValueError, match="HTTPS"):
        validate_staging_base_url("http://retail-mind-staging.onrender.com")


def test_staging_url_rejects_embedded_credentials():
    with pytest.raises(ValueError, match="credentials"):
        validate_staging_base_url("https://user:password@retail-mind-staging.onrender.com")


def test_staging_url_accepts_https_preview_host():
    assert validate_staging_base_url(
        "https://retail-mind-staging.onrender.com/"
    ) == "https://retail-mind-staging.onrender.com"


def test_local_staging_can_use_http_explicitly():
    assert validate_staging_base_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"
