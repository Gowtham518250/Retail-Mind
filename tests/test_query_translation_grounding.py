from types import SimpleNamespace

import query_retrival


def _capture(monkeypatch):
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        payload = (
            '{"english_query":"How much sugar is in stock?","intent":"aggregate",'
            '"metric":"stock","confidence":0.97,"translation_confidence":0.97}'
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
        )

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        query_retrival,
        "client",
        SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=fake_create)
            )
        ),
    )
    return calls


def test_translation_prompt_covers_supported_languages(monkeypatch):
    calls = _capture(monkeypatch)
    query_retrival._translate_query_and_classify("పంచదార ఎంత ఉంది", "te")
    system = calls[0]["messages"][0]["content"]
    for language in (
        "Hindi", "Tamil", "Kannada", "Malayalam",
        "Marathi", "Bengali", "Gujarati", "Punjabi",
    ):
        assert language in system


def test_shop_names_reach_translation_as_data(monkeypatch):
    calls = _capture(monkeypatch)
    token = query_retrival._QUERY_SHOP_VOCABULARY.set(
        ("Sona Masoori Rice", "Ganesh")
    )
    try:
        query_retrival._translate_query_and_classify("గణేష్ జీతం ఎంత", "te")
    finally:
        query_retrival._QUERY_SHOP_VOCABULARY.reset(token)
    user_message = calls[0]["messages"][1]["content"]
    assert "Sona Masoori Rice" in user_message
    assert "Ganesh" in user_message


def test_no_vocabulary_keeps_user_message_free_of_shop_hint(monkeypatch):
    calls = _capture(monkeypatch)
    query_retrival._translate_query_and_classify("పంచదార ఎంత ఉంది", "te")
    assert "Shop names" not in calls[0]["messages"][1]["content"]


def test_misheard_words_are_repaired_before_translation(monkeypatch):
    calls = _capture(monkeypatch)
    query_retrival._translate_query_and_classify("పంచేదారా ఎంత ఉంది", "te")
    assert "పంచదార ఎంత ఉంది" in calls[0]["messages"][1]["content"]
