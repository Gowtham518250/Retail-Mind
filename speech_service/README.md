# Retail Mind open-source Indian voice service

> **Architecture note (2026-10-10):** The current AI Query app uses Groq Whisper through the authenticated backend endpoints `POST /askquery/transcribe` and `POST /askquery/voice`. It then sends the recognized transcript to `POST /askquery`, where the existing Groq text model translates it to English before the RAG/SQL pipeline. The current app flow does **not** require `INDIC_SPEECH_SERVICE_URL` or `INDIC_SPEECH_SERVICE_API_KEY`.

This directory preserves an optional self-hosted open-source Indian-language speech service. It is separate from the default Groq-based AI Query voice flow and should only be deployed if the project intentionally switches back to this architecture.


This separate, self-hosted service records one spoken question, transcribes the selected language and translates it into English. The authenticated Retail Mind backend forwards the English question into the existing RAG/table-retrieval + SQL generation flow.

## Models and licenses

- AI4Bharat IndicConformer: https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual — multilingual ASR for the 22 scheduled Indian languages; MIT license.
- AI4Bharat IndicTrans2 Indic-to-English distilled 200M: https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M — translation into English; MIT checkpoint license.
- faster-whisper: https://github.com/SYSTRAN/faster-whisper — local English ASR; open-source implementation.

These models do not require paid inference APIs. Hugging Face requires accepting access conditions and may ask for a token for the model files. Review the model pages and terms before accepting. The first run downloads weights; after caching, inference can run offline. Accuracy varies by language, accent, microphone, and background noise.


## Local UI and answer translation (no Groq text-generation calls)

When this service is deployed and its service key is configured on the main API, it also provides:

- \`POST /translate-text-batch\`: translate batches of English display strings into the selected Indian language using the English-to-Indic model.
- The main API's \`/askquery/translate-batch\` and \`/askquery/translate-answer\` endpoints proxy to this service. Repeated translations are cached in the API process.
- If the service or model is unavailable, the main API returns the original source strings instead of spending Groq tokens or blocking the screen. Check the main API log for \`path=original_fallback\` if a screen remains in English.

The English-to-Indic checkpoint is \`ai4bharat/indictrans2-en-indic-dist-200M\`. Its Hugging Face page requires accepting the model access conditions; after accepting, set \`HF_TOKEN\` on the speech-service deployment so it can download the model. The model is downloaded on first translation request and then cached by the model runtime. It is a self-hosted model, not a hosted translation API; resource usage depends on the machine running this service.

**Important scope:** this removes Groq text-generation calls used for display-string translation and translated-answer playback. The existing natural-language AI-query interpretation/SQL-generation path and Groq Whisper endpoint remain separate and may still use \`GROQ_API_KEY\`.

## Requirements

Use Python 3.10/3.11 in a dedicated environment. For a CUDA GPU, install a matching PyTorch and torchaudio build first from the official PyTorch installer at https://pytorch.org/get-started/locally/. Then install the remaining requirements. Do not use a CPU-only PyTorch wheel when you expect GPU inference.

Linux or WSL2 is recommended for the AI4Bharat model stack. On Windows, run these Linux-oriented commands in WSL2 with CUDA support configured.

    python3.10 -m venv .venv
    source .venv/bin/activate
    # Install a CUDA-compatible PyTorch/torchaudio pair for the installed NVIDIA driver:
    pip install torch torchaudio
    pip install -r speech_service/requirements.txt

## Configuration

Set these environment variables before starting the service:

- INDIC_SPEECH_SERVICE_API_KEY: long random shared secret; required.
- HF_TOKEN: optional read token after accepting the Hugging Face access conditions.
- VOICE_MODEL_DEVICE: optional cuda or cpu; by default the service selects CUDA if available.
- ENGLISH_WHISPER_SIZE: optional small (default), medium, or large-v3.
- INDIC_ASR_MODEL and INDIC_TRANSLATION_MODEL: optional overrides for Indic speech transcription and Indic-to-English text translation.
- INDIC_EN_TRANSLATION_MODEL: optional English-to-Indic model override; defaults to ai4bharat/indictrans2-en-indic-dist-200M.

Run from the Retail-Mind repository root:

    uvicorn speech_service.app:app --host 0.0.0.0 --port 8765

Health check: GET http://127.0.0.1:8765/health.

If you want self-hosted display translation and/or the optional self-hosted voice flow, configure INDIC_SPEECH_SERVICE_URL on the Retail Mind API and set the same INDIC_SPEECH_SERVICE_API_KEY on both services. The default Groq-based AI Query voice flow still needs GROQ_API_KEY for transcription and natural-language query interpretation.

Do not expose the speech service directly to the public internet. It is intended to be reached through the authenticated backend proxy. The main hosted API does not automatically run the 600M ASR model or translation model. If you host the speech service on your GPU PC, the backend must have a stable network route to it; localhost in the hosted backend will not reach your PC.

## Request path

Flutter records up to 60 seconds, then sends audio to authenticated POST /askquery/voice. The API calls this speech service with the shared key, receives transcript + English translation, and calls its existing /askquery route with the same owner/session. The existing RAG context retrieval, SQL generation, guarded database execution, and query history remain the source of truth.
