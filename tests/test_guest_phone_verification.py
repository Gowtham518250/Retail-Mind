import inspect

import pytest
from fastapi import HTTPException

from online_store import _guest_phone_matches_verified, place_guest_order


@pytest.mark.parametrize(
    ("provided", "verified", "expected"),
    [
        ("+919876543210", "+919876543210", True),
        ("9876543210", "+919876543210", True),
        ("09876543210", "+919876543210", True),
        ("9876543210", "+141598765432", False),
        ("9987654321", "+919876543210", False),
        ("", "+919876543210", False),
        ("9876543210", "", False),
    ],
)
def test_guest_phone_match_uses_exact_digits_not_substring(
    provided, verified, expected
):
    assert _guest_phone_matches_verified(provided, verified) is expected


def test_guest_checkout_does_not_fall_back_after_invalid_firebase_token():
    source = inspect.getsource(place_guest_order)
    assert "auth.verify_id_token(data.firebase_id_token)" in source
    assert "status_code=401" in source
    assert "status_code=403" in source
    assert "raise HTTPException(" in source
    assert "Falling back to unverified phone number" not in source
