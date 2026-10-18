from speech_service import app as speech_service_app


def test_open_source_text_translation_endpoint_is_registered():
    routes = {
        getattr(route, "path", "")
        for route in speech_service_app.app.routes
    }
    assert "/translate-text-batch" in routes
