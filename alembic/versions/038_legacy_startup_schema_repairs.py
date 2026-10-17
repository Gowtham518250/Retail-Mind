"""Move legacy idempotent startup column repairs into versioned schema migration.

Revision ID: 038_legacy_startup_schema_repairs
Revises: 037_password_reset_attempts
"""
from alembic import op
import sqlalchemy as sa

revision = "038_legacy_startup_schema_repairs"
down_revision = "037_password_reset_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    column_cache = {
        table: {column["name"]: column for column in inspector.get_columns(table)}
        for table in tables
    }

    def add_column_if_missing(
        table: str,
        name: str,
        column_type,
        *,
        nullable: bool = True,
        server_default=None,
    ) -> None:
        if table not in tables:
            return
        columns = column_cache[table]
        if name in columns:
            return
        kwargs = {"nullable": nullable}
        if server_default is not None:
            kwargs["server_default"] = server_default
        column = sa.Column(name, column_type, **kwargs)
        op.add_column(table, column)
        columns[name] = {
            "name": name,
            "type": column_type,
            "nullable": nullable,
            "default": server_default,
        }

    # These fields were historically reconciled by app.py on every import.
    # Apply the same additive repairs once, before the API process starts.
    column_repairs = {
        "user_details": [
            ("fcm_token", sa.String(255), True, None),
            ("is_active", sa.Boolean(), True, sa.text("TRUE")),
        ],
        "products": [
            ("purchase_price", sa.Numeric(10, 2), True, sa.text("0")),
            ("image_url", sa.Text(), True, None),
            ("branch_id", sa.Integer(), True, None),
        ],
        "customers": [
            ("state", sa.String(50), True, None),
            ("postal_code", sa.String(20), True, None),
        ],
        "shop_profiles": [
            ("shop_tagline", sa.String(500), True, None),
            ("shop_description", sa.Text(), True, None),
            ("shop_type", sa.String(100), True, sa.text("'General'")),
            ("phone", sa.String(20), True, None),
            ("email", sa.String(100), True, None),
            ("website", sa.String(200), True, None),
            ("gst_number", sa.String(50), True, None),
            ("logo_url", sa.String(500), True, None),
            ("logo_base64", sa.Text(), True, None),
            ("logo_content_type", sa.String(100), True, None),
            ("latitude", sa.Float(), True, None),
            ("longitude", sa.Float(), True, None),
            ("address", sa.Text(), True, None),
            ("address_line1", sa.String(200), True, None),
            ("address_line2", sa.String(200), True, None),
            ("location", sa.String(300), True, None),
            ("city", sa.String(100), True, None),
            ("state", sa.String(100), True, None),
            ("postal_code", sa.String(10), True, None),
            ("upi_id", sa.String(100), True, None),
            ("upi_ids", sa.Text(), True, None),
            ("shop_categories", sa.Text(), True, None),
            ("is_online_store_enabled", sa.Boolean(), True, sa.text("FALSE")),
            ("rating_score", sa.Float(), False, sa.text("0")),
            ("rating_count", sa.Integer(), False, sa.text("0")),
            ("online_setup_fee", sa.Numeric(10, 2), False, sa.text("0")),
            ("online_min_order", sa.Numeric(10, 2), False, sa.text("0")),
            ("online_delivery_fee", sa.Numeric(10, 2), False, sa.text("0")),
            ("online_offer_delivery", sa.Boolean(), False, sa.text("TRUE")),
            ("online_offer_pickup", sa.Boolean(), False, sa.text("TRUE")),
            ("online_accept_cod", sa.Boolean(), False, sa.text("TRUE")),
            ("online_accept_online", sa.Boolean(), False, sa.text("FALSE")),
            ("pan_number", sa.String(50), True, None),
            ("registration_number", sa.String(100), True, None),
            ("contact_person_name", sa.String(100), True, None),
            ("contact_person_phone", sa.String(20), True, None),
            ("contact_person_email", sa.String(100), True, None),
            ("color_primary", sa.String(20), True, None),
            ("color_secondary", sa.String(20), True, None),
            ("logo_file_path", sa.String(500), True, None),
            ("logo_version", sa.Integer(), True, sa.text("0")),
            ("created_at", sa.DateTime(), True, None),
            ("updated_at", sa.DateTime(), True, None),
        ],
        "online_customers": [
            ("phone", sa.String(20), True, None),
            ("city", sa.String(100), True, None),
            ("address", sa.Text(), True, None),
        ],
        "online_orders": [
            ("payment_method", sa.String(20), False, sa.text("'COD'")),
            ("payment_status", sa.String(24), False, sa.text("'COD_DUE'")),
            ("payment_reference", sa.String(128), True, None),
            ("payment_confirmation_source", sa.String(50), True, None),
            ("payment_detection_key", sa.String(128), True, None),
            ("payment_confirmed_at", sa.DateTime(), True, None),
            ("idempotency_key", sa.String(128), True, None),
            ("online_setup_fee", sa.Numeric(10, 2), False, sa.text("0")),
            ("branch_id", sa.Integer(), True, None),
            ("coupon_code", sa.String(50), True, None),
            ("discount_amount", sa.Numeric(12, 2), False, sa.text("0")),
        ],
        "invoices": [
            ("branch_id", sa.Integer(), True, None),
        ],
        "purchase_orders": [
            ("branch_id", sa.Integer(), True, None),
        ],
        "shop_expenses": [
            ("branch_id", sa.Integer(), True, None),
        ],
    }

    for table, repairs in column_repairs.items():
        for name, column_type, nullable, default in repairs:
            add_column_if_missing(
                table,
                name,
                column_type,
                nullable=nullable,
                server_default=default,
            )

    # Preserve the legacy nullable due-date behavior without changing the
    # existing column's data type.
    if "invoices" in tables and "due_date" in column_cache["invoices"]:
        due_date = column_cache["invoices"]["due_date"]
        if not due_date.get("nullable", True):
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table("invoices") as batch_op:
                    batch_op.alter_column(
                        "due_date",
                        existing_type=due_date["type"],
                        existing_nullable=False,
                        nullable=True,
                    )
            else:
                op.alter_column(
                    "invoices",
                    "due_date",
                    existing_type=due_date["type"],
                    existing_nullable=False,
                    nullable=True,
                )

    # The old startup patch deliberately skipped indexes when their table or
    # column was missing. Keep that compatibility, but perform the work once.
    index_cache = {
        table: {index["name"] for index in sa.inspect(bind).get_indexes(table)}
        for table in tables
    }

    def create_index_if_missing(
        name: str, table: str, columns: list[str], *, unique: bool = False
    ) -> None:
        if table not in tables:
            return
        if name in index_cache[table]:
            return
        if not all(column in column_cache[table] for column in columns):
            return
        op.create_index(name, table, columns, unique=unique)
        index_cache[table].add(name)

    create_index_if_missing(
        "ix_invoices_offline_id", "invoices", ["offline_id"]
    )
    create_index_if_missing(
        "uq_online_order_shop_payment_key",
        "online_orders",
        ["shop_id", "payment_detection_key"],
        unique=True,
    )
    create_index_if_missing(
        "ix_online_orders_idempotency_key",
        "online_orders",
        ["idempotency_key"],
    )

    if (
        "shop_profiles" in tables
        and "is_active" in column_cache["shop_profiles"]
    ):
        op.execute(
            sa.text("UPDATE shop_profiles SET is_active = TRUE WHERE is_active IS NULL")
        )


def downgrade() -> None:
    # This revision is a non-destructive repair for legacy schemas. Retain the
    # additive columns on downgrade so data written after this revision is not
    # silently dropped.
    pass
