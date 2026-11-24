"""Agent voice recognition must not be biased by the shop product catalogue."""
import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "retail-mind-agent-ci-only-not-for-production")

import pytest

import voice_asr_guard
from agentic import routes as routes_module


class _Upload:
    filename = "owner-voice.wav"
    content_type = "audio/wav"

    async def read(self, _limit):
        return b"fake-audio-bytes"


def test_agent_voice_uses_catalog_blind_asr_and_preserves_detected_language(monkeypatch):
    monkeypatch.setenv("RETAIL_MIND_AGENT_ENABLED", "true")
    monkeypatch.setattr(routes_module, "resolve_shop_id", lambda _user: 42)
    monkeypatch.setattr(
        routes_module,
        "_require_agent_access",
        lambda _db, _shop_id, _feature: {
            "access": {"assistant_enabled": True, "voice_enabled": True, "actions_enabled": False}
        },
    )

    captured = {}

    async def fake_run_in_threadpool(function, **kwargs):
        captured["transcriber"] = function
        captured["transcribe_kwargs"] = kwargs
        return {
            "transcript": "ఒక సబ్బు 30",
            "language_code": "te-IN",
            "model": "saaras:v4",
        }

    def fake_assess(payload, *, catalog_names):
        captured["assessment_catalog_names"] = catalog_names
        return SimpleNamespace(accepted=True, text=payload["text"])

    async def fake_chat_turn(db, *, shop_id, message, conversation_id, language_code, allow_actions):
        captured["chat"] = {
            "shop_id": shop_id,
            "message": message,
            "conversation_id": conversation_id,
            "language_code": language_code,
            "allow_actions": allow_actions,
        }
        return {"success": True, "response": "Draft received"}

    monkeypatch.setattr(routes_module, "run_in_threadpool", fake_run_in_threadpool)
    monkeypatch.setattr(voice_asr_guard, "assess_transcription", fake_assess)
    monkeypatch.setattr(routes_module, "run_chat_turn", fake_chat_turn)

    result = asyncio.run(routes_module.agent_voice(
        _Upload(),
        conversation_id=None,
        language_code="auto",
        current_user={"id": 42},
        db=object(),
    ))

    assert captured["transcriber"] is routes_module.transcribe_with_sarvam
    assert captured["transcribe_kwargs"]["keyterms"] == []
    assert captured["assessment_catalog_names"] == []
    assert captured["chat"] == {
        "shop_id": 42,
        "message": "ఒక సబ్బు 30",
        "conversation_id": None,
        "language_code": "te",
        "allow_actions": False,
    }
    assert result["transcription"]["transcript"] == "ఒక సబ్బు 30"
    assert result["transcription"]["provider"] == "Sarvam AI"
