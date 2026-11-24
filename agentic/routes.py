"""Owner-authenticated Retail Mind AI assistant API."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import text
from zoneinfo import ZoneInfo
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from db import get_db
from models import AgentPendingAction
from security import owner_only, resolve_shop_id
from subscription_entitlements import get_shop_entitlements, feature_is_allowed
from sarvam_speech import SarvamSpeechError, app_language_code, transcribe_with_sarvam

from .registry import list_capabilities
from .access import resolve_agent_access
from sarvam_tts import SarvamTTSError, synthesize_with_sarvam

from .service import (
    confirm_agent_action,
    delete_conversation,
    get_conversation_messages,
    list_conversations,
    run_chat_turn,
)

router = APIRouter(prefix="/api/agent", tags=["Retail Mind Agent"])

_ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
    "audio/aac",
    "audio/flac",
}
_MAX_AUDIO_BYTES = 8 * 1024 * 1024


def _parse_conversation_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("conversation_id must be a UUID") from exc


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=3000)
    conversation_id: Optional[str] = None
    language_code: str = Field(default="auto", max_length=16)

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, value):
        return _parse_conversation_id(value)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value):
        cleaned = " ".join(str(value or "").split())
        if not cleaned:
            raise ValueError("message cannot be blank")
        return cleaned


class AgentConfirmRequest(BaseModel):
    preview_hash: str = Field(..., min_length=64, max_length=64)


class AgentSpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1800)
    language_code: str = Field(default="en", min_length=2, max_length=8)

    @field_validator("text")
    @classmethod
    def validate_speech_text(cls, value):
        cleaned = " ".join(str(value or "").split())
        if not cleaned:
            raise ValueError("text cannot be blank")
        return cleaned


class AgentSettingsUpdate(BaseModel):
    """Per-shop preferences; secrets and provider settings stay platform-owned."""

    model_config = {"extra": "forbid"}

    assistant_enabled: Optional[bool] = None
    voice_enabled: Optional[bool] = None
    actions_enabled: Optional[bool] = None


def _platform_agent_config() -> dict:
    master_enabled = os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    return {
        "master_enabled": master_enabled,
        "groq_configured": bool((os.getenv("GROQ_API_KEY") or "").strip()),
        "sarvam_configured": bool((os.getenv("SARVAM_API_KEY") or "").strip()),
    }


def _read_agent_preferences(db: Session, shop_id: int) -> dict:
    row = db.execute(text("""
        SELECT assistant_enabled, voice_enabled, actions_enabled
        FROM rm_shop_agent_settings
        WHERE shop_id = :shop_id
    """), {"shop_id": shop_id}).mappings().first()
    if not row:
        return {
            "assistant_enabled": False,
            "voice_enabled": False,
            "actions_enabled": False,
        }
    return {
        "assistant_enabled": bool(row["assistant_enabled"]),
        "voice_enabled": bool(row["voice_enabled"]),
        "actions_enabled": bool(row["actions_enabled"]),
    }


def _build_agent_control_snapshot(db: Session, shop_id: int) -> dict:
    entitlement = get_shop_entitlements(db, shop_id)
    preferences = _read_agent_preferences(db, shop_id)
    platform = _platform_agent_config()
    access = resolve_agent_access(
        platform_enabled=platform["master_enabled"],
        groq_configured=platform["groq_configured"],
        sarvam_configured=platform["sarvam_configured"],
        entitlement=entitlement,
        preferences=preferences,
    )

    usage_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    usage_row = db.execute(text("""
        SELECT used_count, reserved_count
        FROM rm_ai_daily_usage
        WHERE shop_id = :shop_id AND usage_date = :usage_date
    """), {"shop_id": shop_id, "usage_date": usage_date}).mappings().first()
    used = int(usage_row["used_count"] or 0) if usage_row else 0
    reserved = int(usage_row["reserved_count"] or 0) if usage_row else 0
    daily_limit = int(entitlement.get("daily_ai_query_limit") or 0)

    capabilities = list_capabilities()
    for capability in capabilities:
        name = str(capability.get("name") or "")
        if name.startswith("voice."):
            allowed = access["voice_enabled"]
        elif capability.get("requires_confirmation"):
            allowed = access["actions_enabled"]
        else:
            allowed = access["assistant_enabled"]
        capability["enabled"] = bool(
            capability.get("implemented")
            and capability.get("configured")
            and allowed
        )

    return {
        "status": access["status"],
        "execution_enabled": access["assistant_enabled"],
        "platform": platform,
        "plan": {
            "plan_code": entitlement["plan_code"],
            "plan_name": entitlement["plan_name"],
            "status": entitlement["status"],
            "features": entitlement.get("features", {}),
            "daily_ai_query_limit": daily_limit,
        },
        "settings": preferences,
        "entitlements": access["plan_access"],
        "access": {
            "assistant_enabled": access["assistant_enabled"],
            "voice_enabled": access["voice_enabled"],
            "actions_enabled": access["actions_enabled"],
        },
        "usage": {
            "used": used,
            "reserved": reserved,
            "daily_limit": daily_limit,
            "remaining": max(0, daily_limit - used - reserved),
            "reset_timezone": "Asia/Kolkata",
        },
        "capabilities": capabilities,
        "safety": {
            "owner_access_required": True,
            "shop_id_source": "authenticated_owner_access_token",
            "llm_direct_database_access": False,
            "llm_direct_http_or_shell_access": False,
            "financial_writes_require_separate_confirmation": True,
            "invoice_write_path": "existing_invoices_billing_create",
            "invoice_stock_verification": True,
            "pending_bill_preview_ttl_seconds": 300,
        },
    }


def _require_agent_access(db: Session, shop_id: int, feature: str = "assistant") -> dict:
    snapshot = _build_agent_control_snapshot(db, shop_id)
    platform = snapshot["platform"]
    settings = snapshot["settings"]
    entitlements = snapshot["entitlements"]

    if not platform["master_enabled"]:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AGENT_PLATFORM_DISABLED",
                "message": "The Retail Mind AI assistant is not enabled by the platform yet.",
            },
        )
    if not platform["groq_configured"]:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AGENT_PROVIDER_NOT_CONFIGURED",
                "message": "The AI provider is not configured on this deployment.",
            },
        )

    if not entitlements["assistant"]:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "SUBSCRIPTION_REQUIRED",
                "feature": "ai_agent",
                "current_plan": snapshot["plan"]["plan_code"],
                "message": "The AI assistant is not included in your current plan.",
                "upgrade_path": "/subscriptions",
            },
        )
    if not settings["assistant_enabled"]:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AGENT_DISABLED_BY_OWNER",
                "message": "Enable the AI assistant in Agent Control Center to continue.",
            },
        )

    if feature == "voice":
        if not entitlements["voice"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "SUBSCRIPTION_REQUIRED",
                    "feature": "ai_agent_voice",
                    "current_plan": snapshot["plan"]["plan_code"],
                    "message": "Voice assistant access is not included in your current plan.",
                    "upgrade_path": "/subscriptions",
                },
            )
        if not settings["voice_enabled"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AGENT_VOICE_DISABLED_BY_OWNER",
                    "message": "Enable voice assistance in Agent Control Center to use voice.",
                },
            )
        if not platform["sarvam_configured"]:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AGENT_VOICE_PROVIDER_NOT_CONFIGURED",
                    "message": "The voice provider is not configured on this deployment.",
                },
            )

    if feature == "actions":
        if not entitlements["actions"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "SUBSCRIPTION_REQUIRED",
                    "feature": "ai_agent_actions",
                    "current_plan": snapshot["plan"]["plan_code"],
                    "message": "AI business operations are not included in your current plan.",
                    "upgrade_path": "/subscriptions",
                },
            )
        if not settings["actions_enabled"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "AGENT_ACTIONS_DISABLED_BY_OWNER",
                    "message": "Enable business operations in Agent Control Center to prepare actions.",
                },
            )
    return snapshot


@router.get("/capabilities")
def get_agent_capabilities(
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Return provider, subscription, owner opt-in and usage status."""
    return _build_agent_control_snapshot(db, resolve_shop_id(current_user))


