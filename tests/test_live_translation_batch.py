import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def test_live_translation_batch_route_is_registered():
    from query_retrival import app

    routes = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in app.routes
    }
    assert ("/askquery/translate-batch", frozenset({"POST"})) in routes


def test_live_translation_batch_translates_in_order_with_one_model_call(monkeypatch):
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {"translations": ["మొదటి వాక్యం", "రెండవ వాక్యం"]},
                            ensure_ascii=False,
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=fake_create),
            ),
        ),
    )

    result = query_retrival._translate_text_batch_to_language(
        ["A first sentence", "A second sentence"],
        "te",
    )

    assert result == ["మొదటి వాక్యం", "రెండవ వాక్యం"]
    assert len(calls) == 1
    assert calls[0]["stream"] is False
    assert calls[0]["temperature"] == 0.0
    assert "exact same order" in calls[0]["messages"][0]["content"]


def test_live_translation_batch_english_is_identity_without_llm(monkeypatch):
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "")
    inputs = ["Product name", "Stock: 12", "₹300"]
    assert query_retrival._translate_text_batch_to_language(inputs, "en") == inputs


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


def test_live_translation_batch_caches_repeated_text_without_second_model_call(monkeypatch):
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        payload = json.loads(kwargs["messages"][1]["content"].split("\n", 1)[1])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {"translations": [f"translated:{value}" for value in payload["texts"]]},
                            ensure_ascii=False,
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))),
    )
    text_value = "Retail Mind cache test unique 20261018"

    first = query_retrival._translate_text_batch_to_language([text_value], "te")
    second = query_retrival._translate_text_batch_to_language([text_value], "te")

    assert first == [f"translated:{text_value}"]
    assert second == first
    assert len(calls) == 1


def test_live_translation_batch_deduplicates_duplicate_items(monkeypatch):
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps({"translations": ["తెలుగు"]}, ensure_ascii=False)
                    )
                )
            ]
        )

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))),
    )
    text_value = "duplicate item unique 20261018"
    result = query_retrival._translate_text_batch_to_language(
        [text_value, text_value], "te"
    )

    assert result == ["తెలుగు", "తెలుగు"]
    assert len(calls) == 1
    assert json.loads(calls[0]["messages"][1]["content"].split("\n", 1)[1])["texts"] == [text_value]
