def test_support_chat_endpoint_is_registered_and_authenticated():
    import inspect
    from query_retrival import app, support_chat_message

    routes = {
        (getattr(route, "path", ""), frozenset(getattr(route, "methods", set())))
        for route in app.routes
    }
    assert ("/chatbot/message", frozenset({"POST"})) in routes
    assert "message" in inspect.signature(support_chat_message).parameters
    assert "user_id" in inspect.signature(support_chat_message).parameters


def test_support_chat_answers_common_app_guidance_without_shop_data_query():
    from query_retrival import _support_chat_guidance, _is_shop_data_question

    answer = _support_chat_guidance("How do I create a bill?")
    assert answer is not None
    assert "Sales or Add Sale" in answer
    assert "Invoices" in answer
    assert not _is_shop_data_question("How do I create a bill?")


def test_support_chat_routes_live_shop_questions_to_query_engine():
    from query_retrival import _is_shop_data_question, _support_chat_guidance

    question = "Show my sales today"
    assert _support_chat_guidance(question) is None
    assert _is_shop_data_question(question)


def test_support_chat_has_help_fallback_for_unknown_app_questions():
    from query_retrival import _support_chat_guidance

    assert _support_chat_guidance("Can you explain this screen?") is None
