def test_voice_query_route_is_registered_and_has_full_language_set():
    from query_retrival import VOICE_LANGUAGE_CODES, app

    routes = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in app.routes
    }
    assert ("/askquery/voice", frozenset({"POST"})) in routes
    assert "en" in VOICE_LANGUAGE_CODES
    # 22 scheduled Indian languages plus English.
    assert len(VOICE_LANGUAGE_CODES) == 23
    assert {
        "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
        "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta",
        "te", "ur", "en",
    } <= VOICE_LANGUAGE_CODES


def test_speech_service_language_mappings_cover_all_22_scheduled_languages():
    from speech_service.app import INDIC_LANGUAGE_MAP

    assert len(INDIC_LANGUAGE_MAP) == 22
    assert INDIC_LANGUAGE_MAP["brx"] == ("brx", "brx_Deva")
    assert INDIC_LANGUAGE_MAP["te"] == ("te", "tel_Telu")
    assert INDIC_LANGUAGE_MAP["ta"] == ("ta", "tam_Taml")
    assert INDIC_LANGUAGE_MAP["hi"] == ("hi", "hin_Deva")


def test_text_query_route_accepts_language_and_translate_helper_is_registered():
    import inspect
    from query_retrival import _translate_query_to_english, app, ask_query

    assert callable(_translate_query_to_english)
    assert "language_code" in inspect.signature(ask_query).parameters
    routes = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in app.routes
    }
    assert ("/askquery", frozenset({"POST"})) in routes


def test_translate_query_uses_existing_llm_and_returns_english(monkeypatch):
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = {}

    def fake_create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="English translation: How much were sales yesterday?"
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

    translated = query_retrival._translate_query_to_english(
        "నిన్న ఎంత అమ్మకాలు జరిగాయి?",
        "te",
    )

    assert translated == "How much were sales yesterday?"
    assert calls["stream"] is False
    assert calls["temperature"] == 0.0
    assert calls["messages"][1]["content"].startswith("Source language: Telugu")

