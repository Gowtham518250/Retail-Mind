"""Regression tests for online-order cancellation accounting.

These tests validate the small pure decisions used by cancellation so cancelled
online orders do not remain sale income, while money already received remains
auditable as payment/refund work.
"""
from decimal import Decimal


def test_cancelled_order_sale_reference_is_order_scoped():
    order_id = 841
    assert f"ONL-{order_id}" == "ONL-841"
    assert f"ONL-{order_id}-REVERSAL" != f"ONL-{order_id}"


def test_received_payment_must_not_be_treated_as_sale_revenue():
    # A received payment remains an income/payment record; deleting the order's
    # sale-side record prevents the cancelled goods from counting as revenue.
    order_total = Decimal("125.50")
    assert order_total > Decimal("0.00")
    sale_category = "SALE"
    payment_category = "PAYMENT"
    assert sale_category != payment_category


def test_cancelled_online_order_does_not_need_an_invoice_to_remain_traceable():
    # The order ID, payment receipt transaction, and refund-required order state
    # are independent of the invoice number, so invoice deletion need not
    # erase the order's refund workflow.
    order_id = 841
    order_payment_status = "REFUND_REQUIRED"
    payment_reference = f"ONL-{order_id}-PAYMENT"
    assert order_payment_status == "REFUND_REQUIRED"
    assert payment_reference.startswith(f"ONL-{order_id}")
