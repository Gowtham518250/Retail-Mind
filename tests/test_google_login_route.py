"""Regression checks for the owner app's Google sign-in contract."""


from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_google_login_route_is_mounted_at_the_frontend_path():
    auth_source = (ROOT / "auth_routes.py").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert '@router.post("/google")' in auth_source
    assert 'include_router(authentication_router, prefix="/auth"' in app_source


def test_google_login_uses_google_verified_identity_not_client_email():
    source = (ROOT / "auth_routes.py").read_text(encoding="utf-8")

    assert 'https://openidconnect.googleapis.com/v1/userinfo' in source
    assert 'headers={"Authorization": f"Bearer {google_token}"}' in source
    assert 'google_profile.get("email_verified", "")' in source
    assert 'func.lower(User.email) == google_email' in source
    assert "email/name supplied by the browser as proof of account ownership" in source


def test_google_login_returns_the_normal_access_and_refresh_session():
    source = (ROOT / "auth_routes.py").read_text(encoding="utf-8")
    route_start = source.index('@router.post("/google")')
    route_end = source.index('@router.post("/login")', route_start)
    route = source[route_start:route_end]

    assert '"access_token": access_token' in route
    assert '"refresh_token": refresh_token' in route
    assert '"token_type": "bearer"' in route
    assert '"user_id": db_user.id' in route
    assert '"role": user_role' in route



def test_endpoint_audit_lists_google_sign_in_for_client_and_server():
    source = (ROOT / "endpoint_matching.py").read_text(encoding="utf-8")

    assert "'POST /auth/google': 'authentication_router'" in source
    assert "'/auth/google': 'googleSignInEndpoint'" in source


def test_google_login_reports_existing_account_vs_auto_registration():
    source = (ROOT / "auth_routes.py").read_text(encoding="utf-8")
    route_start = source.index('@router.post("/google")')
    route_end = source.index('@router.post("/login")', route_start)
    route = source[route_start:route_end]

    # Existing accounts are selected by Google's verified email, while absent
    # emails are provisioned by this same endpoint.
    assert "is_new_user = db_user is None" in route
    assert "db_user = db.query(User).filter(func.lower(User.email) == google_email).first()" in route
    assert '"is_new_user": is_new_user' in route
    assert '"email": db_user.email' in route
    assert "ShopProfile(" in route
