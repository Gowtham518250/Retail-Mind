"""Self-hosted open-source Indian-language speech service for Retail Mind.

Audio -> AI4Bharat IndicConformer ASR -> IndicTrans2 translation -> English.
The authenticated Retail Mind backend then sends the English question through
its existing RAG/table retrieval + SQL generation route.
"""
from __future__ import annotations

import logging
import os
import secrets
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

app = FastAPI(title="Retail Mind Open-source Indic Voice Service", version="1.0.0")
logger = logging.getLogger("retail_mind_voice")

MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_AUDIO_SECONDS = 60
SERVICE_KEY = (os.getenv("INDIC_SPEECH_SERVICE_API_KEY") or "").strip()
HF_TOKEN = (os.getenv("HF_TOKEN") or "").strip()
DEVICE_OVERRIDE = (os.getenv("VOICE_MODEL_DEVICE") or "").strip()
ASR_MODEL_NAME = os.getenv(
    "INDIC_ASR_MODEL", "ai4bharat/indic-conformer-600m-multilingual"
)
TRANSLATION_MODEL_NAME = os.getenv(
    "INDIC_TRANSLATION_MODEL", "ai4bharat/indictrans2-indic-en-dist-200M"
)

# App language code -> (IndicConformer ASR language ID, IndicTrans2 source tag).
INDIC_LANGUAGE_MAP: dict[str, tuple[str, str]] = {
    "as": ("as", "asm_Beng"),
    "bn": ("bn", "ben_Beng"),
    "brx": ("brx", "brx_Deva"),
    "doi": ("doi", "doi_Deva"),
    "gu": ("gu", "guj_Gujr"),
    "hi": ("hi", "hin_Deva"),
    "kn": ("kn", "kan_Knda"),
    "ks": ("ks", "kas_Arab"),
    "kok": ("kok", "gom_Deva"),
    "mai": ("mai", "mai_Deva"),
    "ml": ("ml", "mal_Mlym"),
    "mni": ("mni", "mni_Mtei"),
    "mr": ("mr", "mar_Deva"),
    "ne": ("ne", "npi_Deva"),
    "or": ("or", "ory_Orya"),
    "pa": ("pa", "pan_Guru"),
    "sa": ("sa", "san_Deva"),
    "sat": ("sat", "sat_Olck"),
    "sd": ("sd", "snd_Arab"),
    "ta": ("ta", "tam_Taml"),
    "te": ("te", "tel_Telu"),
    "ur": ("ur", "urd_Arab"),
}

_model_lock = threading.Lock()
_inference_lock = threading.Lock()
_model_state: dict[str, Any] = {}


def _device() -> str:
    if DEVICE_OVERRIDE:
        return DEVICE_OVERRIDE
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load_indic_models() -> tuple[Any, Any, Any, str]:
    """Load weights on first request and cache model objects."""
    with _model_lock:
        if "indic" in _model_state:
            cached = _model_state["indic"]
            return cached["asr"], cached["translator"], cached["processor"], cached["device"]

        from transformers import AutoModel, AutoModelForSeq2SeqLM, AutoTokenizer
        from IndicTransToolkit import IndicProcessor

        device = _device()
        hf_kwargs = {"token": HF_TOKEN} if HF_TOKEN else {}

        # Matches the official Hugging Face IndicConformer model-card API.
        asr = AutoModel.from_pretrained(
            ASR_MODEL_NAME, trust_remote_code=True, **hf_kwargs
        ).to(device)
        asr.eval()

        tokenizer = AutoTokenizer.from_pretrained(
            TRANSLATION_MODEL_NAME, trust_remote_code=True, **hf_kwargs
        )
        translator = AutoModelForSeq2SeqLM.from_pretrained(
            TRANSLATION_MODEL_NAME, trust_remote_code=True, **hf_kwargs
        ).to(device)
        translator.eval()
        processor = IndicProcessor(inference=True)

        _model_state["indic"] = {
            "asr": asr,
            "translator": translator,
            "tokenizer": tokenizer,
            "processor": processor,
            "device": device,
        }
        return asr, translator, processor, device


def _transcribe_indic(audio_path: str, language_code: str) -> str:
    import torch
    import torchaudio

    asr_language_id, _ = INDIC_LANGUAGE_MAP[language_code]
    waveform, sample_rate = torchaudio.load(audio_path)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sample_rate != 16000:
        waveform = torchaudio.functional.resample(waveform, sample_rate, 16000)

    duration = waveform.shape[-1] / 16000
    if duration > MAX_AUDIO_SECONDS:
        raise HTTPException(status_code=413, detail="Audio must be 60 seconds or shorter.")

    asr, _, _, device = _load_indic_models()
    with _inference_lock, torch.inference_mode():
        prediction = asr(waveform.to(device), asr_language_id, "ctc")
    if isinstance(prediction, (tuple, list)):
        prediction = prediction[0] if prediction else ""
    return str(prediction or "").strip()


