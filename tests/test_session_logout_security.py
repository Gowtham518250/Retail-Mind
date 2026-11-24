from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import session_routes


def _request_with_bearer(token=None):
    authorization = f"Bearer {token}" if token else ""
    return SimpleNamespace(headers={"authorization": authorization})


def test_logout_requires_the_authenticated_bearer_token(monkeypatch):
    calls = []
    monkeypatch.setattr(
        session_routes.SessionService,
        "logout",
        lambda db, token: calls.append((db, token)) or True,
    )
    db = object()

    result = session_routes.logout(
        session_routes.LogoutRequest(access_token="valid-access-token"),
        _request_with_bearer("valid-access-token"),
        current_user=42,
        db=db,
    )

    assert result == {"status": "Logged out successfully"}
    assert calls == [(db, "valid-access-token")]


@pytest.mark.parametrize(
    "body_token,header_token",
    [
        ("other-users-token", "current-users-token"),
        ("", "current-users-token"),
        ("current-users-token", None),
    ],
)
def test_logout_rejects_a_mismatched_or_missing_bearer_token(
    monkeypatch, body_token, header_token
):
    calls = []
    monkeypatch.setattr(
        session_routes.SessionService,
        "logout",
        lambda db, token: calls.append((db, token)) or True,
    )

    with pytest.raises(HTTPException) as error:
        session_routes.logout(
            session_routes.LogoutRequest(access_token=body_token),
            _request_with_bearer(header_token),
            current_user=42,
            db=object(),
        )

    assert error.value.status_code == 403
    assert calls == []
