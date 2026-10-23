"""Shared revenue-recognition policy for invoice-based analytics.

Online-store invoices are created when an order is accepted so the owner can
manage fulfilment and payment. That does not mean the order is a completed sale.
An ONLINE_ORDER invoice contributes to sales analytics only after its associated
OnlineOrder reaches DELIVERED. Cancelled invoices never contribute.
"""
from sqlalchemy import String, cast, exists, or_

from models import Invoice, InvoiceStatus, OnlineOrder, OnlineOrderStatus


def recognized_invoice_filters():
    """Return SQLAlchemy predicates for invoices that count as recognized sales.

    Legacy/manual invoices (including rows with a NULL source) retain the
    existing invoice-based accounting behaviour. For ONLINE_ORDER invoices,
    require a matching delivered order. Match using both the stable notes
    marker and invoice-number formats used by current/legacy order handlers.
    """
    order_id_text = cast(OnlineOrder.id, String)
    invoice_matches_order = or_(
        Invoice.notes.ilike("%Online Order #" + order_id_text + " |%"),
        Invoice.invoice_number == ("ONL-" + order_id_text),
        Invoice.invoice_number.like("ONL-" + order_id_text + "-%"),
    )
    delivered_order_exists = exists().where(
        OnlineOrder.shop_id == Invoice.user_id,
        OnlineOrder.order_status == OnlineOrderStatus.DELIVERED,
        invoice_matches_order,
    )
    revenue_invoice_source = or_(
        Invoice.source.is_(None),
        Invoice.source != "ONLINE_ORDER",
        delivered_order_exists,
    )
    return (
        Invoice.status != InvoiceStatus.CANCELLED,
        revenue_invoice_source,
    )
