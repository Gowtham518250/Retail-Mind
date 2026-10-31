import inspect

from auth_routes import get_sales


def test_legacy_sales_history_eager_loads_invoice_line_items():
    source = inspect.getsource(get_sales)
    assert "selectinload(Invoice.line_items)" in source
    assert "line_items = invoice.line_items or []" in source
    assert "InvoiceLineItem.invoice_id == invoice.id" not in source
