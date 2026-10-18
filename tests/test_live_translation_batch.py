import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


class _FakeResponse:
    def __init__(self, translations):
        self._translations = translations

    def raise_for_status(self):
        return None

    def json(self):
        return {"translations": self._translations}


def _reset_translation_cache(module):
    with module._DISPLAY_TRANSLATION_CACHE_LOCK:
        module._DISPLAY_TRANSLATION_CACHE.clear()


def test_live_translation_batch_route_is_registered():
    from query_retrival import app

    routes = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in app.routes
    }
    assert ("/askquery/translate-batch", frozenset({"POST"})) in routes


def test_live_translation_batch_uses_open_source_service_not_groq(monkeypatch):
    import query_retrival

    _reset_translation_cache(query_retrival)
    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "")
    monkeypatch.setenv("INDIC_SPEECH_SERVICE_URL", "https://indic.example")
    monkeypatch.setenv("INDIC_SPEECH_SERVICE_API_KEY", "service-test-key")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _FakeResponse(["మొదటి వాక్యం", "రెండవ వాక్యం"])

    monkeypatch.setattr(query_retrival.httpx, "post", fake_post)
    result = query_retrival._translate_text_batch_to_language(
        ["A first sentence", "A second sentence"],
        "te",
    )

    assert result == ["మొదటి వాక్యం", "రెండవ వాక్యం"]
    assert len(calls) == 1
    assert calls[0][0] == "https://indic.example/translate-text-batch"
    assert calls[0][1]["json"] == {
        "language_code": "te",
        "texts": ["A first sentence", "A second sentence"],
    }
    assert calls[0][1]["headers"]["X-Speech-Service-Key"] == "service-test-key"
    assert calls[0][1]["timeout"] == 90.0


def test_successful_batch_translation_is_cached(monkeypatch):
    import query_retrival

    _reset_translation_cache(query_retrival)
    monkeypatch.setenv("INDIC_SPEECH_SERVICE_URL", "https://indic.example")
    monkeypatch.setenv("INDIC_SPEECH_SERVICE_API_KEY", "service-test-key")
    calls = []

    def fake_post(_url, **kwargs):
        calls.append(kwargs["json"])
        return _FakeResponse(["పరీక్ష అనువాదం"])

    monkeypatch.setattr(query_retrival.httpx, "post", fake_post)
    first = query_retrival._translate_text_batch_to_language(["A test translation"], "te")
    second = query_retrival._translate_text_batch_to_language(["A test translation"], "te")

    assert first == second == ["పరీక్ష అనువాదం"]
    assert len(calls) == 1


def test_english_translation_is_identity_without_any_service(monkeypatch):
    import query_retrival

    monkeypatch.delenv("INDIC_SPEECH_SERVICE_URL", raising=False)
    monkeypatch.delenv("INDIC_SPEECH_SERVICE_API_KEY", raising=False)
    inputs = ["Product name", "Stock: 12", "₹300"]
    assert query_retrival._translate_text_batch_to_language(inputs, "en") == inputs


def test_missing_translation_service_fails_soft_without_using_groq(monkeypatch):
    import query_retrival

    _reset_translation_cache(query_retrival)
    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "deliberately-limited-key")
    monkeypatch.delenv("INDIC_SPEECH_SERVICE_URL", raising=False)
    monkeypatch.delenv("INDIC_SPEECH_SERVICE_API_KEY", raising=False)
    inputs = ["Worker attendance", "Monthly salary"]
    assert query_retrival._translate_text_batch_to_language(inputs, "te") == inputs


def test_answer_translation_uses_open_source_service(monkeypatch):
    import query_retrival

    _reset_translation_cache(query_retrival)
    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "")
    monkeypatch.setenv("INDIC_SPEECH_SERVICE_URL", "https://indic.example")
    monkeypatch.setenv("INDIC_SPEECH_SERVICE_API_KEY", "service-test-key")
    calls = []

    def fake_post(_url, **kwargs):
        calls.append(kwargs["json"])
        return _FakeResponse(["మీరు చేసిన అమ్మకాలు 12 ఉన్నాయి."])

    monkeypatch.setattr(query_retrival.httpx, "post", fake_post)
    result = query_retrival._translate_answer_to_language("You made 12 sales.", "te")

    assert result == "మీరు చేసిన అమ్మకాలు 12 ఉన్నాయి."
    assert len(calls) == 1


def test_live_translation_batch_rejects_oversized_batch_before_translation():
    from query_retrival import (
        TRANSLATION_BATCH_MAX_ITEMS,
        translate_ask_query_text_batch,
    )

    payload = {
        "language_code": "te",
        "texts": ["short"] * (TRANSLATION_BATCH_MAX_ITEMS + 1),
    }
    with pytest.raises(HTTPException) as error:
        asyncio.run(translate_ask_query_text_batch(payload, user_id=1))

    assert error.value.status_code == 413


def test_live_translation_batch_rejects_invalid_language_before_translation():
    from query_retrival import translate_ask_query_text_batch

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            translate_ask_query_text_batch(
                {"language_code": "unsupported", "texts": ["Hello"]},
                user_id=1,
            )
        )

    assert error.value.status_code == 422
