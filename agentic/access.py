"""Pure policy evaluation for the Retail Mind owner assistant."""

from typing import Any


def resolve_agent_access(
    *,
    platform_enabled: bool,
    groq_configured: bool,
    sarvam_configured: bool,
    entitlement: dict[str, Any],
    preferences: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate platform, subscription and per-shop consent independently."""
    plan_features = entitlement.get("features") or {}
    plan_access = {
        "assistant": plan_features.get("ai_agent") is True,
        "voice": plan_features.get("ai_agent_voice") is True,
        "actions": plan_features.get("ai_agent_actions") is True,
    }
    settings = {
        "assistant_enabled": preferences.get("assistant_enabled") is True,
        "voice_enabled": preferences.get("voice_enabled") is True,
        "actions_enabled": preferences.get("actions_enabled") is True,
    }

    platform_ready = bool(platform_enabled and groq_configured)
    assistant_enabled = bool(
        platform_ready and plan_access["assistant"] and settings["assistant_enabled"]
    )
    voice_enabled = bool(
        assistant_enabled
        and plan_access["voice"]
        and settings["voice_enabled"]
        and sarvam_configured
    )
    actions_enabled = bool(
        assistant_enabled and plan_access["actions"] and settings["actions_enabled"]
    )

    if not platform_enabled:
        status = "platform_disabled"
    elif not groq_configured:
        status = "provider_configuration_missing"
    elif not plan_access["assistant"]:
        status = "plan_required"
    elif not settings["assistant_enabled"]:
        status = "owner_disabled"
    else:
        status = "enabled"

    return {
        "status": status,
        "plan_access": plan_access,
        "settings": settings,
        "assistant_enabled": assistant_enabled,
        "voice_enabled": voice_enabled,
        "actions_enabled": actions_enabled,
    }