def _translate_to_english(transcript: str, language_code: str) -> str:
    import torch

    _, source_language = INDIC_LANGUAGE_MAP[language_code]
    _, translator, processor, device = _load_indic_models()
    tokenizer = _model_state["indic"]["tokenizer"]
    prepared = processor.preprocess_batch(
        [transcript], src_lang=source_language, tgt_lang="eng_Latn"
    )
    encoded = tokenizer(
        prepared,
        truncation=True,
        padding="longest",
        return_tensors="pt",
        return_attention_mask=True,
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}

    with _inference_lock, torch.inference_mode():
        generated = translator.generate(
            **encoded,
            use_cache=True,
            min_length=0,
            max_length=256,
            num_beams=4,
            num_return_sequences=1,
        )
    decoded = tokenizer.batch_decode(
        generated, skip_special_tokens=True, clean_up_tokenization_spaces=True
    )
    postprocessed = processor.postprocess_batch(decoded, lang="eng_Latn")
    return str(postprocessed[0] if postprocessed else "").strip()


def _load_english_asr() -> Any:
    with _model_lock:
        if "english_asr" in _model_state:
            return _model_state["english_asr"]
        from faster_whisper import WhisperModel

        size = os.getenv("ENGLISH_WHISPER_SIZE", "small")
        device = _device()
        compute_type = "float16" if device == "cuda" else "int8"
        model = WhisperModel(size, device=device, compute_type=compute_type)
        _model_state["english_asr"] = model
        return model


def _transcribe_english(audio_path: str) -> str:
    whisper = _load_english_asr()
    segments, _info = whisper.transcribe(
        audio_path, language="en", task="transcribe", vad_filter=True, beam_size=3
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "retail-mind-indic-voice",
        "models_loaded": sorted(_model_state.keys()),
        "speech_key_configured": bool(SERVICE_KEY),
    }


@app.post("/transcribe-and-translate")
async def transcribe_and_translate(
    audio: UploadFile = File(...),
    language_code: str = Form(...),
    x_speech_service_key: str | None = Header(default=None),
) -> dict[str, str]:
    if not SERVICE_KEY:
        raise HTTPException(
            status_code=503,
            detail="INDIC_SPEECH_SERVICE_API_KEY must be configured before enabling voice queries.",
        )
    if not x_speech_service_key or not secrets.compare_digest(
        x_speech_service_key, SERVICE_KEY
    ):
        raise HTTPException(status_code=401, detail="Invalid speech service credentials.")

    code = language_code.strip().lower()
    if code != "en" and code not in INDIC_LANGUAGE_MAP:
        raise HTTPException(status_code=422, detail="Unsupported voice language.")

    allowed_suffixes = {".wav", ".m4a", ".aac", ".mp3", ".ogg", ".webm", ".flac"}
    suffix = Path(audio.filename or "voice-query.wav").suffix.lower() or ".wav"
    content_type = (audio.content_type or "").lower()
    if not content_type.startswith("audio/") and suffix not in allowed_suffixes:
        raise HTTPException(status_code=415, detail="Upload a supported audio recording.")

    content = await audio.read(MAX_AUDIO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The audio recording is empty.")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file exceeds the 20 MB limit.")

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(content)
            temp_path = temporary.name

        if code == "en":
            transcript = await run_in_threadpool(_transcribe_english, temp_path)
            english_query = transcript
            asr_name = "faster-whisper"
            translation_name = "none (English input)"
        else:
            transcript = await run_in_threadpool(_transcribe_indic, temp_path, code)
            if not transcript:
                raise HTTPException(
                    status_code=422,
                    detail="No clear speech was detected. Please record your question again.",
                )
            english_query = await run_in_threadpool(
                _translate_to_english, transcript, code
            )
            asr_name = ASR_MODEL_NAME
            translation_name = TRANSLATION_MODEL_NAME

        if not english_query:
            raise HTTPException(
                status_code=422,
                detail="Translation produced no English question. Please try again.",
            )

        return {
            "language_code": code,
            "transcript": transcript,
            "english_query": english_query,
            "asr_model": asr_name,
            "translation_model": translation_name,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Voice model inference failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Speech models are not ready or inference failed. Check speech-service logs and model access.",
        ) from exc
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
