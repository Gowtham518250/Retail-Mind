import os

os.environ.setdefault(
    "SECRET_KEY",
    "unit-test-access-token-boundary-secret-key-123456789",
)

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import security


def _credentials():
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")


def test_access_token_role_is_normalized(monkeypatch):
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda token: {"sub": "42", "role": "owner"},
    )

    result = security.get_current_user_dict(_credentials())

    assert result["user_id"] == 42
    assert result["role"] == "OWNER"


@pytest.mark.parametrize(
    "payload",
    [
        {"sub": "42"},
        {"sub": "42", "role": ""},
        {"sub": "42", "role": "ADMIN"},
        {"sub": "42", "role": None},
    ],
)
def test_access_token_with_missing_or_unknown_role_is_rejected(monkeypatch, payload):
    monkeypatch.setattr(security, "decode_token", lambda token: payload)

    with pytest.raises(HTTPException) as error:
        security.get_current_user_dict(_credentials())

    assert error.value.status_code == 401


@pytest.mark.parametrize("subject", [None, "", "not-an-id", "0", "-1"])
def test_invalid_access_token_subject_is_rejected(monkeypatch, subject):
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda token: {"sub": subject, "role": "OWNER"},
    )

    with pytest.raises(HTTPException) as error:
        security.get_current_user(_credentials())

    assert error.value.status_code == 401


def test_refresh_token_cannot_be_used_for_api_access(monkeypatch):
    refresh_payload = {"sub": "42", "role": "OWNER", "type": "refresh"}
    monkeypatch.setattr(security, "decode_token", lambda token: refresh_payload)

    with pytest.raises(HTTPException) as user_error:
        security.get_current_user(_credentials())
    assert user_error.value.status_code == 401

    with pytest.raises(HTTPException) as role_error:
        security.get_current_user_dict(_credentials())
    assert role_error.value.status_code == 401


def test_valid_access_identity_remains_accepted(monkeypatch):
    monkeypatch.setattr(
        security,
        "decode_token",
        lambda token: {"sub": "42", "role": "WORKER", "user_type": "WORKER"},
    )

    assert security.get_current_user(_credentials()) == 42
    assert security.get_current_user_dict(_credentials())["role"] == "WORKER"
