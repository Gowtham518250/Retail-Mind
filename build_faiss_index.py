import json
import os
from pathlib import Path
import requests
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

# The production-fix branch lost the catalog files, so restore the canonical
# catalog from the repository's main branch during the Render build.
API = "https://api.github.com/repos/Gowtham518250/Retail-Mind/contents/business_table_catalog?ref=main"
listing = requests.get(API, timeout=30)
listing.raise_for_status()
for item in listing.json():
    if item.get("type") != "file" or not item["name"].endswith(".txt"):
        continue
    target = CATALOG_DIR / item["name"]
    response = requests.get(item["download_url"], timeout=30)
    response.raise_for_status()
    target.write_text(response.text, encoding="utf-8")

documents = []
table_catalog = {}

for path in sorted(CATALOG_DIR.glob("*.txt")):
    content = path.read_text(encoding="utf-8").strip()
    table_catalog[path.stem] = {
        "source": f"business_table_catalog/{path.name}",
        "content": content,
    }
    start = 0
    while start < len(content):
        end = min(start + 700, len(content))
        chunk = content[start:end]
        documents.append(Document(
            page_content=chunk,
            metadata={"table": path.stem, "source": f"business_table_catalog/{path.name}"},
        ))
        if end == len(content):
            break
        start = max(end - 200, start + 1)

repo_id = "Xenova/all-MiniLM-L6-v2"
tokenizer_path = hf_hub_download(repo_id=repo_id, filename="tokenizer.json", cache_dir=str(CACHE))
model_path = hf_hub_download(repo_id=repo_id, filename="onnx/model.onnx", cache_dir=str(CACHE))
tokenizer = Tokenizer.from_file(tokenizer_path)
tokenizer.enable_truncation(max_length=256)
session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
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
