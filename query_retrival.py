import re
import os
from pathlib import Path

import os

from fastapi import Form, HTTPException, Depends, APIRouter
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.orm import Session
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from groq import Groq
from db import get_db
from security import get_current_user as check_current_user

BASE_DIR = Path(__file__).resolve().parent

# CPU-only embedding runtime for small Render instances.
# Uses the same all-MiniLM-L6-v2 model family as the existing FAISS index,
# but runs inference with ONNX Runtime instead of PyTorch.
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

MODEL_REPO = "Xenova/all-MiniLM-L6-v2"
MODEL_CACHE = Path(os.getenv("HF_HOME", "/tmp/.cache/huggingface"))
MODEL_CACHE.mkdir(parents=True, exist_ok=True)

TOKENIZER_PATH = hf_hub_download(
    repo_id=MODEL_REPO,
    filename="tokenizer.json",
    cache_dir=str(MODEL_CACHE),
)
MODEL_PATH = hf_hub_download(
    repo_id=MODEL_REPO,
    filename="onnx/model.onnx",
    cache_dir=str(MODEL_CACHE),
)

_TOKENIZER = Tokenizer.from_file(TOKENIZER_PATH)
_TOKENIZER.enable_truncation(max_length=256)
_SESSION = ort.InferenceSession(
    MODEL_PATH,
    providers=["CPUExecutionProvider"],
)

class MiniLMONNXEmbeddings(Embeddings):
    """all-MiniLM-L6-v2 embeddings without loading PyTorch."""

    @staticmethod
    def _embed(text: str) -> list[float]:
        encoded = _TOKENIZER.encode(text)
        input_ids = np.asarray([encoded.ids], dtype=np.int64)
        attention_mask = np.asarray([encoded.attention_mask], dtype=np.int64)
        token_type_ids = np.asarray([encoded.type_ids], dtype=np.int64)

        inputs = {}
        input_names = {item.name for item in _SESSION.get_inputs()}
        if "input_ids" in input_names:
            inputs["input_ids"] = input_ids
        if "attention_mask" in input_names:
            inputs["attention_mask"] = attention_mask
        if "token_type_ids" in input_names:
            inputs["token_type_ids"] = token_type_ids

        outputs = _SESSION.run(None, inputs)
        token_embeddings = outputs[0]

        mask = attention_mask[..., None].astype(np.float32)
        pooled = (token_embeddings * mask).sum(axis=1) / np.clip(
            mask.sum(axis=1), 1e-9, None
        )

        # Match the normalized Sentence-Transformers representation.
        norm = np.linalg.norm(pooled, axis=1, keepdims=True)
        pooled = pooled / np.clip(norm, 1e-12, None)
        return pooled[0].astype(np.float32).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

embeddings = MiniLMONNXEmbeddings()
faiss_index = Path(os.getenv("FAISS_INDEX_PATH", BASE_DIR / "faiss_index"))
if not faiss_index.is_absolute():
    faiss_index = BASE_DIR / faiss_index
vectorstore = FAISS.load_local(
    str(faiss_index),
    embeddings,
    allow_dangerous_deserialization=True,
)

app= APIRouter()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
@app.post("/askquery")
async def ask_query(query:str=Form(...),db:Session=Depends(get_db),user_id:int=Depends(check_current_user)):
    print("🔥 ENDPOINT CALLED")
    print("QUERY:", query)

    answer = vectorstore.similarity_search(query, k=3)

    print("Relevant database information:")
    for doc in answer:
        print("-----")
        print(doc.page_content)
        print("Table:", doc.metadata.get("table"))
        print("Source:", doc.metadata.get("source"))
    table_paths = []
    for doc in answer:
        source_path = doc.metadata.get("source")
        if source_path  not in table_paths:
            table_paths.append(source_path)
    retrived_table_information=[]
    for path in table_paths:
        try:
            source_name = Path(str(path).replace("\\", "/")).name
            catalog_path = BASE_DIR / "business_table_catalog" / source_name
            if catalog_path.suffix != ".txt" or not catalog_path.is_file():
                continue
            with catalog_path.open("r", encoding="utf-8") as file:
                content = file.read()
                retrived_table_information.append(content)
        except Exception as e:
            print(f"Error reading file {path}: {str(e)}")
    print("Retrieved table information:")
    for content in retrived_table_information:
        print(content)
    prompt = ChatPromptTemplate.from_template(
    
    """You are a PostgreSQL Text-to-SQL generator for a retail management system.


    You will receive:

    1. A user's natural-language question.
    2. Complete table information retrieved from the database schema catalog.

    Your job is to generate the correct SQL query.

    Rules:

    - Carefully understand the user's question.
    - Examine all retrieved table information.
    - Select the table that is most relevant to the user's question.
    - Use ONLY tables and columns that appear in the retrieved table information.
    - Follow the QUERY GUIDANCE provided in the retrieved table information.
    - Do NOT invent table names.
    - Do NOT invent column names.
    - Do NOT invent relationships.
    - Do NOT assume a column exists just because it would normally exist in a database.
    - Prefer the source table specified by the QUERY GUIDANCE.
    - Generate PostgreSQL-compatible SQL.
    - Generate a single-table, read-only SELECT query only.
    - Always filter rows with `user_id = :user_id`. Do not use a literal user ID.
    - Do not use JOINs, subqueries, OR, or UNION.
    - Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
    - For date-related questions such as "today", follow the table's documented business-date guidance.
    - If the question requires information from multiple related tables and the relationships are explicitly provided, you may use a JOIN.
    - If the retrieved information is insufficient to answer the question, state that the schema information is insufficient instead of inventing information.

    Retrieved complete table information:

    {retrieved_table_information}

    User question:

    {question}

    Return the result in exactly this format:

    TABLE: <selected table or tables>

    SQL:
    <postgresql query>

    Do not provide any explanation outside this format.
    """ 
    )
    retrived_table_information_str = "\n\n".join(retrived_table_information)

    formatted_prompt = prompt.format(
            retrieved_table_information=retrived_table_information_str,
            question=query
        )
    completion = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        messages=[{"role": "user", "content": formatted_prompt}],
        temperature=0.6,
        max_completion_tokens=2048,
        top_p=0.95,
        reasoning_effort="default",
        stream=True,
        stop=None,
    )

    generated_parts = []
    for chunk in completion:
        delta = getattr(chunk.choices[0], "delta", None)
        content = getattr(delta, "content", None) or ""
        if content:
            generated_parts.append(content)

    generated_text = "".join(generated_parts).strip()
    sql_match = re.search(r"\bSQL\s*:\s*(.+)", generated_text, re.IGNORECASE | re.DOTALL)
    if not sql_match:
        raise HTTPException(status_code=400, detail="The generated response did not contain SQL.")

    sql = sql_match.group(1).strip().strip("`").strip()
    sql = re.sub(r";\s*$", "", sql)
    if (
        not re.match(r"^SELECT\b", sql, re.IGNORECASE)
        or ";" in sql
        or re.search(r"\b(JOIN|UNION|OR|INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|WITH)\b", sql, re.IGNORECASE)
        or not re.search(r"\buser_id\s*=\s*:user_id\b", sql, re.IGNORECASE)
    ):
        raise HTTPException(
            status_code=400,
            detail="Generated SQL must be a single read-only SELECT scoped by user_id = :user_id.",
        )

    try:
        rows = db.execute(text(sql), {"user_id": user_id}).mappings().all()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="The generated SQL could not be executed.") from exc

    return {"query": query, "sql": sql, "results": jsonable_encoder([dict(row) for row in rows])}
        