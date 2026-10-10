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
