"""Capability registry reflects implemented APIs and deployment feature flag."""
import os
from typing import Any

_IMPLEMENTED = {
    "inventory.lookup",
    "customer.lookup",
    "billing.prepare",
    "billing.confirm",
    "khata.lookup",
    "orders.lookup",
    "attendance.lookup",
    "analytics.read",
    "voice.transcription",
    "voice.synthesis",
}
_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {"name": "inventory.lookup", "description": "Read active catalog products and stock for the authenticated shop.", "risk": "read", "requires_confirmation": False},
    {"name": "customer.lookup", "description": "Find active customers belonging to the authenticated shop.", "risk": "personal_data_read", "requires_confirmation": False},
    {"name": "billing.prepare", "description": "Use the existing voice-billing parser to prepare a five-minute invoice preview; no invoice or stock mutation occurs.", "risk": "draft", "requires_confirmation": False},
    {"name": "billing.confirm", "description": "Confirm a specific owner-reviewed preview through the existing invoice creation path, then verify invoice and stock movements.", "risk": "financial_write", "requires_confirmation": True},
    {"name": "khata.lookup", "description": "Read the legacy shop-scoped Khata balance summary. Credit and repayment writes remain disabled.", "risk": "read", "requires_confirmation": False},
    {"name": "orders.lookup", "description": "Read shop-scoped online order counts and recent order statuses. Order changes remain disabled.", "risk": "read", "requires_confirmation": False},
    {"name": "attendance.lookup", "description": "Read attendance summaries for a date in the authenticated shop.", "risk": "employee_data_read", "requires_confirmation": False},
    {"name": "analytics.read", "description": "Read a bounded invoice-based billed/received summary.", "risk": "read", "requires_confirmation": False},
    {"name": "voice.transcription", "description": "Transcribe owner voice input using the existing Sarvam Saaras adapter.", "risk": "external_provider", "requires_confirmation": False},
    {"name": "voice.synthesis", "description": "Synthesize an assistant response using Sarvam Bulbul for a supported Indian language.", "risk": "external_provider", "requires_confirmation": False},
    {"name": "khata.record", "description": "Record credit or repayment. Disabled until a single canonical ledger write path and replay protection are verified.", "risk": "financial_write", "requires_confirmation": True},
    {"name": "orders.manage", "description": "Accept, reject, cancel or refund an order. Disabled until every transition is wrapped and tested.", "risk": "business_write", "requires_confirmation": True},
    {"name": "attendance.manage", "description": "Change attendance or payroll records. Disabled until approved correction workflow is defined.", "risk": "employee_data_write", "requires_confirmation": True},
)


def list_capabilities() -> list[dict[str, Any]]:
    """Return deployment-aware capability flags without exposing server secrets."""
    enabled = os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    return [
        {
            **item,
            "implemented": item["name"] in _IMPLEMENTED,
            "enabled": bool(enabled and item["name"] in _IMPLEMENTED),
        }
        for item in _CAPABILITIES
    ]
