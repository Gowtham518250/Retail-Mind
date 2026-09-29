import json
import re
import os
import calendar
from datetime import date, timedelta
from pathlib import Path

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

# Configure Hugging Face before importing huggingface_hub so Render never
# falls back to the non-writable /app cache, including Xet.
MODEL_CACHE = Path("/tmp/.cache/huggingface")
MODEL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(MODEL_CACHE)
os.environ["HF_XET_CACHE"] = str(MODEL_CACHE / "xet")
os.environ["HF_HUB_CACHE"] = str(MODEL_CACHE / "hub")
os.environ["HF_HUB_DISABLE_XET"] = "1"

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

MODEL_REPO = "Xenova/all-MiniLM-L6-v2"

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
configured_faiss = Path(os.getenv("FAISS_INDEX_PATH", ""))
faiss_index = configured_faiss if configured_faiss.is_absolute() else (
    BASE_DIR / configured_faiss if str(configured_faiss) else BASE_DIR / "faiss_index"
)
# Ignore stale Render paths such as /app/faiss_index when the build produced
# the index inside the deployed repository.
if not (faiss_index / "index.faiss").is_file() or not (faiss_index / "index.pkl").is_file():
    faiss_index = BASE_DIR / "faiss_index"
if not (faiss_index / "index.faiss").is_file() or not (faiss_index / "index.pkl").is_file():
    raise RuntimeError(
        f"FAISS index files are missing. Expected {faiss_index / 'index.faiss'} and {faiss_index / 'index.pkl'}."
    )
vectorstore = FAISS.load_local(
    str(faiss_index),
    embeddings,
    allow_dangerous_deserialization=True,
)

# Complete table catalog generated alongside the FAISS index. This avoids
# depending on the original .txt files being present at runtime and lets us
# expand each retrieved chunk back to the full table definition.
catalog_json = Path(
    os.getenv("RAG_TABLE_CATALOG_PATH", str(BASE_DIR / "rag_table_catalog.json"))
)
if catalog_json.is_file():
    try:
        with catalog_json.open("r", encoding="utf-8") as file:
            full_table_catalog = json.load(file)
    except Exception as exc:
        print(f"Could not load complete RAG catalog {catalog_json}: {exc}")
        full_table_catalog = {}
else:
    full_table_catalog = {}

