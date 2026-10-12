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
    assert "reasoning_effort" not in calls
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



def test_deterministic_query_planner_avoids_extra_llm_for_simple_kpis():
    from query_retrival import _can_use_fast_business_query, _make_deterministic_query_plan

    plan = _make_deterministic_query_plan("What were my total sales yesterday?")
    assert plan["planner"] == "deterministic"
    assert plan["intent"] == "aggregate"
    assert plan["metric"] == "sales_amount"
    assert plan["confidence"] >= 0.9
    assert _can_use_fast_business_query(
        "What were my total sales yesterday?",
        {"kind": "exact", "label": "yesterday"},
    )


def test_deterministic_query_planner_keeps_dimensional_questions_on_rag_sql():
    from query_retrival import _can_use_fast_business_query, _make_deterministic_query_plan

    query = "Show total sales by product this month"
    plan = _make_deterministic_query_plan(query)
    assert plan["planner"] == "deterministic"
    assert plan["intent"] == "general"
    assert plan["confidence"] == 0.0
    assert not _can_use_fast_business_query(
        query,
        {"kind": "range", "label": "this month"},
    )


def test_deterministic_query_planner_does_not_fast_path_ambiguous_mixed_metric():
    from query_retrival import _can_use_fast_business_query

    assert not _can_use_fast_business_query(
        "Show total sales and expenses",
        {"kind": "unspecified", "label": "not specified"},
    )
    assert not _can_use_fast_business_query(
        "What is my total profit?",
        {"kind": "unspecified", "label": "not specified"},
    )



def test_mixed_sales_and_inventory_questions_never_use_kpi_fast_path():
    from query_retrival import _can_use_fast_business_query

    for query in (
        "What are my total sales and stock value?",
        "Show total sales and payments received",
        "What is my total sales tax?",
    ):
        assert not _can_use_fast_business_query(
            query,
            {"kind": "unspecified", "label": "not specified"},
        )



def test_combined_query_translation_and_classification_uses_one_chat_call(monkeypatch):
    from types import SimpleNamespace
    import json
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps({
                            "english_query": "What were my total sales yesterday?",
                            "intent": "aggregate",
                            "metric": "sales_amount",
                            "confidence": 0.98,
                        })
                    )
                )
            ]
        )

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))),
    )

    result = query_retrival._translate_query_and_classify(
        "నిన్న నా మొత్తం అమ్మకాలు ఎంత?",
        "te",
    )

    assert result["english_query"] == "What were my total sales yesterday?"
    assert result["classification"]["intent"] == "aggregate"
    assert result["classification"]["metric"] == "sales_amount"
    assert result["classification"]["confidence"] == 0.98
    assert len(calls) == 1
    assert calls[0]["stream"] is False
    assert "reasoning_effort" not in calls[0]
    assert "classify" in calls[0]["messages"][0]["content"].lower()


def test_common_answer_templates_do_not_call_groq(monkeypatch):
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "")
    def unexpected_call(**kwargs):
        raise AssertionError("A predefined summary must not call Groq")

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=unexpected_call))),
    )

    assert query_retrival._translate_answer_to_language("The total is ₹12,450.", "te") == "మొత్తం ₹12,450."
    assert query_retrival._translate_answer_to_language(
        "Found 7 matching result(s).", "hi"
    ) == "7 मिलते-जुलते रिकॉर्ड मिले।"
    assert query_retrival._translate_answer_to_language(
        "No matching records were found for your question.", "ta"
    ) == "உங்கள் கேள்விக்குப் பொருந்தும் பதிவுகள் எதுவும் இல்லை."


def test_combined_query_translation_keeps_plain_text_provider_fallback(monkeypatch):
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(
                            content="English translation: How much were sales yesterday?"
                        ))]
                    )
                )
            )
        ),
    )

    result = query_retrival._translate_query_and_classify(
        "నిన్న ఎంత అమ్మకాలు జరిగాయి?", "te"
    )
    assert result["english_query"] == "How much were sales yesterday?"
    assert result["classification"]["source"] == "deterministic_fallback"


def test_query_path_has_no_separate_llm_planner(monkeypatch):
    import inspect
    import query_retrival

    source = inspect.getsource(query_retrival.ask_query)
    assert "_translate_query_and_classify" in source
    assert "_make_query_plan(" not in source
    assert not hasattr(query_retrival, "_make_query_plan")

