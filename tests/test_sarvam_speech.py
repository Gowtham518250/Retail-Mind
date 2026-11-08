import json
from types import SimpleNamespace

import pytest

import sarvam_speech


def test_sarvam_request_uses_v4_auth_language_and_merchant_keyterms(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"transcript": "రెండు కిలోల బియ్యం", "language_code": "te-IN", "request_id": "req-1"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(sarvam_speech.httpx, "post", fake_post)
    result = sarvam_speech.transcribe_with_sarvam(
        audio_bytes=b"audio",
        filename="bill.wav",
        content_type="audio/wav",
        language_code="te",
        keyterms=["Rice", "Rice", "Sona Masoori"],
        api_key="test-secret",
    )

    assert captured["url"] == "https://api.sarvam.ai/speech-to-text"
    assert captured["headers"]["api-subscription-key"] == "test-secret"
    assert captured["data"]["model"] == "saaras:v4"
    assert captured["data"]["language_code"] == "te-IN"
    assert json.loads(captured["data"]["keyterms"]) == ["Rice", "Sona Masoori"]
    assert result["transcript"] == "రెండు కిలోల బియ్యం"
    assert result["provider"] == "Sarvam AI"


def test_sarvam_auto_language_uses_unknown(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"transcript": "hello", "language_code": "en-IN"}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(sarvam_speech.httpx, "post", fake_post)
    sarvam_speech.transcribe_with_sarvam(
        audio_bytes=b"audio",
        filename="question.m4a",
        content_type="audio/mp4",
        language_code="auto",
        api_key="test-secret",
    )
    assert captured["data"]["language_code"] == "unknown"
    assert "keyterms" not in captured["data"]


def test_sarvam_rejects_missing_api_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with pytest.raises(sarvam_speech.SarvamSpeechError):
        sarvam_speech.transcribe_with_sarvam(
            audio_bytes=b"audio",
            filename="question.wav",
            content_type="audio/wav",
        )
