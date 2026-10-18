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



# English -> Indian-language translation for interface text and translated answers.
# Loaded only when the text translation endpoint is used, so normal speech queries
# do not pay the memory cost until this capability is actually needed.
EN_INDIC_TRANSLATION_MODEL_NAME = os.getenv(
    "INDIC_EN_TRANSLATION_MODEL",
    "ai4bharat/indictrans2-en-indic-dist-200M",
)
TEXT_TRANSLATION_MAX_ITEMS = 20
TEXT_TRANSLATION_MAX_CHARS_PER_ITEM = 4000
TEXT_TRANSLATION_MAX_TOTAL_CHARS = 4000
TARGET_SCRIPT_RANGES: dict[str, tuple[int, int]] = {
    "as": (0x0980, 0x09FF),
    "bn": (0x0980, 0x09FF),
    "gu": (0x0A80, 0x0AFF),
    "hi": (0x0900, 0x097F),
    "mr": (0x0900, 0x097F),
    "ne": (0x0900, 0x097F),
    "pa": (0x0A00, 0x0A7F),
    "or": (0x0B00, 0x0B7F),
    "ta": (0x0B80, 0x0BFF),
    "te": (0x0C00, 0x0C7F),
    "kn": (0x0C80, 0x0CFF),
    "ml": (0x0D00, 0x0D7F),
}
_PROTECTED_TRANSLATION_TOKEN = __import__("re").compile(
    r"https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|"
    r"\{[^{}]{1,80}\}|%[a-zA-Z]|₹\s?[\d,]+(?:\.\d+)?|"
    r"\b\d[\d,]*(?:\.\d+)?(?:%|[/:.-]\d[\d,]*(?:\.\d+)?)?\b"
)


def _load_english_indic_model() -> tuple[Any, Any, Any, str]:
    """Load the distilled, open-source English-to-Indic model on first use."""
    with _model_lock:
        if "english_indic" in _model_state:
            cached = _model_state["english_indic"]
            return cached["tokenizer"], cached["translator"], cached["processor"], cached["device"]

        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        from IndicTransToolkit import IndicProcessor

        device = _device()
        hf_kwargs = {"token": HF_TOKEN} if HF_TOKEN else {}
        tokenizer = AutoTokenizer.from_pretrained(
            EN_INDIC_TRANSLATION_MODEL_NAME,
            trust_remote_code=True,
            **hf_kwargs,
        )
        translator = AutoModelForSeq2SeqLM.from_pretrained(
            EN_INDIC_TRANSLATION_MODEL_NAME,
            trust_remote_code=True,
            **hf_kwargs,
        ).to(device)
        translator.eval()
        processor = IndicProcessor(inference=True)
        _model_state["english_indic"] = {
            "tokenizer": tokenizer,
            "translator": translator,
            "processor": processor,
            "device": device,
        }
        return tokenizer, translator, processor, device


def _already_in_target_script(text: str, language_code: str) -> bool:
    bounds = TARGET_SCRIPT_RANGES.get(language_code)
    if not bounds:
        return False
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    start, end = bounds
    matching = sum(start <= ord(char) <= end for char in letters)
    return matching / len(letters) >= 0.70


