from types import SimpleNamespace

import pytest

from query_retrival import (
    _SESSION,
    _TOKENIZER,
    _fast_worker_payroll_query,
    _is_explicit_worker_salary_guidance_query,
    _select_distinct_schema_tables,
)


class _DatabaseMustNotBeUsed:
    def query(self, *_args, **_kwargs):
        raise AssertionError("Payment-history questions must not be answered from attendance.")


@pytest.mark.parametrize(
    "question",
    [
        "How much have I paid worker Ganesh this month?",
        "Show the payment history for employee Ganesh",
        "List transactions for worker Ganesh",
        "What amount did I transfer to staff last week?",
        "Show payment records for workers",
        "How much salary was already paid to Ganesh?",
        "Ganesh's salary payment record from last week",
        "What is Ganesh's salary?",
        "Show me Ganesh's attendance",
        "Which staff member worked the most hours last month?",
    ],
)
def test_unrecognized_or_historical_worker_questions_fall_through_to_general_sql(question):
    assert not _is_explicit_worker_salary_guidance_query(question)
    assert _fast_worker_payroll_query(question, _DatabaseMustNotBeUsed(), 10) is None


@pytest.mark.parametrize(
    "question",
    [
        "My worker Ganesh is asking for salary. How much should I pay based on attendance?",
        "What salary should I pay Ganesh for this month?",
        "How much should I pay my employee according to attendance?",
        "Calculate the amount to pay based on the attendance",
        "What is the configured worker salary for Ganesh?",
    ],
)
def test_only_explicit_salary_guidance_uses_worker_payroll_shortcut(question):
    assert _is_explicit_worker_salary_guidance_query(question)



def _document(table, chunk):
    return SimpleNamespace(
        metadata={"table": table, "source": f"business_table_catalog/{table}.txt"},
        page_content=chunk,
    )


def test_schema_retrieval_keeps_best_chunk_per_table_in_rank_order():
    invoice_best = _document("invoices", "invoice schema best chunk")
    invoice_duplicate = _document("invoices", "another invoice chunk")
    payments = _document("payments", "payment schema")
    workers = _document("workers", "worker schema")
    customers = _document("customers", "customer schema")

    selected = _select_distinct_schema_tables(
        [
            (invoice_best, 0.05),
            (invoice_duplicate, 0.08),
            (payments, 0.10),
            (workers, 0.12),
            (customers, 0.14),
        ],
        max_tables=4,
    )

    assert selected == (invoice_best, payments, workers, customers)
    assert len({doc.metadata["table"] for doc in selected}) == 4


def test_schema_retrieval_respects_table_limit():
    scored = [
        (_document("table_" + str(i), "schema " + str(i)), i / 100)
        for i in range(12)
    ]
    selected = _select_distinct_schema_tables(scored, max_tables=5)
    assert len(selected) == 5
    assert [doc.metadata["table"] for doc in selected] == [
        "table_0", "table_1", "table_2", "table_3", "table_4"
    ]



def test_query_embedding_model_is_not_loaded_during_module_import():
    # The API should bind its port without doing a Hugging Face download or
    # initializing ONNX. The model runtime is loaded only when an AI query
    # actually needs an embedding.
    assert _TOKENIZER is None
    assert _SESSION is None
