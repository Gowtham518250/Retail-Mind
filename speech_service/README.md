# Retail Mind open-source Indian voice service

This service is a self-hosted audio-to-English adapter for Ask Retail Mind. It uses no paid speech or translation API.

## Model choices

- **Indic speech recognition:** [AI4Bharat IndicConformer](https://github.com/AI4Bharat/IndicConformerASR), MIT, covers the 22 scheduled Indian languages.
- **Indian-language to English translation:** [IndicTrans2 Indic-En Distilled 200M](https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M), MIT model checkpoint.
- **English speech:** faster-whisper/Whisper locally; set `ENGLISH_WHISPER_SIZE` to `small`, `medium`, or `large-v3` to trade latency for accuracy.

After downloading/caching the weights, inference runs locally with no paid inference API. Model quality still varies by language, accent, mic and recording conditions; it must be evaluated on real shopkeeper speech.

## Setup on a local GPU PC

Use Linux/WSL2 for the NeMo speech dependencies. Create and activate the environment first, then install a matching PyTorch + torchaudio pair for your driver before installing the AI4Bharat NeMo fork:

```bash
python3.10 -m venv .venv
source .venv/bin/activate

# Choose the matching CUDA build at https://pytorch.org/get-started/locally/
pip install torch torchvision torchaudio

git clone https://github.com/AI4Bharat/NeMo.git
cd NeMo
git checkout nemo-v2
bash reinstall.sh
cd ..

pip install -r speech_service/requirements.txt
```

For Windows, run these Linux-oriented commands inside WSL2. Select compatible CUDA/PyTorch/torchaudio versions for your installed driver; do not install a CPU-only build if you expect GPU inference. If NeMo's installer adjusts dependency versions, install `speech_service/requirements.txt` afterward and verify both imports before serving.

IndicTrans2's Hugging Face model page may require accepting its free model-access conditions while signed in. Create a read-only Hugging Face token and set it as `HF_TOKEN` for the initial download. You do not need a paid plan or inference endpoint.

## Environment

Set these in the shell before starting the service:

- `INDIC_SPEECH_SERVICE_API_KEY`: a long random shared secret. It must match the same key set in the Retail Mind backend.
- `HF_TOKEN`: optional except where model access requires it.
- `VOICE_MODEL_DEVICE`: optional; `cuda` or `cpu`. Defaults to CUDA when available.
- `ENGLISH_WHISPER_SIZE`: defaults to `small`.

Do not expose this service directly to the public internet. The backend proxy authenticates the shop owner and sends the shared service key.

Start the service:

```bash
uvicorn speech_service.app:app --host 0.0.0.0 --port 8765
```

Health check: `GET http://127.0.0.1:8765/health`.

Set the following environment variables on the Retail Mind API service:

- `INDIC_SPEECH_SERVICE_URL=http://127.0.0.1:8765` when both run on the same machine/network namespace (otherwise use the private service URL reachable by the backend).
- `INDIC_SPEECH_SERVICE_API_KEY` to the same secret as the voice service.

The frontend records audio, sends it to authenticated `POST /askquery/voice`, receives the transcript and English translation, and the backend sends that English question through the existing `/askquery` pipeline. That pipeline keeps the current RAG table retrieval, SQL generation, guarded execution, and query history.

## Important deployment note

The main Retail Mind backend is currently on a CPU-oriented hosted environment. Do not assume this GPU speech service is available just because the API is deployed. Deploy it on your GPU PC or another machine you control and configure a secure, reachable private endpoint. The typed-query path continues to work when the speech service is offline.
