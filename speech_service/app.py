"""
Self-hosted, open-source Indian-language voice service for Ask Retail Mind.

Pipeline:
audio -> AI4Bharat IndicConformer ASR -> IndicTrans2 English translation
      -> authenticated Retail-Mind /askquery/voice proxy -> existing RAG/SQL engine.

After model weights are cached, inference does not call a paid model API.
Keep this service on a private LAN or behind the authenticated Retail-Mind proxy.
"""
from __future__ import annotations

import os
import secrets
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

app = FastAPI(title="Retail Mind Open-source Indic Voice Service", version="1.0.0")

MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_AUDIO_SECONDS = 60
SERVICE_KEY = os.getenv("INDIC_SPEECH_SERVICE_API_KEY", "").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
DEVICE_OVERRIDE = os.getenv("VOICE_MODEL_DEVICE", "").strip()

# IndicConformer language IDs (AI4Bharat's model interface) and the
# corresponding IndicTrans2 Indic->English source language tags.
INDIC_LANGUAGE_MAP: dict[str, tuple[str, str]] = {
    "as": ("as", "asm_Beng"),
    "bn": ("bn", "ben_Beng"),
    "brx": ("br", "brx_Deva"),
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
_model_state: dict[str, Any] = {}


def _device() -> str:
    if DEVICE_OVERRIDE:
        return DEVICE_OVERRIDE
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _load_indic_models() -> tuple[Any, Any, Any, str]:
    with _model_lock:
        if "indic" in _model_state:
            value = _model_state["indic"]
            return value["asr"], value["translator"], value["processor"], value["device"]

        # AI4Bharat's NeMo fork is required for the IndicConformer model.
        import nemo.collections.asr as nemo_asr
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        from IndicTransToolkit.processor import IndicProcessor

        device = _device()
        asr = nemo_asr.models.EncDecCTCModel.from_pretrained(
            model_name="ai4bharat/IndicConformer"
        ).to(device)
        asr.eval()
        asr.cur_decoder = "ctc"

        model_name = "ai4bharat/indictrans2-indic-en-dist-200M"
        tokenizer_kwargs = {"token": HF_TOKEN} if HF_TOKEN else {}
        tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True, **tokenizer_kwargs
        )
        translator = AutoModelForSeq2SeqLM.from_pretrained(
            model_name, trust_remote_code=True, **tokenizer_kwargs
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


def _load_english_asr() -> Any:
    with _model_lock:
        if "english_asr" in _model_state:
            return _model_state["english_asr"]
        from faster_whisper import WhisperModel

        model_size = os.getenv("ENGLISH_WHISPER_SIZE", "small")
        device = _device()
        compute_type = "float16" if device == "cuda" else "int8"
        whisper = WhisperModel(model_size, device=device, compute_type=compute_type)
        _model_state["english_asr"] = whisper
        return whisper


def _transcribe_indic(audio_path: str, language_code: str) -> str:
    import numpy as np
    import torch
    import torchaudio

    asr_code, _ = INDIC_LANGUAGE_MAP[language_code]
    waveform, sample_rate = torchaudio.load(audio_path)
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sample_rate != 16000:
        waveform = torchaudio.functional.resample(waveform, sample_rate, 16000)
    duration = waveform.shape[-1] / 16000
    if duration > MAX_AUDIO_SECONDS:
        raise HTTPException(status_code=413, detail="Audio must be 60 seconds or shorter.")

    asr, _, _, _ = _load_indic_models()
    audio_array = waveform.squeeze(0).cpu().numpy().astype(np.float32)
    with torch.inference_mode():
        predictions = asr.transcribe(
            [audio_array],
            batch_size=1,
            logprobs=False,
            language_id=asr_code,
        )
    prediction = predictions[0] if predictions else ""
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
    with torch.inference_mode():
        tokens = translator.generate(
            **encoded,
            use_cache=True,
            num_beams=4,
            max_length=256,
            num_return_sequences=1,
        )
    decoded = tokenizer.batch_decode(tokens, skip_special_tokens=True)
    postprocessed = processor.postprocess_batch(decoded, lang="eng_Latn")
    return str(postprocessed[0] if postprocessed else "").strip()


def _transcribe_english(audio_path: str) -> str:
    whisper = _load_english_asr()
    segments, _info = whisper.transcribe(
        audio_path,
        language="en",
        task="transcribe",
        vad_filter=True,
        beam_size=3,
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
            detail="INDIC_SPEECH_SERVICE_API_KEY is required before enabling the voice service.",
        )
    if not x_speech_service_key or not secrets.compare_digest(
        x_speech_service_key, SERVICE_KEY
    ):
        raise HTTPException(status_code=401, detail="Invalid speech service credentials.")

    code = language_code.strip().lower()
    if code != "en" and code not in INDIC_LANGUAGE_MAP:
        raise HTTPException(status_code=422, detail="Unsupported language code.")
    allowed_audio_suffixes = {".wav", ".m4a", ".aac", ".mp3", ".ogg", ".webm", ".flac"}
    suffix = Path(audio.filename or "voice-query.wav").suffix.lower() or ".wav"
    if not (audio.content_type or "").lower().startswith("audio/") and suffix not in allowed_audio_suffixes:
        raise HTTPException(status_code=415, detail="Upload an audio recording.")

    
    content = await audio.read(MAX_AUDIO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="The audio recording is empty.")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file is too large.")

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        if code == "en":
            transcript = await run_in_threadpool(_transcribe_english, tmp_path)
            english_query = transcript
        else:
            # Keep heavyweight model loading/inference off FastAPI's event loop,
            # so health checks and other requests remain responsive.
            transcript = await run_in_threadpool(_transcribe_indic, tmp_path, code)
            if not transcript:
                raise HTTPException(
                    status_code=422,
                    detail="No clear speech was detected. Please record your question again.",
                )
            english_query = await run_in_threadpool(_translate_to_english, transcript, code)

        if not english_query:
            raise HTTPException(
                status_code=422,
                detail="Translation produced no English text. Please try again.",
            )
        return {
            "language_code": code,
            "transcript": transcript,
            "english_query": english_query,
            "translation_model": "IndicTrans2 Indic-En Distilled 200M" if code != "en" else "faster-whisper",
            "asr_model": "AI4Bharat IndicConformer" if code != "en" else "Whisper",
        }
    except HTTPException:
        raise
    except Exception as exc:
        # Log only safe error metadata; never return file paths, raw audio or traceback.
        import logging
        logging.getLogger("retail_mind_voice").exception(
            "Speech model inference failed (%s)", type(exc).__name__
        )
        raise HTTPException(
            status_code=503,
            detail="Speech model is not ready or failed. Check the voice-service logs and model downloads.",
        )
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
