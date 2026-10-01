def test_ai_query_history_model_and_routes():
    from models import AIQueryHistory
    from query_retrival import app, _fast_business_query

    assert hasattr(AIQueryHistory, "question")
    assert hasattr(AIQueryHistory, "answer")
    assert hasattr(AIQueryHistory, "user_id")

    routes = {(getattr(route, "path", ""), getattr(route, "methods", set())) for route in app.routes}
    assert any(path == "/askquery/history" and "GET" in methods for path, methods in routes)
    assert any(path == "/askquery/history" and "DELETE" in methods for path, methods in routes)
    assert any(path == "/askquery/history/{history_id}" and "DELETE" in methods for path, methods in routes)

    assert callable(_fast_business_query)
