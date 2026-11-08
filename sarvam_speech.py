"""Shared Sarvam Saaras v4 speech-to-text adapter for Retail Mind."""
from __future__ import annotations
import json
import os
from typing import Any
import httpx

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_STT_MODEL = (os.getenv("SARVAM_STT_MODEL") or "saaras:v4").strip()

_LANGUAGE_CODES = {
    "as": "as-IN", "bn": "bn-IN", "brx": "brx-IN", "doi": "doi-IN",
    "en": "en-IN", "gu": "gu-IN", "hi": "hi-IN", "kn": "kn-IN",
    "kok": "kok-IN", "ks": "ks-IN", "mai": "mai-IN", "ml": "ml-IN",
    "mni": "mni-IN", "mr": "mr-IN", "ne": "ne-IN", "or": "od-IN",
    "od": "od-IN", "pa": "pa-IN", "sa": "sa-IN", "sat": "sat-IN",
    "sd": "sd-IN", "ta": "ta-IN", "te": "te-IN", "ur": "ur-IN",
}
_SARVAM_TO_APP = {value.lower(): key for key, value in _LANGUAGE_CODES.items()}
_SARVAM_TO_APP["od-in"] = "or"

class SarvamSpeechError(RuntimeError):
    """Provider error carrying only a safe status code."""
    def __init__(self, status_code: int | None, message: str = "Sarvam speech recognition failed"):
        super().__init__(message)
        self.status_code = status_code

def sarvam_language_code(value: str | None) -> str:
    """Convert app locale codes to Sarvam BCP-47; unknown asks Sarvam to detect."""
    code = str(value or "unknown").strip().lower()
    if code in {"", "auto", "und", "unknown"}:
        return "unknown"
    if code in _LANGUAGE_CODES:
        return _LANGUAGE_CODES[code]
    supported = {v.lower() for v in _LANGUAGE_CODES.values()}
    return code if code in supported else "unknown"

def app_language_code(value: str | None) -> str | None:
    """Convert Sarvam detected locale to the app's short locale code."""
    code = str(value or "").strip().lower()
    if not code or code == "unknown":
        return None
    if code in _SARVAM_TO_APP:
        return _SARVAM_TO_APP[code]
    short = code.split("-", 1)[0]
    return "or" if short == "od" else short

def transcribe_with_sarvam(
    *,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    language_code: str | None = "auto",
    keyterms: list[str] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Transcribe audio with Saaras v4 and optional merchant-specific keyterms."""
    key = (api_key or os.getenv("SARVAM_API_KEY") or "").strip()
    if not key:
        raise SarvamSpeechError(None, "SARVAM_API_KEY is not configured")
    terms = []
    seen = set()
    for term in keyterms or []:
        cleaned = " ".join(str(term or "").split()).strip()
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            terms.append(cleaned[:64])
        if len(terms) >= 50:
            break
    data = {
        "model": SARVAM_STT_MODEL,
        "language_code": sarvam_language_code(language_code),
        "mode": "transcribe",
    }
    if terms:
        data["keyterms"] = json.dumps(terms, ensure_ascii=False)
    try:
        response = httpx.post(
            SARVAM_STT_URL,
            headers={"api-subscription-key": key},
            data=data,
            files={"file": (filename or "recording.wav", audio_bytes, content_type or "audio/wav")},
            timeout=httpx.Timeout(45.0, connect=8.0),
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise SarvamSpeechError(504, "Sarvam speech recognition timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise SarvamSpeechError(exc.response.status_code) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise SarvamSpeechError(None) from exc
    transcript = str(payload.get("transcript") or "").strip()
    if not transcript:
        raise SarvamSpeechError(422, "Sarvam returned an empty transcript")
    return {
        "transcript": transcript,
        "language_code": str(payload.get("language_code") or "").strip() or None,
        "request_id": payload.get("request_id"),
        "model": SARVAM_STT_MODEL,
        "provider": "Sarvam AI",
    }
