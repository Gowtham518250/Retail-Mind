import json
import os
import shutil
from pathlib import Path
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

BASE_DIR = Path(__file__).resolve().parent
CACHE = BASE_DIR / ".cache" / "huggingface"
CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(CACHE)
os.environ["HF_XET_CACHE"] = str(CACHE / "xet")
os.environ["HF_HUB_CACHE"] = str(CACHE / "hub")
os.environ["HF_HUB_DISABLE_XET"] = "1"

CATALOG_DIR = BASE_DIR / "business_table_catalog"
CATALOG_DIR.mkdir(parents=True, exist_ok=True)


def _append_document_chunks(documents, table_name, content, source):
    """Add overlapping schema chunks for FAISS from a trusted local catalog entry."""
    content = str(content or "").strip()
    start = 0
    while start < len(content):
        end = min(start + 700, len(content))
        documents.append(Document(
            page_content=content[start:end],
            metadata={"table": table_name, "source": source},
        ))
        if end == len(content):
            break
        start = max(end - 200, start + 1)


def _load_schema_catalog():
    """Prefer checked-in .txt schemas, falling back to the checked-in JSON catalog.

    Render builds from the production branch, which contains rag_table_catalog.json
    and the generated FAISS files but does not contain business_table_catalog/*.txt.
    Fetching that directory from GitHub's main branch was brittle and returned 404.
    """
    documents = []
    table_catalog = {}
    catalog_files = sorted(CATALOG_DIR.glob("*.txt"))

    if catalog_files:
        for catalog_file in catalog_files:
            content = catalog_file.read_text(encoding="utf-8").strip()
            if not content:
                continue
            table_name = catalog_file.stem
            source = f"business_table_catalog/{catalog_file.name}"
            table_catalog[table_name] = content
            _append_document_chunks(documents, table_name, content, source)
    else:
        catalog_path = BASE_DIR / "rag_table_catalog.json"
        if not catalog_path.is_file():
            raise RuntimeError(
                "No business schema files or rag_table_catalog.json found. "
                "Commit the schema catalog before building the FAISS index."
            )
        with catalog_path.open("r", encoding="utf-8") as catalog_file:
            stored_catalog = json.load(catalog_file)
        if not isinstance(stored_catalog, dict) or not stored_catalog:
            raise RuntimeError(f"Schema catalog is empty or invalid: {catalog_path}")

        for table_name, entry in sorted(stored_catalog.items()):
            if isinstance(entry, dict):
                content = str(entry.get("content") or "").strip()
                source = str(
                    entry.get("source") or f"business_table_catalog/{table_name}.txt"
                )
            else:
                content = str(entry or "").strip()
                source = f"business_table_catalog/{table_name}.txt"
            if not content:
                continue
            table_catalog[str(table_name)] = content
            _append_document_chunks(documents, str(table_name), content, source)

    if not documents or not table_catalog:
        raise RuntimeError("No usable schema entries found to build the FAISS index.")
    return documents, table_catalog


documents, table_catalog = _load_schema_catalog()

repo_id = "Xenova/all-MiniLM-L6-v2"
MODEL_ASSETS_DIR = BASE_DIR / "model_assets"
MODEL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Download the model during the build, then package standalone copies inside
# the deployment artifact. API startup must not depend on Hugging Face network
# availability or a build-container cache being shared with the runtime.
downloaded_tokenizer_path = hf_hub_download(
    repo_id=repo_id,
    filename="tokenizer.json",
    cache_dir=str(CACHE),
)
downloaded_model_path = hf_hub_download(
    repo_id=repo_id,
    filename="onnx/model.onnx",
    cache_dir=str(CACHE),
)
tokenizer_path = MODEL_ASSETS_DIR / "tokenizer.json"
model_path = MODEL_ASSETS_DIR / "model.onnx"
shutil.copy2(downloaded_tokenizer_path, tokenizer_path)
shutil.copy2(downloaded_model_path, model_path)
print(f"Packaged local embedding assets in {MODEL_ASSETS_DIR}", flush=True)

tokenizer = Tokenizer.from_file(str(tokenizer_path))
tokenizer.enable_truncation(max_length=256)
session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
input_names = {item.name for item in session.get_inputs()}

def embed_one(value):
    encoded = tokenizer.encode(value)
    attention = np.asarray([encoded.attention_mask], dtype=np.int64)
    inputs = {
        "input_ids": np.asarray([encoded.ids], dtype=np.int64),
        "attention_mask": attention,
        "token_type_ids": np.asarray([encoded.type_ids], dtype=np.int64),
    }
    inputs = {k: v for k, v in inputs.items() if k in input_names}
    output = session.run(None, inputs)[0]
    mask = attention[..., None].astype(np.float32)
    pooled = (output * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    pooled /= np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
    return pooled[0].astype(np.float32).tolist()

class BuildEmbeddings:
    def embed_documents(self, texts):
        return [embed_one(t) for t in texts]
    def embed_query(self, text):
        return embed_one(text)

embeddings = BuildEmbeddings()
index_dir = BASE_DIR / "faiss_index"
index_dir.mkdir(parents=True, exist_ok=True)
vectorstore = FAISS.from_documents(documents, embeddings)
vectorstore.save_local(str(index_dir))

# Persist the complete catalog separately from the FAISS chunks. FAISS
# retrieval is chunk-based, while SQL generation needs the full schema text
# for every selected table.
catalog_path = BASE_DIR / "rag_table_catalog.json"
catalog_path.write_text(
    json.dumps(table_catalog, ensure_ascii=False),
    encoding="utf-8",
)

print(
    f"Built FAISS index with {len(documents)} chunks in {index_dir}; "
    f"saved {len(table_catalog)} complete tables to {catalog_path}"
)
