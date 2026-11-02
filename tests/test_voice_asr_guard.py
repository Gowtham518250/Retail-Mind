"""Phantom-speech regression tests: silence / noise must never become bill lines."""
import asyncio
import io
import json

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

import inventory as inventory_module
from voice_asr_guard import GuardThresholds, assess_transcription, has_repetition_loop, is_known_hallucination
from voice_billing_core import custom_name_is_grounded


def seg(text, *, nsp=0.02, lp=-0.25, cr=1.2, start=0.0, end=2.0):
    return {"text": text, "no_speech_prob": nsp, "avg_logprob": lp, "compression_ratio": cr, "start": start, "end": end}


def payload(*segments, duration=3.0):
    return {"text": " ".join(s["text"] for s in segments), "duration": duration, "segments": list(segments)}


EN_PREFIX = inventory_module._VOICE_BILLING_WHISPER_PREFIXES["en"]
TE_PREFIX = inventory_module._VOICE_BILLING_WHISPER_PREFIXES["te"]


# ---- real speech must pass -------------------------------------------------

def test_clear_speech_is_accepted():
    v = assess_transcription(payload(seg("2 kg rice 50")))
    assert v.accepted and v.text == "2 kg rice 50" and v.scored


def test_clear_telugu_speech_is_accepted():
    v = assess_transcription(payload(seg("రెండు కిలోల బియ్యం యాభై", lp=-0.45)), prompt_prefix=TE_PREFIX)
    assert v.accepted


def test_polite_phrase_inside_a_real_order_is_not_a_hallucination():
    assert assess_transcription(payload(seg("2 kg rice thank you"))).accepted


def test_hesitant_but_real_speech_is_not_over_rejected():
    # borderline: mediocre decoder confidence, clearly speech
    assert assess_transcription(payload(seg("3 packets biscuits", nsp=0.15, lp=-0.9))).accepted


# ---- silence, noise and hallucinations must be rejected ----------------------

def test_telugu_gibberish_from_screenshot_is_rejected_when_no_speech_is_likely():
    gibberish = "ఇదాం ఎద్దారు మాస్ట్ నిత్రం. ఆదంతుల ఇది కరేశాం చొనంపిస్తా."
    v = assess_transcription(payload(seg(gibberish, nsp=0.72, lp=-1.05)), prompt_prefix=TE_PREFIX)
    assert not v.accepted and v.reason == "no_speech"


def test_low_decoder_confidence_alone_rejects_garbage():
    v = assess_transcription(payload(seg("ఇదాం ఎద్దారు మాస్ట్ నిత్రం", nsp=0.2, lp=-1.7)))
    assert not v.accepted and v.reason == "low_confidence"


def test_very_high_no_speech_probability_rejects_even_confident_text():
    v = assess_transcription(payload(seg("2 kg rice", nsp=0.93, lp=-0.2)))
    assert not v.accepted and v.reason == "no_speech"


@pytest.mark.parametrize(
    "text",
    ["Thank you.", "Thanks for watching!", "Thank you for watching", "please subscribe",
     "Subtitles by the Amara.org community", "చూసినందుకు ధన్యవాదాలు", "धन्यवाद", "you", "Bye."],
)
def test_known_silence_hallucinations_are_rejected_even_with_high_confidence(text):
    assert is_known_hallucination(text)
    v = assess_transcription(payload(seg(text, nsp=0.1, lp=-0.3)))
    assert not v.accepted and v.reason == "known_hallucination"


def test_hallucinated_tail_is_dropped_but_real_speech_is_kept():
    v = assess_transcription(payload(
        seg("2 kg rice 50", start=0.0, end=2.0),
        seg("Thanks for watching", nsp=0.4, lp=-0.8, start=2.0, end=3.0),
    ))
    assert v.accepted and v.text == "2 kg rice 50" and v.dropped_segments == 1


def test_repetition_loop_by_compression_ratio():
    v = assess_transcription(payload(seg("rice rice rice rice rice rice", cr=3.4)))
    assert not v.accepted and v.reason == "repetition"


def test_repetition_loop_by_text_when_ratio_is_missing():
    assert has_repetition_loop("rice rice rice rice")
    assert has_repetition_loop("two kg two kg two kg two kg")
    assert not has_repetition_loop("2 kg rice 2 kg sugar")
    s = {"text": "rice rice rice rice rice", "start": 0, "end": 2}
    assert not assess_transcription(payload(s)).accepted


def test_prompt_prefix_echo_is_rejected():
    echo = "Retail billing. Preserve the spoken product names, quantities and rupee prices."
    v = assess_transcription(payload(seg(echo, nsp=0.3, lp=-0.5)), prompt_prefix=EN_PREFIX)
    assert not v.accepted and v.reason == "prompt_echo"


def test_catalog_vocabulary_echo_is_rejected_but_not_when_a_quantity_is_spoken():
    names = ["Rice", "Sugar", "Oil", "Salt", "Tea", "Milk", "Soap", "Dal"]
    echo = "Rice, Sugar, Oil, Salt, Tea, Milk, Soap, Dal"
    assert not assess_transcription(payload(seg(echo)), catalog_names=names).accepted
    assert assess_transcription(payload(seg("2 rice 1 sugar 1 oil 1 salt")), catalog_names=names).accepted


def test_audio_shorter_than_a_tap_is_rejected():
    v = assess_transcription(payload(seg("ok rice"), duration=0.2))
    assert not v.accepted and v.reason == "too_short"


def test_voiced_time_after_filtering_must_reach_the_minimum():
    v = assess_transcription(payload(seg("rice", start=0.0, end=0.1)))
    assert not v.accepted and v.reason == "too_short"


