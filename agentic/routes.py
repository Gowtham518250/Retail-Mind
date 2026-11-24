"""Owner-authenticated Retail Mind AI assistant API."""
from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from db import get_db
from models import AgentPendingAction
from security import owner_only, resolve_shop_id
from sarvam_speech import SarvamSpeechError, app_language_code, transcribe_with_sarvam

from .registry import list_capabilities
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


@router.get("/capabilities")
def get_agent_capabilities(_owner: dict = Depends(owner_only)):
    """Describe implemented and intentionally disabled agent capabilities."""
    capabilities = list_capabilities()
    flag_enabled = os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    groq_ready = bool((os.getenv("GROQ_API_KEY") or "").strip())
    enabled = flag_enabled and groq_ready
    status = (
        "enabled" if enabled
        else "provider_configuration_missing" if flag_enabled
        else "disabled_by_configuration"
    )
    return {
        "status": status,
        "execution_enabled": enabled,
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


@router.post("/chat")
async def agent_chat(
    data: AgentChatRequest,
    current_user: dict = Depends(owner_only),
    db: Session = Depends(get_db),
):
    shop_id = resolve_shop_id(current_user)
    return await run_chat_turn(
        db,
        shop_id=shop_id,
        message=data.message,
        conversation_id=data.conversation_id,
        language_code=data.language_code,
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
    if os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=503, detail="The Retail Mind AI assistant is not enabled on this deployment.")
    shop_id = resolve_shop_id(current_user)
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
):
    """Synthesize a bounded assistant response as a WAV stream."""
    if os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=503, detail="The Retail Mind AI assistant is not enabled on this deployment.")
    resolve_shop_id(current_user)
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
    if os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=503, detail="AI bill confirmation is disabled on this deployment.")
    shop_id = resolve_shop_id(current_user)
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
