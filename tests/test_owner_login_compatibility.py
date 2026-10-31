from auth_routes import UserLogin


def test_login_schema_accepts_email_field():
    request = UserLogin(email="owner@example.com", password="not-a-real-password")
    assert request.email == "owner@example.com"
    assert request.username is None


def test_login_schema_accepts_legacy_username_field():
    request = UserLogin(username="shopkeeper", password="not-a-real-password")
    assert request.username == "shopkeeper"
    assert request.email is None


def test_legacy_username_field_can_carry_an_email_identifier():
    request = UserLogin(
        username="owner@example.com",
        password="not-a-real-password",
    )
    assert request.username == "owner@example.com"
