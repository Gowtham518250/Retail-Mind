"""Sarvam Bulbul REST text-to-speech adapter for Retail Mind.

Provider secrets remain server-side. Audio is returned only to authenticated
owners and is not persisted to the database.
"""
from __future__ import annotations
import base64
import binascii
import os
import re
from typing import Any
import httpx

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
MAX_TTS_TEXT_CHARS = 1800
MAX_TTS_AUDIO_BYTES = 5 * 1024 * 1024

_LANGUAGE_CODES = {
    "en": "en-IN", "hi": "hi-IN", "bn": "bn-IN", "ta": "ta-IN",
    "te": "te-IN", "kn": "kn-IN", "ml": "ml-IN", "mr": "mr-IN",
    "gu": "gu-IN", "pa": "pa-IN", "or": "od-IN", "od": "od-IN",
}


class SarvamTTSError(RuntimeError):
    """Safe provider exception without response bodies or credentials."""
    def __init__(self, status_code: int | None = None):
        super().__init__("Sarvam text-to-speech request failed")
        self.status_code = status_code


def sarvam_tts_language_code(value: str | None) -> str:
    code = str(value or "en").strip().lower().split("-", 1)[0]
    if code not in _LANGUAGE_CODES:
        raise ValueError("Choose one of the supported Indian languages.")
    return _LANGUAGE_CODES[code]


def clean_speech_text(value: str) -> str:
    text = str(value or "").replace(chr(96) * 3, " ")
    text = re.sub(r"\x60([^\x60]*)\x60", r"\\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[*_#>|~]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:MAX_TTS_TEXT_CHARS]


def synthesize_with_sarvam(*, text: str, language_code: str = "en", api_key: str | None = None) -> dict[str, Any]:
    key = (api_key or os.getenv("SARVAM_API_KEY") or "").strip()
    if not key:
        raise SarvamTTSError(None)
    cleaned = clean_speech_text(text)
    if not cleaned:
        raise ValueError("There is no text to speak.")
    language = sarvam_tts_language_code(language_code)
    model = (os.getenv("SARVAM_TTS_MODEL") or "bulbul:v3").strip()
    speaker = (os.getenv("SARVAM_TTS_SPEAKER") or "shubh").strip().lower()
    if model not in {"bulbul:v3", "bulbul:v4-flash"}:
        raise ValueError("Unsupported Sarvam TTS model configuration.")
    if not re.fullmatch(r"[a-z0-9_]{2,64}", speaker):
        raise ValueError("Invalid Sarvam TTS speaker configuration.")

    try:
        response = httpx.post(
            SARVAM_TTS_URL,
            headers={"api-subscription-key": key, "Accept": "application/json", "Content-Type": "application/json"},
            json={
                "text": cleaned,
                "model": model,
                "speaker": speaker,
                "language_code": language,
                "output_audio_codec": "wav",
                "speech_sample_rate": 22050,
            },
            timeout=httpx.Timeout(35.0, connect=8.0),
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise SarvamTTSError(504) from exc
    except httpx.HTTPStatusError as exc:
        raise SarvamTTSError(exc.response.status_code) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise SarvamTTSError(None) from exc

    audio_parts = payload.get("audios")
    if not isinstance(audio_parts, list) or not audio_parts:
        raise SarvamTTSError(502)
    encoded = "".join(str(part or "") for part in audio_parts)
    if not encoded or len(encoded) > (MAX_TTS_AUDIO_BYTES * 4 // 3 + 16):
        raise SarvamTTSError(502)
    try:
        audio_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SarvamTTSError(502) from exc
    if not audio_bytes or len(audio_bytes) > MAX_TTS_AUDIO_BYTES:
        raise SarvamTTSError(502)
    return {
        "audio_bytes": audio_bytes,
        "content_type": "audio/wav",
        "language_code": language,
        "model": model,
        "request_id": str(payload.get("request_id") or "")[:128],
    }
