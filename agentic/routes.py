"""Owner-authenticated Retail Mind AI assistant API."""
from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from db import get_db
from models import AgentPendingAction
from security import owner_only, resolve_shop_id
from sarvam_speech import SarvamSpeechError, app_language_code, transcribe_with_sarvam

from .registry import list_capabilities
from .service import (
    confirm_invoice_action,
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


def _validate_conversation_id(value: Optional[str]) -> Optional[str]:
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
        return _validate_conversation_id(value)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value):
        cleaned = " ".join(str(value or "").split())
        if not cleaned:
            raise ValueError("message cannot be blank")
        return cleaned


class AgentConfirmRequest(BaseModel):
    preview_hash: str = Field(..., min_length=64, max_length=64)


@router.get("/capabilities")
def get_agent_capabilities(_owner: dict = Depends(owner_only)):
    """Describe implemented and intentionally disabled agent capabilities."""
    capabilities = list_capabilities()
    enabled = os.getenv("RETAIL_MIND_AGENT_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }
    return {
        "status": "enabled" if enabled else "disabled_by_configuration",
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
    shop_id = resolve_shop_id(current_user)
    conversation_id = _validate_conversation_id(conversation_id)
    content_type = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in _ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio format.")
    payload = await audio.read(_MAX_AUDIO_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=422, detail="The uploaded audio is empty.")
    if len(payload) > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio must be 8 MB or smaller.")

    try:
        transcription = await run_in_threadpool(
            transcribe_with_sarvam,
            audio_bytes=payload,
            filename=(audio.filename or "owner-voice-audio")[:120],
            content_type=content_type,
            language_code=language_code,
        )
    except SarvamSpeechError as exc:
        status = int(exc.status_code or 503)
        if status < 400 or status > 599:
            status = 503
        raise HTTPException(status_code=status, detail="Voice transcription is temporarily unavailable.") from exc

    transcript = str(transcription.get("transcript") or "").strip()
    detected_language = app_language_code(transcription.get("language_code")) or language_code
    result = await run_chat_turn(
        db,
        shop_id=shop_id,
        message=transcript,
        conversation_id=conversation_id,
        language_code=detected_language,
    )
    result["transcription"] = {
        "transcript": transcript,
        "language_code": detected_language,
        "provider": "Sarvam AI",
    }
    return result


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
    conversation_id = _validate_conversation_id(conversation_id)
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
    conversation_id = _validate_conversation_id(conversation_id)
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
            AgentPendingAction.expires_at > __import__("datetime").datetime.utcnow(),
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
    return confirm_invoice_action(
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
    action.updated_at = __import__("datetime").datetime.utcnow()
    db.flush()
    return {"success": True, "action_id": action_id, "status": "CANCELLED"}
