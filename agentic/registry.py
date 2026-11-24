"""Capability registry reflects implementation and required provider configuration."""
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
    "khata.payment",
    "khata.record",
    "orders.transition",
    "voice.transcription",
    "voice.synthesis",
}
_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {"name": "inventory.lookup", "description": "Read active catalog products and stock for the authenticated shop.", "risk": "read", "requires_confirmation": False, "provider": "groq"},
    {"name": "customer.lookup", "description": "Find active customers belonging to the authenticated shop.", "risk": "personal_data_read", "requires_confirmation": False, "provider": "groq"},
    {"name": "billing.prepare", "description": "Use the existing voice-billing parser to prepare a five-minute invoice preview; no invoice or stock mutation occurs.", "risk": "draft", "requires_confirmation": False, "provider": "groq"},
    {"name": "billing.confirm", "description": "Confirm a specific owner-reviewed preview through the existing invoice creation path, then verify invoice and stock movements.", "risk": "financial_write", "requires_confirmation": True, "provider": "backend"},
    {"name": "khata.lookup", "description": "Read the invoice-derived pending-payment receivables view for the authenticated shop. This is not the legacy KhataBalance ledger; credit and repayment writes remain disabled.", "risk": "read", "requires_confirmation": False, "provider": "groq"},
    {"name": "orders.lookup", "description": "Read shop-scoped online order counts and recent order statuses. Order changes remain disabled.", "risk": "read", "requires_confirmation": False, "provider": "groq"},
    {"name": "attendance.lookup", "description": "Read attendance summaries for a date in the authenticated shop.", "risk": "employee_data_read", "requires_confirmation": False, "provider": "groq"},
    {"name": "analytics.read", "description": "Read a bounded invoice-based billed/received summary.", "risk": "read", "requires_confirmation": False, "provider": "groq"},
    {"name": "khata.payment", "description": "Record payment against one selected invoice using the existing idempotent invoice-payment engine; requires owner confirmation.", "risk": "financial_write", "requires_confirmation": True, "provider": "backend"},
    {"name": "orders.transition", "description": "Accept, dispatch or reject an online order via the existing owner route; requires confirmation. Delivery, cancellation and refunds remain disabled.", "risk": "business_write", "requires_confirmation": True, "provider": "backend"},
    {"name": "voice.transcription", "description": "Transcribe owner voice input using Sarvam Saaras and process it through the Groq assistant.", "risk": "external_provider", "requires_confirmation": False, "provider": "groq_sarvam"},
    {"name": "voice.synthesis", "description": "Synthesize an assistant response using Sarvam Bulbul for supported Indian languages.", "risk": "external_provider", "requires_confirmation": False, "provider": "sarvam"},
    {"name": "khata.record", "description": "Add legacy Khata credit or record a repayment using an atomic, idempotent history and journal write after owner confirmation.", "risk": "financial_write", "requires_confirmation": True, "provider": "backend"},
    {"name": "orders.manage", "description": "Accept, reject, cancel or refund an order. Disabled until every transition is wrapped and tested.", "risk": "business_write", "requires_confirmation": True, "provider": "disabled"},
    {"name": "attendance.manage", "description": "Change attendance or payroll records. Disabled until approved correction workflow is defined.", "risk": "employee_data_write", "requires_confirmation": True, "provider": "disabled"},
)


def list_capabilities() -> list[dict[str, Any]]:
    """Return deployment-aware capability configuration without exposing secrets."""
    feature_enabled = os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    groq_ready = bool((os.getenv("GROQ_API_KEY") or "").strip())
    sarvam_ready = bool((os.getenv("SARVAM_API_KEY") or "").strip())

    def provider_ready(provider: str) -> bool:
        if provider == "groq":
            return groq_ready
        if provider == "backend":
            return True
        if provider == "groq_sarvam":
            return groq_ready and sarvam_ready
        if provider == "sarvam":
            return sarvam_ready
        return False

    result = []
    for item in _CAPABILITIES:
        implemented = item["name"] in _IMPLEMENTED
        configured = provider_ready(item["provider"])
        result.append({
            **item,
            "implemented": implemented,
            "configured": configured,
            "enabled": bool(feature_enabled and implemented and configured),
        })
    return result
