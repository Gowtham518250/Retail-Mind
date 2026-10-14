"""Fast, testable helpers for hybrid schema retrieval in the AI query endpoint."""
from __future__ import annotations
import math
import re
from typing import Any, Iterable

_STOPWORDS = set("""a an the and or but if then than that this these those i me my our ours we you your yours please show tell give find get list what which who whom when where why how can could would should do does did is are was were be been being have has had of for to from in on at by with about as into it its there here any each every per own""".split())
_DATE_WORDS = set("""today yesterday tomorrow daily weekly monthly yearly week month year day days weeks months years last past previous current recent since during between range period overall recently""".split())


def _normalise_token(token: str) -> str:
    token = token.casefold()
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def schema_query_terms(value: str) -> set[str]:
    raw = re.findall(r"[a-z][a-z0-9_]{1,}", str(value or "").casefold())
    return {_normalise_token(t) for t in raw if t not in _STOPWORDS and t not in _DATE_WORDS and len(_normalise_token(t)) >= 2}


def canonical_schema_query(query: str) -> str:
    """Stable cache key for paraphrases that target the same schema concepts."""
    terms = schema_query_terms(query)
    return " ".join(sorted(terms)) if terms else re.sub(r"\s+", " ", str(query or "").casefold()).strip()[:500]


def _content(entry: Any) -> str:
    return str(entry.get("content") or "") if isinstance(entry, dict) else str(entry or "")


def hybrid_rank_tables(query: str, catalog: dict[str, Any] | None, vector_ranked_tables: Iterable[str] = (), limit: int = 8) -> list[str]:
    """Fuse FAISS ranks with lexical schema matches using reciprocal-rank fusion."""
    limit = max(1, min(int(limit), 20))
    vector_names, seen = [], set()
    for value in vector_ranked_tables or ():
        name = str(value or "").strip()
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            vector_names.append(name)
    fused, display = {}, {}
    for rank, name in enumerate(vector_names, 1):
        key = name.casefold()
        display.setdefault(key, name)
        fused[key] = fused.get(key, 0.0) + 1.0 / (60.0 + rank)

    rows = []
    for name, entry in (catalog or {}).items():
        table_terms = schema_query_terms(str(name).replace("_", " "))
        all_terms = table_terms | schema_query_terms(_content(entry))
        rows.append({"name": str(name), "table_terms": table_terms, "all_terms": all_terms})
    terms = schema_query_terms(query)
    if terms and rows:
        df = {}
        for row in rows:
            for term in row["all_terms"]:
                df[term] = df.get(term, 0) + 1
        lexical, total = [], len(rows)
        for row in rows:
            score = 0.0
            for term in terms:
                if term in row["all_terms"]:
                    idf = math.log(1.0 + (total - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
                    score += idf * (3.0 if term in row["table_terms"] else 1.0)
            if score:
                lexical.append((score, row["name"]))
        lexical.sort(key=lambda x: (-x[0], x[1].casefold()))
        for rank, (_score, name) in enumerate(lexical, 1):
            key = name.casefold()
            display.setdefault(key, name)
            fused[key] = fused.get(key, 0.0) + 1.5 / (60.0 + rank)
    return [display[k] for k in sorted(fused, key=lambda k: (-fused[k], k))[:limit]]


def build_bounded_schema_context(sections: Iterable[str], max_chars: int = 18000) -> str:
    """Bound prompt size while retaining each schema section's head and tail."""
    cleaned = [str(s or "").strip() for s in sections if str(s or "").strip()]
    if not cleaned:
        return ""
    limit = max(1000, int(max_chars))
    sep = "\n\n"
    combined = sep.join(cleaned)
    if len(combined) <= limit:
        return combined
    budget = max(80, (limit - len(sep) * (len(cleaned) - 1)) // len(cleaned))
    marker = "\n...[schema middle omitted for prompt budget]...\n"
    bounded = []
    for section in cleaned:
        if len(section) <= budget:
            bounded.append(section)
        else:
            room = max(1, budget - len(marker))
            head = max(1, int(room * 0.72))
            tail_size = max(0, room - head)
            tail = section[-tail_size:] if tail_size else ""
            bounded.append(section[:head] + marker + tail)
    result = sep.join(bounded)
    return result[:limit] if len(result) > limit else result
