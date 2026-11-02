import asyncio
from types import SimpleNamespace

import query_retrival
from support_chat_retrieval import (
    classify_shop_data_intent,
    greeting_answer,
    is_simple_greeting,
    normalize_support_query,
    retrieve_support_article,
)


def test_simple_greetings_are_deterministic_and_language_aware():
    assert is_simple_greeting("Hi")
    assert is_simple_greeting("హలో")
    assert greeting_answer("en").startswith("Hello!")
    assert "నమస్కారం" in greeting_answer("te")


def test_help_retrieval_returns_bill_workflow_for_paraphrased_question():
    article = retrieve_support_article("How do I create bill?", "en")
    assert article is not None
    assert article["id"] == "create_bill"
    assert "Sales or Add Sale" in article["answer"]
    assert "Invoices" in article["answer"]
    assert article["retrieval"] == "lexical_support_rag"


def test_help_retrieval_returns_telugu_answer():
    article = retrieve_support_article("బిల్ ఎలా తయారు చేయాలి", "te")
    assert article is not None
    assert article["id"] == "create_bill"
    assert "Retail Mind" in article["answer"]


def test_help_retrieval_does_not_guess_unmatched_questions():
    assert retrieve_support_article("What is the weather outside?", "en") is None
    assert retrieve_support_article("Can you explain this screen?", "en") is None


def test_local_normalization_handles_common_telugu_and_roman_telugu():
    today_query = normalize_support_query("ఈరోజు అమ్మకాలు ఎంత?")
    yesterday_query = normalize_support_query("ninna ammakalu")
    assert "today" in today_query and "sales" in today_query
    assert "yesterday" in yesterday_query and "sales" in yesterday_query
    assert "low stock" in normalize_support_query("తక్కువ స్టాక్ ఏవి?")


def test_supported_business_intents_are_classified_without_llm():
    assert classify_shop_data_intent("Show my sales today")[0] == "sales_amount"
    assert classify_shop_data_intent("Which products are low in stock?")[0] == "low_stock"
    assert classify_shop_data_intent("Who owes me money?")[0] == "receivables"
    assert classify_shop_data_intent("ఈరోజు అమ్మకాలు ఎంత?")[0] == "sales_amount"
    assert classify_shop_data_intent("తక్కువ స్టాక్ ఏవి?")[0] == "low_stock"


def test_support_chat_greeting_does_not_call_groq_or_query_engine(monkeypatch):
    async def unexpected_query(*_args, **_kwargs):
        raise AssertionError("Greeting must not call the business query engine.")

    def unexpected_translation(*_args, **_kwargs):
        raise AssertionError("Support chat must not call translation/LLM services.")

    monkeypatch.setattr(query_retrival, "ask_query", unexpected_query)
    monkeypatch.setattr(query_retrival, "_translate_answer_to_language", unexpected_translation)

    result = asyncio.run(query_retrival.support_chat_message(
        message="Hi",
        language_code="en",
        conversation_history="[]",
        db=object(),
        user_id=41,
    ))

    assert result["source"] == "greeting"
    assert result["llm_calls"] == 0
    assert "Retail Mind assistant" in result["answer"]


def test_support_chat_retrieves_app_help_without_groq(monkeypatch):
    async def unexpected_query(*_args, **_kwargs):
        raise AssertionError("Application help must not enter the SQL/LLM query engine.")

    def unexpected_translation(*_args, **_kwargs):
        raise AssertionError("Application help must not call translation/LLM services.")

    monkeypatch.setattr(query_retrival, "ask_query", unexpected_query)
    monkeypatch.setattr(query_retrival, "_translate_answer_to_language", unexpected_translation)

    result = asyncio.run(query_retrival.support_chat_message(
        message="How do I create a bill?",
        language_code="en",
        conversation_history="[]",
        db=object(),
        user_id=41,
    ))

    assert result["source"] == "retail_mind_help"
    assert result["retrieved_documents"][0]["id"] == "create_bill"
    assert "Sales or Add Sale" in result["answer"]
    assert result["llm_calls"] == 0


def test_support_chat_telugu_help_uses_local_answer_without_translation(monkeypatch):
    result = asyncio.run(query_retrival.support_chat_message(
        message="బిల్ ఎలా తయారు చేయాలి",
        language_code="te",
        conversation_history="[]",
        db=object(),
        user_id=41,
    ))

    assert result["source"] == "retail_mind_help"
    assert "Retail Mind" in result["answer"]
    assert "సేవ్" in result["answer"]


def test_support_chat_business_data_uses_fast_sql_handler_not_ask_query(monkeypatch):
    calls = {}

    def fake_fast_query(query, db, user_id, date_scope):
        calls.update(query=query, db=db, user_id=user_id, date_scope=date_scope)
        return {
            "answer": "Your total sales amount today is ₹1,250.00.",
            "generated_sql": "SELECT ... WHERE user_id = :user_id",
            "results": [{"total_sales_amount": 1250.0}],
            "has_more": False,
        }

    async def unexpected_query(*_args, **_kwargs):
        raise AssertionError("Support chat must not call ask_query/Groq.")

    monkeypatch.setattr(query_retrival, "_fast_business_query", fake_fast_query)
    monkeypatch.setattr(query_retrival, "ask_query", unexpected_query)
    monkeypatch.setattr(query_retrival, "_persist_query_history", lambda **_kwargs: None)

    db = object()
    result = asyncio.run(query_retrival.support_chat_message(
        message="Show my sales today",
        language_code="en",
        conversation_history="[]",
        db=db,
        user_id=77,
    ))

    assert result["source"] == "shop_data_query"
    assert result["llm_calls"] == 0
    assert result["results"] == [{"total_sales_amount": 1250.0}]
    assert calls["db"] is db
    assert calls["user_id"] == 77
    assert calls["query"] == "show my sales today"
    assert calls["date_scope"]["label"] == "today"


def test_unsupported_chat_question_requests_clarification_without_groq(monkeypatch):
    async def unexpected_query(*_args, **_kwargs):
        raise AssertionError("Unknown questions must not fall through to ask_query.")

    def unexpected_translation(*_args, **_kwargs):
        raise AssertionError("Unknown questions must not invoke translation.")

    monkeypatch.setattr(query_retrival, "ask_query", unexpected_query)
    monkeypatch.setattr(query_retrival, "_translate_answer_to_language", unexpected_translation)

    result = asyncio.run(query_retrival.support_chat_message(
        message="Can you explain this completely unrelated screen?",
        language_code="en",
        conversation_history="[]",
        db=object(),
        user_id=41,
    ))

    assert result["source"] == "clarification"
    assert result["llm_calls"] == 0
    assert "couldn't confidently match" in result["answer"].lower()