app= APIRouter()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
@app.post("/askquery")
async def ask_query(query:str=Form(...),db:Session=Depends(get_db),user_id:int=Depends(check_current_user)):
    print("🔥 ENDPOINT CALLED")
    print("QUERY:", query)

    answer = vectorstore.similarity_search(query, k=6)

    print("Relevant database information:")
    for doc in answer:
        print("-----")
        print(doc.page_content)
        print("Table:", doc.metadata.get("table"))
        print("Source:", doc.metadata.get("source"))
    table_paths = []
    retrived_table_information = []
    retrieved_table_records = []
    processed_tables = set()

    # FAISS returns chunks, but SQL generation needs complete table context.
    # Expand each selected table using rag_table_catalog.json.

    # The current app's primary sale/billing flow writes invoices
    # (the mobile SaleService syncs an invoice), while the legacy sales table
    # can contain older/raw sale rows. Use invoices for normal sales/billing
    # questions and sales only for explicit raw-sales-table questions.
    sales_intent = bool(
        re.search(r"\b(sale|sales|sold|revenue|turnover|billed|billing|bill|bills)\b", query, re.IGNORECASE)
        and not re.search(r"\b(sales\s+table|raw\s+sales|raw\s+sale|sale\s+rows?)\b", query, re.IGNORECASE)
    )
    raw_sales_intent = bool(
        re.search(r"\b(sales\s+table|raw\s+sales|raw\s+sale|sale\s+rows?)\b", query, re.IGNORECASE)
    )
    invoice_intent = bool(
        re.search(r"\b(invoice|invoices|bill|bills|billing)\b", query, re.IGNORECASE)
    )

    if sales_intent and not raw_sales_intent and "invoices" not in processed_tables:
        invoice_content = full_table_catalog.get("invoices")

        if isinstance(invoice_content, dict):
            invoice_content = invoice_content.get("content", "")

        if isinstance(invoice_content, str) and invoice_content.strip():
            retrived_table_information.append(invoice_content)
            retrieved_table_records.append({
                "table": "invoices",
                "source": "business_table_catalog/invoices.txt",
                "content": invoice_content,
                "retrieval": "full_table_catalog_intent",
            })
            processed_tables.add("invoices")

    if raw_sales_intent and "sales" not in processed_tables:
        sales_content = full_table_catalog.get("sales")

        if isinstance(sales_content, dict):
            sales_content = sales_content.get("content", "")

        if isinstance(sales_content, str) and sales_content.strip():
            retrived_table_information.append(sales_content)
            retrieved_table_records.append({
                "table": "sales",
                "source": "business_table_catalog/sales.txt",
                "content": sales_content,
                "retrieval": "full_table_catalog_intent",
            })
            processed_tables.add("sales")

    for doc in answer:
        source_path = doc.metadata.get("source")
        table_name = doc.metadata.get("table")
        source_name = Path(str(source_path).replace("\\", "/")).name if source_path else None
        catalog_key = table_name or (Path(source_name).stem if source_name else None)

        if source_path not in table_paths:
            table_paths.append(source_path)

        if catalog_key and catalog_key not in processed_tables:
            catalog_entry = full_table_catalog.get(catalog_key)
            # Support both catalog formats so an already-deployed JSON file
            # with {"source": ..., "content": ...} keeps working.
            if isinstance(catalog_entry, dict):
                content = catalog_entry.get("content", "")
                catalog_source = catalog_entry.get("source", source_path)
            else:
                content = catalog_entry or ""
                catalog_source = source_path

            if isinstance(content, str) and content.strip():
                retrived_table_information.append(content)
                retrieved_table_records.append({
                    "table": catalog_key,
                    "source": catalog_source,
                    "content": content,
                    "retrieval": "full_table_catalog",
                })
                processed_tables.add(catalog_key)
                continue

        # Legacy fallback for an already-deployed instance without the JSON catalog.
        if source_name and catalog_key not in processed_tables:
            catalog_path = BASE_DIR / "business_table_catalog" / source_name
            if catalog_path.suffix == ".txt" and catalog_path.is_file():
                try:
                    content = catalog_path.read_text(encoding="utf-8")
                    retrived_table_information.append(content)
                    retrieved_table_records.append({
                        "table": catalog_key,
                        "source": source_path,
                        "content": content,
                        "retrieval": "catalog_file",
                    })
                    processed_tables.add(catalog_key)
                    continue
                except Exception as exc:
                    print(f"Error reading catalog file {catalog_path}: {exc}")

        # Final fallback: expose the FAISS chunk itself.
        content = str(getattr(doc, "page_content", "") or "").strip()
        if content:
            retrived_table_information.append(content)
            retrieved_table_records.append({
                "table": catalog_key,
                "source": source_path,
                "content": content,
                "retrieval": "faiss_chunk",
            })
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
    - Use ONLY tables, columns, and relationships explicitly present in the retrieved catalog.
    - Treat QUERY GUIDANCE as authoritative business semantics.
    - Generate PostgreSQL-compatible SQL.
    - JOINs are allowed only when the retrieved catalog explicitly documents the relationship.
    - For tables with user_id, scope using user_id = :user_id.
    - For the sales table, shopkeeper_id is the authenticated shop owner scope, so use shopkeeper_id = :user_id.
    - The catalog may contain example placeholders such as :shop_id or :business_date. Ignore those example parameter names: the only runtime parameter available is :user_id. For business-date filters, use the documented date column and a SQL date expression directly.
    - Never invent a relationship or literal user/shop ID.
    - Do not assume a column exists just because it would normally exist in a database.
    - Use the documented date column and business-date/timezone guidance for date/range questions.
    - IMPORTANT: Do not add a date filter unless the user explicitly asks for a date or time range.
    - If the user says "today", filter to today's Asia/Kolkata business date only.
    - If the user gives a specific date, filter to that exact date only.
    - If the user gives a range such as yesterday, this week, last week, this month, or last month, use that exact range.
    - If no date or range is mentioned, do not silently assume today; answer across the full available period requested by the question.
    - For normal sales questions in this application, use the invoices table because the current sale workflow records completed sales as invoices:
      - count completed/active invoices for sale counts;
      - use invoices.total_amount for billed sales amount;
      - exclude CANCELLED and DRAFT invoices;
      - use invoice_line_items for billed item/unit quantities.
    - Use the legacy sales table only when the user explicitly asks for raw sales rows or the sales table.
    - Do not combine sales and invoices totals unless the user explicitly asks for a reconciliation; the application can record both and they may overlap.
    - For "today", use the shop's business date (Asia/Kolkata) rather than the database server timezone.
    - Distinguish COUNT(rows), SUM(quantity), revenue, billed value, cash received, and stock exactly as documented.
    - Generate exactly one read-only SELECT query.
    - Do not use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, COPY, or multiple statements.
    - The query must contain the authenticated parameter :user_id somewhere in its scope logic.
    - If the catalog is insufficient, do not invent a schema or relationship.

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
    try:
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=0.1,
            max_tokens=2048,
            top_p=0.9,
            stream=True,
            stop=None,
        )

        generated_parts = []
        for chunk in completion:
            if not getattr(chunk, "choices", None):
                continue
            delta = getattr(chunk.choices[0], "delta", None)
            content = getattr(delta, "content", None) or ""
            if content:
                generated_parts.append(content)
    except Exception as exc:
        print("Groq completion failed:")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Exception: {exc}")
        raise HTTPException(status_code=502, detail="The SQL generation service is temporarily unavailable.") from exc

    generated_text = "".join(generated_parts).strip()
    sql_match = re.search(r"\bSQL\s*:\s*(.+)", generated_text, re.IGNORECASE | re.DOTALL)
    if not sql_match:
        raise HTTPException(status_code=400, detail="The generated response did not contain SQL.")

    sql = sql_match.group(1).strip().strip("`").strip()
    sql = re.sub(r";\s*$", "", sql)

    # Normalize catalog example placeholders to the single authenticated
    # parameter supported by this endpoint.
    sql = re.sub(r":shop_id\b", ":user_id", sql, flags=re.IGNORECASE)
    # The endpoint binds only :user_id. Convert the catalog's example
    # :business_date placeholder to a SQL date expression as well.
    # Normalize business-date placeholders before the generic CURRENT_DATE
    # rule. The target columns are DATE columns, so keep the expression as DATE.
    sql = re.sub(
        r":business_date\b",
        "(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\bCURRENT_DATE\s+AT\s+TIME\s+ZONE\s+'Asia/Kolkata'\b",
        "(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\(\s*\((CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date\)\s+AT\s+TIME\s+ZONE\s+'Asia/Kolkata'\s*\)",
        r"(\1)",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\bCURRENT_DATE\b",
        "(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date",
        sql,
        flags=re.IGNORECASE,
    )

    # For common sales metrics, use a deterministic source preference:
    # current invoices are canonical for the modern sale workflow; when there
    # are no qualifying invoice rows for the requested period, fall back to
    # legacy sales rows. Crucially, the requested date/range controls the
    # filter: no date mentioned means no date filter.
    sale_metric_intent = bool(
        re.search(r"\b(sale|sales|sold|revenue|turnover)\b", query, re.IGNORECASE)
        and not re.search(r"\b(invoice|invoices|bill|bills|billing)\b", query, re.IGNORECASE)
        and not raw_sales_intent
    )
    if sale_metric_intent:
        normalized_query = re.sub(r"\s+", " ", query.lower()).strip()

        wants_units = bool(
            re.search(r"\b(how many|number of|total)\b.*\b(items?|units?)\b.*\b(sold|sales?)\b", normalized_query)
            or re.search(r"\b(items?|units?)\b.*\b(sold|sales?)\b", normalized_query)
        )
        wants_count = bool(
            re.search(r"\b(how many|number of)\b.*\bsales?\b", normalized_query)
            or re.search(r"\b(count|number)\s+of\s+sales?\b", normalized_query)
        )

        def build_date_filters(column_name: str):
            today_expr = "(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date"

            if re.search(r"\b(today|todays|today's)\b", normalized_query):
                return f"{column_name} = {today_expr}", "today"

            if re.search(r"\byesterday\b", normalized_query):
                return f"{column_name} = ({today_expr} - INTERVAL '1 day')::date", "yesterday"

            # Exact ISO date: 2026-09-20
            iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", normalized_query)
            if iso_match:
                y, m, d = map(int, iso_match.groups())
                try:
                    exact = date(y, m, d).isoformat()
                    return f"{column_name} = DATE '{exact}'", exact
                except ValueError:
                    pass

            # Exact Indian/common date: 20/09/2026 or 20-09-2026
            dmy_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", normalized_query)
            if dmy_match:
                d, m, y = map(int, dmy_match.groups())
                try:
                    exact = date(y, m, d).isoformat()
                    return f"{column_name} = DATE '{exact}'", exact
                except ValueError:
                    pass

            # Named month + day, with optional year: "September 20" / "September 20, 2026"
            month_names = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12,
            }
            month_pattern = "|".join(month_names)
            month_match = re.search(
                rf"\b({month_pattern})\s+(\d{{1,2}})(?:,\s*(20\d{{2}}))?\b",
                normalized_query,
                re.IGNORECASE,
            )
            if month_match:
                month_num = month_names[month_match.group(1).lower()]
                day_num = int(month_match.group(2))
                year_num = int(month_match.group(3)) if month_match.group(3) else date.today().year
                try:
                    exact = date(year_num, month_num, day_num).isoformat()
                    return f"{column_name} = DATE '{exact}'", exact
                except ValueError:
                    pass

            # Common natural-language ranges.
            if re.search(r"\b(this week|current week)\b", normalized_query):
                return (
                    f"{column_name} >= date_trunc('week', {today_expr})::date "
                    f"AND {column_name} < (date_trunc('week', {today_expr}) + INTERVAL '7 days')::date",
                    "this week",
                )

            if re.search(r"\b(last week|previous week)\b", normalized_query):
                return (
                    f"{column_name} >= (date_trunc('week', {today_expr}) - INTERVAL '7 days')::date "
                    f"AND {column_name} < date_trunc('week', {today_expr})::date",
                    "last week",
                )

            if re.search(r"\b(this month|current month)\b", normalized_query):
                return (
                    f"{column_name} >= date_trunc('month', {today_expr})::date "
                    f"AND {column_name} < (date_trunc('month', {today_expr}) + INTERVAL '1 month')::date",
                    "this month",
                )

            if re.search(r"\b(last month|previous month)\b", normalized_query):
                return (
                    f"{column_name} >= (date_trunc('month', {today_expr}) - INTERVAL '1 month')::date "
                    f"AND {column_name} < date_trunc('month', {today_expr})::date",
                    "last month",
                )

            return "", "all time"

        invoice_date_filter, date_scope = build_date_filters("invoice_date")
        sales_date_filter, _ = build_date_filters("sale_date")

        invoice_where = (
            "user_id = :user_id AND status NOT IN ('CANCELLED', 'DRAFT')"
            + (f" AND {invoice_date_filter}" if invoice_date_filter else "")
        )
        sales_where = (
            "shopkeeper_id = :user_id"
            + (f" AND {sales_date_filter}" if sales_date_filter else "")
        )

        if wants_count:
            sql = (
                "WITH invoice_rows AS ("
                "SELECT COUNT(*)::bigint AS cnt "
                "FROM invoices "
                f"WHERE {invoice_where}"
                "), sales_rows AS ("
                "SELECT COUNT(*)::bigint AS cnt "
                "FROM sales "
                f"WHERE {sales_where}"
                ") "
                "SELECT CASE WHEN invoice_rows.cnt > 0 "
                "THEN invoice_rows.cnt ELSE sales_rows.cnt END AS sales_count "
                "FROM invoice_rows CROSS JOIN sales_rows"
            )
            generated_text = "TABLE: invoices (fallback: sales)\n\nSQL:\n" + sql
        elif wants_units:
            sql = (
                "WITH invoice_rows AS ("
                "SELECT COALESCE(SUM(ili.quantity), 0)::numeric AS qty "
                "FROM invoice_line_items ili "
                "JOIN invoices i ON i.id = ili.invoice_id "
                f"WHERE i.{invoice_where.replace('user_id', 'user_id', 1) if False else 'user_id = :user_id'} "
                "AND i.status NOT IN ('CANCELLED', 'DRAFT')"
                + (f" AND i.{invoice_date_filter}" if invoice_date_filter else "")
                + "), sales_rows AS ("
                "SELECT COALESCE(SUM(quantity), 0)::numeric AS qty "
                "FROM sales "
                f"WHERE {sales_where}"
                ") "
                "SELECT CASE WHEN invoice_rows.qty > 0 "
                "THEN invoice_rows.qty ELSE sales_rows.qty END AS total_units_sold "
                "FROM invoice_rows CROSS JOIN sales_rows"
            )
            generated_text = "TABLE: invoices (fallback: sales)\n\nSQL:\n" + sql
        elif re.search(r"\b(total|amount|revenue|turnover)\b", normalized_query):
            sql = (
                "WITH invoice_rows AS ("
                "SELECT COUNT(*)::bigint AS cnt, "
                "COALESCE(SUM(total_amount), 0)::numeric AS total "
                "FROM invoices "
                f"WHERE {invoice_where}"
                "), sales_rows AS ("
                "SELECT COUNT(*)::bigint AS cnt, "
                "COALESCE(SUM(total), 0)::numeric AS total "
                "FROM sales "
                f"WHERE {sales_where}"
                ") "
                "SELECT CASE WHEN invoice_rows.cnt > 0 "
                "THEN invoice_rows.total ELSE sales_rows.total END AS total_sales_amount "
                "FROM invoice_rows CROSS JOIN sales_rows"
            )
            generated_text = "TABLE: invoices (fallback: sales)\n\nSQL:\n" + sql

    print("Generated SQL:")
    print(sql)

    if (
        not re.match(r"^SELECT\b", sql, re.IGNORECASE)
        or ";" in sql
        or re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|CALL|DO|EXECUTE|MERGE|VACUUM|ANALYZE)\b", sql, re.IGNORECASE)
        or re.search(r"\b(pg_sleep|pg_terminate_backend|pg_cancel_backend|dblink|lo_import|lo_export)\s*\(", sql, re.IGNORECASE)
        or not re.search(r":user_id\b", sql, re.IGNORECASE)
    ):
        print("SQL validation failed for generated SQL:")
        print(sql)
        raise HTTPException(
            status_code=400,
            detail="Generated SQL must be a single read-only SELECT scoped with the authenticated :user_id parameter.",
        )

    try:
        rows = db.execute(text(sql), {"user_id": user_id}).mappings().all()
    except Exception as exc:
        db.rollback()
        print("SQL execution failed:")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Exception: {exc}")
        print("SQL:")
        print(sql)
        raise HTTPException(status_code=400, detail="The generated SQL could not be executed.") from exc

    return {
        "query": query,
        "generated_sql": sql,
        "generated_model_response": generated_text,
        "retrieved_table_information": retrieved_table_records,
        "sql": sql,
        "results": jsonable_encoder([dict(row) for row in rows]),
    }
        