"""Regression checks for production-backend audit fixes."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def function_block(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    end_at = source.index(end, start_at)
    return source[start_at:end_at]


def test_public_self_registration_cannot_mint_worker_or_customer_roles():
    source = read_source("auth_routes.py")
    register = function_block(source, 'def register(', '@router.post("/login")')
    assert "requested_role != ROLE_OWNER" in register
    assert "requested_legacy_role != ROLE_OWNER" in register
    assert "is_active=True" in register


def test_owner_password_reset_otp_lookup_locks_the_challenge_row():
    source = read_source("auth_routes.py")
    lookup = function_block(source, "def _find_db_otp(", "otp_cache = {}")
    assert ".with_for_update().first()" in lookup


def test_customer_password_reset_otp_has_account_level_throttle():
    source = read_source("online_store.py")
    request = function_block(
        source,
        'def request_customer_password_reset_otp(',
        '@router.post("/customer/verify-password-reset-otp")',
    )
    assert ".with_for_update().first()" in request
    assert "recent_otp_count >= 3" in request
    assert "timedelta(minutes=10)" in request


def test_coupon_usage_is_locked_and_released_for_cancelled_orders():
    source = read_source("online_store.py")
    authenticated = function_block(source, '@router.post("/order")', '@router.post("/guest-order")')
    guest = function_block(source, '@router.post("/guest-order")', '@router.get("/my-orders")')
    reverse = function_block(
        source,
        "def _release_online_order_coupon(",
        "# =====================\n# CUSTOMER AUTH SCHEMAS",
    )
    assert ".with_for_update().first()" in authenticated
    assert ".with_for_update().first()" in guest
    assert "coupon.used_count = current_count - 1" in reverse
    assert "_release_online_order_coupon(db, order, shop_id)" in reverse


def test_unpaid_upi_reservations_expire_under_row_lock_and_restore_stock():
    source = read_source("production_boot.py")
    expiry = function_block(
        source,
        "def _expire_stale_unpaid_online_order_reservations(",
        "def _run_periodic_maintenance(",
    )
    assert 'ONLINE_ORDER_UPI_RESERVATION_MINUTES' in expiry
    assert 'OnlineOrder.payment_method == "UPI"' in expiry
    assert 'OnlineOrder.payment_status == "PENDING"' in expiry
    assert 'OnlineOrder.order_status.in_(["PENDING", "ACCEPTED"])' in expiry
    assert ".with_for_update(skip_locked=True)" in expiry
    assert "_reverse_online_order_financials(" in expiry
    assert 'order.order_status = "CANCELLED"' in expiry


def test_stock_movement_endpoint_is_idempotent_and_preserves_http_errors():
    source = read_source("inventory.py")
    schema = function_block(
        source,
        "class StockMovementCreate(",
        "class ProductBatchCreate(",
    )
    route = function_block(
        source,
        '@router.post("/stock-movement", response_model=dict)',
        '@router.get("/stock-movements/{product_id}")',
    )
    assert "idempotency_key: Optional[str]" in schema
    assert "StockMovement.idempotency_key == idempotency_key" in route
    assert "stock_movement.idempotency_key = idempotency_key" in route
    assert "except HTTPException:" in route
    assert "except IntegrityError:" in route


def test_payment_notification_rejects_blank_idempotency_and_reference():
    source = read_source("online_store.py")
    schema = function_block(
        source,
        "class PaymentNotificationMatch(",
        "class OrderRating(",
    )
    assert '@field_validator("payment_reference", "idempotency_key")' in schema
    assert "if not cleaned:" in schema


def test_upi_reservation_index_migration_follows_cancellation_cleanup():
    migration = read_source(
        "alembic/versions/042_upi_reservation_expiry_index.py"
    )
    assert 'revision = "042_upi_reservation_expiry_index"' in migration
    assert 'down_revision = "041_cancelled_online_order_financial_cleanup"' in migration
    assert "ix_online_orders_upi_pending_reservation" in migration
