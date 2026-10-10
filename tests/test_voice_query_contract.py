def test_voice_query_route_is_registered_and_has_full_language_set():
    from query_retrival import VOICE_LANGUAGE_CODES, app

    routes = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in app.routes
    }
    assert ("/askquery/voice", frozenset({"POST"})) in routes
    assert ("/askquery/transcribe", frozenset({"POST"})) in routes
    assert "en" in VOICE_LANGUAGE_CODES
    # 22 scheduled Indian languages plus English.
    assert len(VOICE_LANGUAGE_CODES) == 23
    assert {
        "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
        "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta",
        "te", "ur", "en",
    } <= VOICE_LANGUAGE_CODES


def test_groq_whisper_language_handling_covers_selected_voice_codes():
    from query_retrival import GROQ_STT_LANGUAGE_CODES, VOICE_LANGUAGE_CODES

    assert "hi" in GROQ_STT_LANGUAGE_CODES
    assert "te" in GROQ_STT_LANGUAGE_CODES
    assert "ta" in GROQ_STT_LANGUAGE_CODES
    assert "brx" in VOICE_LANGUAGE_CODES
    assert "brx" not in GROQ_STT_LANGUAGE_CODES  # let Whisper auto-detect three-letter codes


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



def test_transcription_only_endpoint_is_registered():
    from query_retrival import app

    routes = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in app.routes
    }
    assert ("/askquery/transcribe", frozenset({"POST"})) in routes


def test_groq_audio_transcription_returns_spoken_text(monkeypatch):
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = {}

    def fake_create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(text="నిన్న నా అమ్మకాలు ఎంత?")

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(
            audio=SimpleNamespace(
                transcriptions=SimpleNamespace(create=fake_create),
            ),
        ),
    )

    transcript = query_retrival._transcribe_audio_with_groq(
        b"test-wave-bytes",
        "question.wav",
        "audio/wav",
        "te",
    )

    assert transcript == "నిన్న నా అమ్మకాలు ఎంత?"
    assert calls["model"] == query_retrival.GROQ_STT_MODEL
    assert calls["language"] == "te"
    assert calls["response_format"] == "json"
    assert calls["temperature"] == 0.0
    assert calls["file"][0] == "question.wav"


def test_three_letter_language_uses_whisper_language_detection(monkeypatch):
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = {}

    def fake_create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(text="recognised words")

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(
            audio=SimpleNamespace(
                transcriptions=SimpleNamespace(create=fake_create),
            ),
        ),
    )

    assert query_retrival._transcribe_audio_with_groq(
        b"test-wave-bytes", "question.wav", "audio/wav", "brx"
    ) == "recognised words"
    assert "language" not in calls



def test_answer_translation_route_is_registered():
    from query_retrival import app

    routes = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in app.routes
    }
    assert ("/askquery/translate-answer", frozenset({"POST"})) in routes


def test_translate_answer_uses_existing_llm_and_preserves_target_language(monkeypatch):
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = {}

    def fake_create(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="మీ మొత్తం అమ్మకాలు ₹12,450.")
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

    translated = query_retrival._translate_answer_to_language(
        "Your total sales are ₹12,450.",
        "te",
    )

    assert translated == "మీ మొత్తం అమ్మకాలు ₹12,450."
    assert calls["stream"] is False
    assert calls["temperature"] == 0.0
    assert "Telugu" in calls["messages"][0]["content"]
    assert "preserve all numbers" in calls["messages"][0]["content"].lower()


def test_answer_translation_returns_english_without_llm(monkeypatch):
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "")
    assert query_retrival._translate_answer_to_language("Total sales: ₹12,450", "en") == "Total sales: ₹12,450"
