import inspect

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from models import Invoice
from sales_recognition import recognized_invoice_filters


def test_online_order_invoice_counts_as_revenue_only_after_delivery():
    statement = select(Invoice.id).where(*recognized_invoice_filters())
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    # Regular/manual invoices keep existing behaviour, while an ONLINE_ORDER
    # invoice needs a matching order whose lifecycle has reached DELIVERED.
    assert "ONLINE_ORDER" in sql
    assert "DELIVERED" in sql
    assert "CANCELLED" in sql
    assert "online_orders" in sql


def test_owner_sales_analytics_use_the_shared_revenue_recognition_policy():
    from growth_suite import growth_overview, growth_analytics
    from observability_service import get_business_overview

    assert "recognized_invoice_filters()" in inspect.getsource(growth_overview)
    assert "recognized_invoice_filters()" in inspect.getsource(growth_analytics)
    assert "OnlineOrder.order_status == OnlineOrderStatus.DELIVERED" in inspect.getsource(growth_analytics)
    assert "recognized_invoice_filters()" in inspect.getsource(get_business_overview)


def test_cancel_and_finalized_order_paths_publish_sales_invalidation():
    from online_store import cancel_customer_order, update_order_status

    cancel_source = inspect.getsource(cancel_customer_order)
    action_source = inspect.getsource(update_order_status)

    assert "_online_order_sales_updated_event" in cancel_source
    assert "_online_order_sales_updated_event" in action_source
    assert "append_sync_event(db, event)" in cancel_source
    assert "append_sync_event(db, event)" in action_source
    assert "_invalidate_online_order_caches" in cancel_source
    assert "_invalidate_online_order_caches" in action_source


def test_sales_restore_distinguishes_open_invoices_from_recognized_sales():
    from sales_restore_service import restore_all_sales

    source = inspect.getsource(restore_all_sales)
    assert "counts_as_sale" in source
    assert "recognized_invoice_filters()" in source
    assert "recognized_invoices" in source