def test_payload_without_segments_uses_text_rules_and_is_marked_unscored():
    ok = assess_transcription({"text": "2 kg rice 50"})
    assert ok.accepted and not ok.scored and ok.reason == "ok_unscored"
    assert not assess_transcription({"text": "Thank you."}).accepted
    assert not assess_transcription({"text": "   "}).accepted
    assert not assess_transcription("not a dict").accepted  # type: ignore[arg-type]


def test_thresholds_are_configurable():
    strict = GuardThresholds(no_speech_soft=0.2)
    s = seg("2 kg rice", nsp=0.3, lp=-0.85)
    assert assess_transcription(payload(s)).accepted
    assert not assess_transcription(payload(s), thresholds=strict).accepted


def test_public_diagnostics_never_contain_transcript_text():
    v = assess_transcription(payload(seg("2 kg rice 50")))
    assert "2 kg" not in json.dumps(v.public())


# ---- custom-item grounding ---------------------------------------------------

def test_custom_item_must_be_present_in_the_transcript():
    norm = inventory_module._voice_billing_normalize
    assert custom_name_is_grounded(["Toothbrush"], ["2 toothbrush"], normalize=norm)
    assert custom_name_is_grounded(["Tooth brush"], ["2 toothbrush"], normalize=norm)
    assert custom_name_is_grounded(["Soaps"], ["3 soap"], normalize=norm)
    assert not custom_name_is_grounded(["Toothbrush"], ["2 kg rice"], normalize=norm)
    assert custom_name_is_grounded([""], ["anything"], normalize=norm)  # nothing testable: do not block


# ---- endpoint level -----------------------------------------------------------

class _EmptyQuery:
    def filter(self, *a): return self
    def order_by(self, *a): return self
    def limit(self, *a): return self
    def all(self): return []


class _Db:
    def query(self, *a): return _EmptyQuery()


def _run_audio(monkeypatch, whisper_json):
    monkeypatch.setenv("GROQ_API_KEY", "unit-test-key")
    calls = {"parse": 0}

    class FakeResponse:
        status_code = 200
        def raise_for_status(self): return None
        def json(self): return whisper_json

    class FakeAsyncClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def post(self, url, *, headers, data, files): return FakeResponse()

    async def fake_parse(request, *, user_id, db):
        calls["parse"] += 1
        return {"success": True, "items": [], "needs_clarification": False}

    monkeypatch.setattr(inventory_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(inventory_module, "parse_voice_billing", fake_parse)
    audio = UploadFile(filename="v.m4a", file=io.BytesIO(b"fake"), headers=Headers({"content-type": "audio/mp4"}))
    result = asyncio.run(inventory_module.parse_voice_billing_audio(
        audio=audio, language_code="te", user_id=7, db=_Db()))
    return result, calls


def test_silent_recording_returns_422_and_never_reaches_the_llm(monkeypatch):
    silent = payload(seg("ఇదాం ఎద్దారు మాస్ట్ నిత్రం.", nsp=0.8, lp=-1.2), duration=4.0)
    with pytest.raises(HTTPException) as exc:
        _run_audio(monkeypatch, silent)
    assert exc.value.status_code == 422
    assert "No clear speech" in exc.value.detail


def test_silent_recording_does_not_call_the_parser(monkeypatch):
    calls = {}
    try:
        _, calls = _run_audio(monkeypatch, payload(seg("Thank you.", nsp=0.9, lp=-1.4)))
    except HTTPException:
        pass
    assert calls.get("parse", 0) == 0


def test_real_recording_passes_through_with_speech_quality(monkeypatch):
    result, calls = _run_audio(monkeypatch, payload(seg("2 kg rice 50")))
    assert calls["parse"] == 1
    assert result["transcript"] == "2 kg rice 50"
    assert result["speech_quality"]["accepted"] is True


def test_extractor_invented_item_is_not_added_to_the_bill(monkeypatch):
    from test_voice_billing_parse_contract import _run_voice_billing_endpoint

    result, _, _, _ = _run_voice_billing_endpoint(
        monkeypatch,
        [{
            "product_id": None, "product_name_en": "Toothbrush", "product_name_local": "",
            "quantity": 1, "spoken_unit": "", "spoken_price_kind": "none", "confidence": 0.95,
        }],
        transcript="2 kg rice 50",
        language_code="en-IN",
    )
    assert result["items"] == []
    assert result["needs_clarification"] is True
    assert "Toothbrush" in result["clarification_question"]


# ---- AI Query voice path uses the same guard ---------------------------------

def _query_transcribe(monkeypatch, response):
    from types import SimpleNamespace
    import query_retrival

    monkeypatch.setattr(query_retrival, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        query_retrival, "client",
        SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=lambda **kw: response))),
    )
    return query_retrival._transcribe_audio_with_groq(b"x", "q.wav", "audio/wav", "te")


def test_ai_query_voice_rejects_silence_hallucination(monkeypatch):
    from types import SimpleNamespace
    silent = SimpleNamespace(text="Thank you.", duration=3.0, segments=[seg("Thank you.", nsp=0.9, lp=-1.4)])
    with pytest.raises(HTTPException) as exc:
        _query_transcribe(monkeypatch, silent)
    assert exc.value.status_code == 422


def test_ai_query_voice_accepts_real_question_as_pydantic_like_object(monkeypatch):
    from types import SimpleNamespace

    class Resp(SimpleNamespace):
        def model_dump(self):
            return {"text": "yesterday sales", "duration": 2.0, "segments": [seg("yesterday sales")]}

    assert _query_transcribe(monkeypatch, Resp(text="yesterday sales")) == "yesterday sales"