def _translate_english_batch_to_indic(
    texts: list[str],
    language_code: str,
) -> list[str]:
    """Translate a batch with IndicTrans2, retaining placeholders and numeric facts."""
    if language_code == "en":
        return texts
    language_entry = INDIC_LANGUAGE_MAP.get(language_code)
    if not language_entry:
        raise HTTPException(status_code=422, detail="Unsupported translation language.")
    target_language = language_entry[1]

    prepared_inputs: list[str] = []
    candidate_indices: list[int] = []
    original_texts = list(texts)
    token_maps: dict[int, dict[str, str]] = {}
    results: list[str | None] = [None] * len(texts)

    for index, source in enumerate(texts):
        text_value = str(source or "").strip()
        if not text_value or _already_in_target_script(text_value, language_code):
            results[index] = text_value
            continue

        replacements: dict[str, str] = {}
        def protect(match: Any) -> str:
            token = f"<ID{len(replacements)}>"
            replacements[token] = match.group(0)
            return token

        protected = _PROTECTED_TRANSLATION_TOKEN.sub(protect, text_value)
        prepared_inputs.append(protected)
        candidate_indices.append(index)
        token_maps[index] = replacements

    if not prepared_inputs:
        return [value if value is not None else "" for value in results]

    tokenizer, translator, processor, device = _load_english_indic_model()
    preprocessed = processor.preprocess_batch(
        prepared_inputs,
        src_lang="eng_Latn",
        tgt_lang=target_language,
    )
    encoded = tokenizer(
        preprocessed,
        truncation=True,
        padding="longest",
        max_length=256,
        return_tensors="pt",
        return_attention_mask=True,
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}

    import torch
    with _inference_lock, torch.inference_mode():
        generated = translator.generate(
            **encoded,
            use_cache=True,
            min_length=0,
            max_length=256,
            num_beams=3,
            num_return_sequences=1,
        )

    decoded = tokenizer.batch_decode(
        generated,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    )
    postprocessed = processor.postprocess_batch(decoded, lang=target_language)

    for index, translated in zip(candidate_indices, postprocessed):
        original = original_texts[index]
        value = str(translated or "").strip()
        replacements = token_maps[index]
        # If the model lost a protected value, do not return a translation that
        # could silently alter a price, ID, URL, phone number, or placeholder.
        if any(token not in value for token in replacements):
            results[index] = original
            continue
        for token, literal in replacements.items():
            value = value.replace(token, literal)
        results[index] = value or original

    return [value if value is not None else original_texts[index] for index, value in enumerate(results)]


@app.post("/translate-text-batch")
async def translate_text_batch(
    payload: dict[str, Any],
    x_speech_service_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Translate interface text with local IndicTrans2; no third-party LLM call."""
    if not SERVICE_KEY:
        raise HTTPException(
            status_code=503,
            detail="INDIC_SPEECH_SERVICE_API_KEY must be configured.",
        )
    if not x_speech_service_key or not secrets.compare_digest(
        x_speech_service_key, SERVICE_KEY
    ):
        raise HTTPException(status_code=401, detail="Invalid speech service credentials.")

    language_code = str(payload.get("language_code") or "").strip().lower()
    if language_code not in {"en", *INDIC_LANGUAGE_MAP.keys()}:
        raise HTTPException(status_code=422, detail="Unsupported translation language.")

    texts = payload.get("texts")
    if not isinstance(texts, list) or not texts:
        raise HTTPException(status_code=422, detail="Provide a non-empty texts array.")
    if len(texts) > TEXT_TRANSLATION_MAX_ITEMS:
        raise HTTPException(
            status_code=413,
            detail=f"Translate at most {TEXT_TRANSLATION_MAX_ITEMS} text items per request.",
        )
    if any(not isinstance(value, str) for value in texts):
        raise HTTPException(status_code=422, detail="Every text item must be a string.")
    normalized = [value.strip() for value in texts]
    if any(len(value) > TEXT_TRANSLATION_MAX_CHARS_PER_ITEM for value in normalized):
        raise HTTPException(status_code=413, detail="A translation item exceeds the 4,000-character limit.")
    if sum(len(value) for value in normalized) > TEXT_TRANSLATION_MAX_TOTAL_CHARS:
        raise HTTPException(status_code=413, detail="Combined translation text exceeds 4,000 characters.")

    if language_code == "en":
        translated = normalized
    else:
        try:
            translated = await run_in_threadpool(
                _translate_english_batch_to_indic,
                normalized,
                language_code,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("IndicTrans2 text translation failed")
            raise HTTPException(
                status_code=503,
                detail="The open-source translation model is temporarily unavailable.",
            ) from exc

    return {
        "translations": translated,
        "language_code": language_code,
        "translation_model": EN_INDIC_TRANSLATION_MODEL_NAME,
        "provider": "self_hosted_indictrans2",
    }


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