@router.get("/control-center")
def get_agent_control_center(
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Detailed control-center payload for the authenticated shop owner."""
    return _build_agent_control_snapshot(db, resolve_shop_id(current_user))


@router.put("/settings")
def update_agent_settings(
    data: AgentSettingsUpdate,
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Persist per-shop opt-ins; each enabled capability remains plan-gated."""
    shop_id = resolve_shop_id(current_user)
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one agent setting to update.")

    entitlement = get_shop_entitlements(db, shop_id)
    feature_for_setting = {
        "assistant_enabled": "ai_agent",
        "voice_enabled": "ai_agent_voice",
        "actions_enabled": "ai_agent_actions",
    }
    for setting_name, requested in updates.items():
        if requested is True:
            feature_name = feature_for_setting[setting_name]
            if not feature_is_allowed(entitlement, feature_name):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "SUBSCRIPTION_REQUIRED",
                        "feature": feature_name,
                        "current_plan": entitlement["plan_code"],
                        "message": "This AI capability is not included in your current plan.",
                        "upgrade_path": "/subscriptions",
                    },
                )

    current = _read_agent_preferences(db, shop_id)
    current.update(updates)
    db.execute(text("""
        INSERT INTO rm_shop_agent_settings (
            shop_id, assistant_enabled, voice_enabled, actions_enabled
        )
        VALUES (
            :shop_id, :assistant_enabled, :voice_enabled, :actions_enabled
        )
        ON CONFLICT (shop_id) DO UPDATE SET
            assistant_enabled = EXCLUDED.assistant_enabled,
            voice_enabled = EXCLUDED.voice_enabled,
            actions_enabled = EXCLUDED.actions_enabled,
            updated_at = NOW()
    """), {
        "shop_id": shop_id,
        "assistant_enabled": current["assistant_enabled"],
        "voice_enabled": current["voice_enabled"],
        "actions_enabled": current["actions_enabled"],
    })
    db.commit()
    return _build_agent_control_snapshot(db, shop_id)


