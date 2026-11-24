"""Authenticated, read-only discovery endpoints for the agent foundation."""
from fastapi import APIRouter, Depends

from security import owner_only
from .registry import list_capabilities

router = APIRouter(prefix="/api/agent", tags=["Retail Mind Agent"])


@router.get("/capabilities")
def get_agent_capabilities(_owner: dict = Depends(owner_only)):
    """List the agent capabilities and their safety gates.

    This endpoint deliberately does not expose data or execute tools. Disabled
    capabilities remain unavailable until their service wrappers and tests ship.
    """
    capabilities = list_capabilities()
    return {
        "status": "foundation_ready",
        "execution_enabled": False,
        "capabilities": capabilities,
        "safety": {
            "shop_scope": "derived_from_authenticated_owner",
            "financial_writes_require_confirmation": True,
            "llm_direct_database_access": False,
            "success_requires_server_verification": True,
        },
    }
