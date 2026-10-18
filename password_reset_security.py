"""Retired experimental password-reset endpoints.

The former hardened flow was unsafe because it returned the mailbox-confirmation
URL to its unauthenticated caller and let the caller register the OTP proof.
Keep the old paths registered but explicitly disabled so old clients get a
clear 410 response and cannot accidentally fall back to the unsafe flow.
Use the backend-generated, email-delivered OTP flow under /auth instead.
"""

from fastapi import HTTPException


_DISABLED_DETAIL = (
    "This experimental password-reset flow is disabled for security. "
    "Use the owner OTP password-reset flow under /auth."
)


def _disabled_password_reset_endpoint():
    raise HTTPException(status_code=410, detail=_DISABLED_DETAIL)


def attach_password_reset_security_routes(router) -> None:
    """Register explicit 410 responses for every retired route."""

    disabled_routes = (
        ("/password-reset/start", ["POST"], "disabled_password_reset_start"),
        ("/password-reset/register-otp", ["POST"], "disabled_password_reset_register_otp"),
        ("/password-reset/confirm-email", ["GET"], "disabled_password_reset_confirm_email"),
        ("/password-reset/authorize", ["POST"], "disabled_password_reset_authorize"),
        ("/password-reset/status", ["GET"], "disabled_password_reset_status"),
    )

    for path, methods, name in disabled_routes:
        router.add_api_route(
            path,
            _disabled_password_reset_endpoint,
            methods=methods,
            name=name,
            include_in_schema=False,
        )