@router.post("/chat")
async def agent_chat(
    data: AgentChatRequest,
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    shop_id = resolve_shop_id(current_user)
    snapshot = _require_agent_access(db, shop_id, "assistant")
    return await run_chat_turn(
        db,
        shop_id=shop_id,
        message=data.message,
        conversation_id=data.conversation_id,
        language_code=data.language_code,
        allow_actions=snapshot["access"]["actions_enabled"],
    )


@router.post("/voice")
async def agent_voice(
    audio: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    language_code: str = Form("auto", max_length=16),
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Transcribe a short owner voice request using the existing Sarvam adapter."""
    shop_id = resolve_shop_id(current_user)
    snapshot = _require_agent_access(db, shop_id, "voice")
    try:
        conversation_id = _parse_conversation_id(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    suffix = os.path.splitext(audio.filename or "")[1].lower()
    allowed_suffixes = {".wav", ".mp3", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm", ".ogg", ".flac"}
    if not content_type.startswith("audio/") and suffix not in allowed_suffixes:
        raise HTTPException(status_code=415, detail="Unsupported audio format.")
    if not content_type.startswith("audio/"):
        content_type = {
            ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
            ".mp4": "audio/mp4", ".mpeg": "audio/mpeg", ".mpga": "audio/mpeg",
            ".webm": "audio/webm", ".ogg": "audio/ogg", ".flac": "audio/flac",
        }.get(suffix, "audio/wav")
    payload = await audio.read(_MAX_AUDIO_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=422, detail="The uploaded audio is empty.")
    if len(payload) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio must be 8 MB or smaller.")

    try:
        # Do not bias the speech recognizer with this shop's product catalog.
        # The follow-on chat/voice-billing AI must first understand what the
        # owner actually said; inventory lookup belongs after extraction.
        from inventory import _ASR_NO_SPEECH_MESSAGE
        from voice_asr_guard import assess_transcription

        transcription = await run_in_threadpool(
            transcribe_with_sarvam,
            audio_bytes=payload,
            filename=(audio.filename or "owner-voice-audio")[:120],
            content_type=content_type,
            language_code=language_code,
            keyterms=[],
        )
    except SarvamSpeechError as exc:
        status = int(exc.status_code or 503)
        if status < 400 or status > 599:
            status = 503
        raise HTTPException(status_code=status, detail="Voice transcription is temporarily unavailable.") from exc

    transcript = str(transcription.get("transcript") or "").strip()
    verdict = assess_transcription({"text": transcript}, catalog_names=[])
    if not verdict.accepted:
        raise HTTPException(status_code=422, detail=_ASR_NO_SPEECH_MESSAGE)
    transcript = verdict.text
    detected_language = app_language_code(transcription.get("language_code")) or language_code
    effective_language = language_code
    if language_code.strip().lower() in {"", "auto", "und"} and detected_language:
        effective_language = detected_language
    result = await run_chat_turn(
        db,
        shop_id=shop_id,
        message=transcript,
        conversation_id=conversation_id,
        language_code=effective_language,
        allow_actions=snapshot["access"]["actions_enabled"],
    )
    result["transcription"] = {
        "transcript": transcript,
        "language_code": detected_language,
        "provider": "Sarvam AI",
    }
    return result


@router.post("/speech")
async def agent_speech(
    data: AgentSpeechRequest,
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    """Synthesize a bounded assistant response as a WAV stream."""
    _require_agent_access(db, resolve_shop_id(current_user), "voice")
    try:
        result = await run_in_threadpool(
            synthesize_with_sarvam,
            text=data.text,
            language_code=data.language_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SarvamTTSError as exc:
        status = int(exc.status_code or 503)
        if status < 400 or status > 599:
            status = 503
        raise HTTPException(status_code=status, detail="Speech synthesis is temporarily unavailable.") from exc

    return Response(
        content=result["audio_bytes"],
        media_type=result["content_type"],
        headers={
            "Cache-Control": "no-store",
            "X-Speech-Language": result["language_code"],
            "X-Speech-Model": result["model"],
            "X-Speech-Request-ID": result["request_id"],
        },
    )


@router.get("/conversations")
def agent_conversations(
    limit: int = Query(30, ge=1, le=50),
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    return list_conversations(db, shop_id=resolve_shop_id(current_user), limit=limit)


@router.get("/conversations/{conversation_id}/messages")
def agent_conversation_messages(
    conversation_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    conversation_id = _parse_conversation_id(conversation_id)
    return get_conversation_messages(
        db,
        shop_id=resolve_shop_id(current_user),
        conversation_id=conversation_id,
        limit=limit,
    )


@router.delete("/conversations/{conversation_id}")
def agent_delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    conversation_id = _parse_conversation_id(conversation_id)
    return delete_conversation(
        db,
        shop_id=resolve_shop_id(current_user),
        conversation_id=conversation_id,
    )


@router.get("/actions/pending")
def agent_pending_actions(
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    shop_id = resolve_shop_id(current_user)
    rows = (
        db.query(AgentPendingAction)
        .filter(
            AgentPendingAction.user_id == shop_id,
            AgentPendingAction.status == "PENDING",
            AgentPendingAction.expires_at > datetime.utcnow(),
        )
        .order_by(AgentPendingAction.created_at.desc())
        .limit(30)
        .all()
    )
    return {
        "actions": [
            {
                "action_id": row.id,
                "action_type": row.action_type,
                "status": row.status,
                "preview_hash": row.preview_hash,
                "preview": row.preview,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            }
            for row in rows
        ]
    }


@router.post("/actions/{action_id}/confirm")
def confirm_agent_action(
    action_id: str,
    data: AgentConfirmRequest,
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    try:
        action_id = str(uuid.UUID(action_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="action_id must be a UUID") from exc
    shop_id = resolve_shop_id(current_user)
    _require_agent_access(db, shop_id, "actions")
    return confirm_agent_action(
        db,
        shop_id=shop_id,
        current_user=current_user,
        action_id=action_id,
        supplied_preview_hash=data.preview_hash,
    )


@router.post("/actions/{action_id}/cancel")
def cancel_agent_action(
    action_id: str,
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    try:
        action_id = str(uuid.UUID(action_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="action_id must be a UUID") from exc
    shop_id = resolve_shop_id(current_user)
    action = db.query(AgentPendingAction).filter(
        AgentPendingAction.id == action_id,
        AgentPendingAction.user_id == shop_id,
    ).with_for_update().first()
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found.")
    if action.status == "CANCELLED":
        return {"success": True, "action_id": action_id, "status": "CANCELLED"}
    if action.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Action cannot be cancelled in state {action.status}.")
    action.status = "CANCELLED"
    action.updated_at = datetime.utcnow()
    db.flush()
    return {"success": True, "action_id": action_id, "status": "CANCELLED"}
