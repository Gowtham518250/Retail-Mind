from fastapi.testclient import TestClient

from app import api


def test_root_head_probe_returns_success_without_response_body():
    client = TestClient(api, base_url="http://localhost")

    response = client.head("/")

    assert response.status_code == 200
    assert response.content == b""
