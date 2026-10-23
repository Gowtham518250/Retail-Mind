"""Clean legacy cancelled online-order invoices and dashboard journal artifacts.

Revision ID: 041_cancelled_online_order_financial_cleanup
Revises: 040_fractional_stock_units

The migration is idempotent by design: it only targets invoices and journal rows
that can be tied to an order already marked CANCELLED, REJECTED, or RETURNED.
Real receipts are preserved as REFUND_REQUIRED audit rows, not revenue.
"""
from datetime import datetime
from decimal import Decimal

from alembic import op
import sqlalchemy as sa


revision = "041_cancelled_online_order_financial_cleanup"
down_revision = "040_fractional_stock_units"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    required = {"online_orders", "invoices", "universal_transactions"}
    if not required.issubset(tables):
        # Older dev/test databases may not have all optional feature tables.
        return

    orders = conn.execute(sa.text("""
        SELECT id, shop_id, total_amount, payment_status, payment_confirmed_at
        FROM online_orders
        WHERE UPPER(CAST(order_status AS VARCHAR)) IN ('CANCELLED', 'REJECTED', 'RETURNED')
        ORDER BY id
    """)).mappings().all()

    invoice_query = sa.text("""
        SELECT id, invoice_number, paid_amount
        FROM invoices
        WHERE user_id = :shop_id
          AND (
              LOWER(COALESCE(notes, '')) LIKE :note_pattern
              OR LOWER(COALESCE(notes, '')) LIKE :note_exact_pattern
              OR invoice_number = :prefix
              OR invoice_number LIKE :prefix_dash
          )
    """)

    # reference_id is a VARCHAR column. Explicitly type the expanding bind
    # parameters as strings: SQLAlchemy otherwise compiles an empty invoice list
    # to "IN (SELECT CAST(NULL AS INTEGER) WHERE 1!=1)", which PostgreSQL rejects
    # as varchar = integer when a cancelled order has no matching invoices.
    payment_query = sa.text("""
        SELECT id, amount, reference_id, description
        FROM universal_transactions
        WHERE shop_id = :shop_id
          AND category IN ('PAYMENT', 'REFUND_REQUIRED')
          AND (
              reference_id = :fallback_ref
              OR reference_id = :order_ref
              OR reference_id LIKE :prefix_dash
              OR reference_id IN :invoice_numbers
          )
    """).bindparams(
        sa.bindparam("invoice_numbers", expanding=True, type_=sa.String())
    )

    sale_query = sa.text("""
        SELECT id
        FROM universal_transactions
        WHERE shop_id = :shop_id
          AND category = 'SALE'
          AND (
              reference_id = :sale_ref
              OR reference_id LIKE :prefix_dash
              OR reference_id IN :invoice_numbers
          )
    """).bindparams(
        sa.bindparam("invoice_numbers", expanding=True, type_=sa.String())
    )

    for order in orders:
        order_id = int(order["id"])
        shop_id = int(order["shop_id"])
        prefix = f"ONL-{order_id}"
        note_pattern = f"%online order #{order_id} |%"
        note_exact_pattern = f"%online order #{order_id}"
        prefix_dash = f"{prefix}-%"
        params = {
            "shop_id": shop_id,
            "note_pattern": note_pattern,
            "note_exact_pattern": note_exact_pattern,
            "prefix": prefix,
            "prefix_dash": prefix_dash,
        }
        invoices = conn.execute(invoice_query, params).mappings().all()
        invoice_ids = [int(row["id"]) for row in invoices]
        invoice_numbers = [
            str(row["invoice_number"]) for row in invoices if row["invoice_number"]
        ]

        received_amount = max(
            (Decimal(str(row["paid_amount"] or 0)) for row in invoices),
            default=Decimal("0"),
        )
        order_payment_status = str(order["payment_status"] or "").upper()
        if order_payment_status in {"PAID", "REFUND_REQUIRED"}:
            received_amount = max(
                received_amount,
                Decimal(str(order["total_amount"] or 0)),
            )

        payment_params = {
            "shop_id": shop_id,
            "fallback_ref": f"{prefix}-PAYMENT",
            "order_ref": prefix,
            "prefix_dash": prefix_dash,
            "invoice_numbers": invoice_numbers,
        }
        payment_rows = conn.execute(payment_query, payment_params).mappings().all()
        journal_received_amount = sum(
            (Decimal(str(payment["amount"] or 0)) for payment in payment_rows),
            Decimal("0"),
        )
        received_amount = max(received_amount, journal_received_amount)
        for payment in payment_rows:
            description = (
                f"Refund required for cancelled online order #{order_id}; "
                f"{payment['description'] or 'Payment receipt retained'}"
            )[:200]
            conn.execute(sa.text("""
                UPDATE universal_transactions
                SET category = 'REFUND_REQUIRED', description = :description
                WHERE id = :tx_id
            """), {"description": description, "tx_id": int(payment["id"])})

        if received_amount > Decimal("0") and not payment_rows:
            conn.execute(sa.text("""
                INSERT INTO universal_transactions
                    (shop_id, tx_type, category, amount, reference_id, description, tx_date)
                VALUES
                    (:shop_id, 'INCOME', 'REFUND_REQUIRED', :amount, :reference_id, :description, :tx_date)
            """), {
                "shop_id": shop_id,
                "amount": float(received_amount),
                "reference_id": invoice_numbers[0] if invoice_numbers else f"{prefix}-PAYMENT",
                "description": f"Refund required for cancelled online order #{order_id}",
                "tx_date": order["payment_confirmed_at"] or datetime.utcnow(),
            })

        if received_amount > Decimal("0"):
            conn.execute(sa.text("""
                UPDATE online_orders
                SET payment_status = 'REFUND_REQUIRED'
                WHERE id = :order_id
            """), {"order_id": order_id})

        sale_params = {
            "shop_id": shop_id,
            "sale_ref": prefix,
            "prefix_dash": prefix_dash,
            "invoice_numbers": invoice_numbers,
        }
        sale_rows = conn.execute(sale_query, sale_params).mappings().all()
        for sale_row in sale_rows:
            conn.execute(sa.text(
                "DELETE FROM universal_transactions WHERE id = :tx_id"
            ), {"tx_id": int(sale_row["id"])})

        conn.execute(sa.text("""
            DELETE FROM universal_transactions
            WHERE shop_id = :shop_id
              AND reference_id = :reversal_ref
              AND category = 'SALE_REVERSAL'
        """), {"shop_id": shop_id, "reversal_ref": f"{prefix}-REVERSAL"})

        if "sales" in tables:
            conn.execute(sa.text("""
                DELETE FROM sales
                WHERE shopkeeper_id = :shop_id AND reference_order_id = :order_id
            """), {"shop_id": shop_id, "order_id": order_id})

        # Explicit child deletes support legacy schemas without ON DELETE CASCADE.
        for invoice_id in invoice_ids:
            if "invoice_line_items" in tables:
                conn.execute(sa.text(
                    "DELETE FROM invoice_line_items WHERE invoice_id = :invoice_id"
                ), {"invoice_id": invoice_id})
            if "payments" in tables:
                conn.execute(sa.text(
                    "DELETE FROM payments WHERE invoice_id = :invoice_id"
                ), {"invoice_id": invoice_id})
            conn.execute(sa.text(
                "DELETE FROM invoices WHERE id = :invoice_id AND user_id = :shop_id"
            ), {"invoice_id": invoice_id, "shop_id": shop_id})


def downgrade():
    # This correction deletes cancelled-order invoice documents and reclassifies
    # real receipts. Re-creating the prior misleading dashboard rows would be unsafe.
    pass
