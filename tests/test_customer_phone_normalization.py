"""Customer phone input normalization contract tests."""

import pytest
from pydantic import ValidationError

from customers import CustomerCreate, CustomerUpdate


@pytest.mark.parametrize(
    ("raw_phone", "expected"),
    [
        ("9876543210", "9876543210"),
        ("98765 43210", "9876543210"),
        ("+91 98765 43210", "9876543210"),
        ("919876543210", "9876543210"),
        ("09876543210", "9876543210"),
        ("0091 98765 43210", "9876543210"),
    ],
)
def test_customer_create_normalizes_indian_phone(raw_phone, expected):
    customer = CustomerCreate(customer_name="Test Customer", phone=raw_phone)
    assert customer.phone == expected


def test_customer_update_normalizes_indian_phone():
    customer = CustomerUpdate(phone="+91-98765-43210")
    assert customer.phone == "9876543210"


@pytest.mark.parametrize("invalid_phone", ["", "12345", "1234567890", "abcdefghij"])
def test_customer_create_rejects_invalid_phone(invalid_phone):
    with pytest.raises(ValidationError):
        CustomerCreate(customer_name="Test Customer", phone=invalid_phone)