def test_invoices_schema_repair_fixes_wrong_tenant_and_date_columns():
    from query_retrival import _repair_known_schema_aliases

    broken = (
        "SELECT SUM(total_amount) AS total_sales FROM invoices "
        "WHERE shopkeeper_id = :user_id AND business_date = :business_date "
        "AND status NOT IN ('CANCELLED', 'DRAFT')"
    )
    repaired = _repair_known_schema_aliases(broken)

    assert "shopkeeper_id" not in repaired
    assert "WHERE user_id = :user_id" in repaired
    assert "invoice_date = :business_date" in repaired
    # The bind parameter must not be accidentally renamed.
    assert ":business_date" in repaired


def test_invoices_schema_repair_handles_table_aliases_without_touching_sales():
    from query_retrival import _repair_known_schema_aliases

    invoice_sql = (
        "SELECT SUM(i.total_amount) FROM invoices i "
        "WHERE i.shopkeeper_id = :user_id AND i.business_date = :business_date"
    )
    repaired_invoice = _repair_known_schema_aliases(invoice_sql)
    assert "i.user_id = :user_id" in repaired_invoice
    assert "i.invoice_date = :business_date" in repaired_invoice

    sales_sql = (
        "SELECT SUM(total) FROM sales "
        "WHERE shopkeeper_id = :user_id AND sale_date = :business_date"
    )
    assert _repair_known_schema_aliases(sales_sql) == sales_sql


def test_uncertain_telugu_sales_translation_gets_high_reasoning_verification(monkeypatch):
    from types import SimpleNamespace
    import json
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            answer = {
                "english_query": "Could you tell me about today's sales details?",
                "intent": "general",
                "metric": "other",
                "confidence": 0.58,
            }
        else:
            answer = {
                "english_query": "Can you tell me roughly how much sales my shop made today?",
                "intent": "aggregate",
                "metric": "sales_amount",
                "confidence": 0.99,
            }
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answer)))]
        )

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))),
    )

    result = query_retrival._translate_query_and_classify(
        "నాకు ఈరోజు సేల్స్ ఎంత అమ్ముడయ్యాయో కొద్దిగా చెప్పగలవా?",
        "te",
    )

    assert len(calls) == 2
    assert calls[1]["model"] == "openai/gpt-oss-120b"
    assert "reasoning_effort" not in calls[1]  # Groq SDK 0.10.0 rejects this keyword
    assert calls[1]["response_format"] == {"type": "json_object"}
    assert result["english_query"] == "Can you tell me roughly how much sales my shop made today?"
    assert result["classification"]["intent"] == "aggregate"
    assert result["classification"]["metric"] == "sales_amount"
    assert result["classification"]["confidence"] == 0.99
    assert result["classification"]["source"] == "high_reasoning_translation_verifier"


def test_failed_sql_repair_requires_read_only_tenant_scoped_sql(monkeypatch):
    from types import SimpleNamespace
    import json
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    answers = [
        {"sql": "SELECT SUM(total_amount) FROM invoices WHERE user_id = :user_id AND invoice_date = :business_date"},
        {"sql": "UPDATE invoices SET total_amount = 0"},
    ]
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(answers[len(calls) - 1])))]
        )

    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))),
    )

    repaired = query_retrival._repair_failed_sql_with_groq(
        question="How much sales did I make today?",
        failed_sql="SELECT SUM(total_amount) FROM invoices WHERE shopkeeper_id = :user_id",
        execution_error='column "shopkeeper_id" does not exist',
        schema_context="TABLE invoices: user_id, invoice_date, total_amount",
    )
    assert repaired is not None
    assert "user_id = :user_id" in repaired

    rejected = query_retrival._repair_failed_sql_with_groq(
        question="How much sales did I make today?",
        failed_sql="SELECT broken",
        execution_error="syntax error",
        schema_context="TABLE invoices: user_id, invoice_date, total_amount",
    )
    assert rejected is None

def test_low_confidence_translated_question_stops_before_sql_generation(monkeypatch):
    import query_retrival
    from fastapi import HTTPException

    monkeypatch.setattr(
        query_retrival,
        "_translate_query_and_classify",
        lambda query, language_code: {
            "english_query": "A vague translation",
            "classification": {
                "intent": "general",
                "metric": "other",
                "confidence": 0.42,
                "source": "high_reasoning_translation_verifier",
            },
        },
    )

    def unexpected_schema_search(_query):
        raise AssertionError("SQL/RAG must not run while translation confidence is low")

    monkeypatch.setattr(query_retrival, "_cached_schema_search", unexpected_schema_search)

    import asyncio

    try:
        asyncio.run(query_retrival.ask_query(
            query="ప్రశ్న స్పష్టంగా అర్థం కాలేదు",
            language_code="te",
            db=object(),
            user_id=7,
        ))
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "no shop data was queried" in exc.detail.lower()
    else:
        raise AssertionError("Low-confidence translated questions must request clarification")

