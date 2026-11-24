"""Central, explicit capability registry for the Retail Mind assistant.

No tool in this registry executes business mutations yet. Each capability is
marked unavailable until its wrapper, authorization, confirmation, idempotency,
and integration tests are implemented.
"""
from typing import Any

_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "name": "inventory.lookup",
        "description": "Read products and stock belonging to the authenticated shop.",
        "risk": "read",
        "requires_confirmation": False,
        "enabled": False,
    },
    {
        "name": "customer.lookup",
        "description": "Find a customer using shop-scoped identifiers.",
        "risk": "read",
        "requires_confirmation": False,
        "enabled": False,
    },
    {
        "name": "billing.prepare",
        "description": "Prepare a draft invoice from confirmed products and quantities.",
        "risk": "draft",
        "requires_confirmation": False,
        "enabled": False,
    },
    {
        "name": "billing.create",
        "description": "Create an invoice and apply the existing billing/stock rules.",
        "risk": "financial_write",
        "requires_confirmation": True,
        "enabled": False,
    },
    {
        "name": "khata.record",
        "description": "Record customer credit or repayment in the existing ledger.",
        "risk": "financial_write",
        "requires_confirmation": True,
        "enabled": False,
    },
    {
        "name": "orders.manage",
        "description": "Review or update online orders using existing owner routes.",
        "risk": "business_write",
        "requires_confirmation": True,
        "enabled": False,
    },
    {
        "name": "attendance.lookup",
        "description": "Read attendance information for the authenticated shop.",
        "risk": "read",
        "requires_confirmation": False,
        "enabled": False,
    },
    {
        "name": "analytics.read",
        "description": "Read shop-scoped sales, inventory, and business summaries.",
        "risk": "read",
        "requires_confirmation": False,
        "enabled": False,
    },
)


def list_capabilities() -> list[dict[str, Any]]:
    """Return copies so callers cannot mutate the process-wide registry."""
    return [dict(item) for item in _CAPABILITIES]
