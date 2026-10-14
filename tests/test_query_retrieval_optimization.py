from query_retrieval_optimization import build_bounded_schema_context, canonical_schema_query, hybrid_rank_tables


def test_canonical_schema_query_reuses_equivalent_wording():
    assert canonical_schema_query("Show my sales for yesterday by products") == canonical_schema_query("Yesterday: product sales, show!")


def test_hybrid_retrieval_surfaces_exact_schema_terms_missing_from_vector_topk():
    catalog = {
        "users": "TABLE: users\naccount profile fields",
        "invoices": "TABLE: invoices\ninvoice total amount and payment status",
        "attendance": "TABLE: attendance\nattendance_date worker_id check_in_time working_hours",
        "products": "TABLE: products\nproduct_name stock_quantity",
    }
    ranked = hybrid_rank_tables("attendance by worker check in", catalog, ["users", "invoices"], limit=3)
    assert ranked[0] == "attendance"
    assert "users" in ranked
    assert len(ranked) == 3


def test_hybrid_retrieval_falls_back_to_vector_candidates_without_lexical_match():
    assert hybrid_rank_tables("zxqv_unmatched_concept", {"invoices": "invoice total amount"}, ["invoices"], limit=5) == ["invoices"]


def test_bounded_schema_context_keeps_each_section_header_and_tail():
    section = "TABLE: invoices\n" + ("column definitions " * 250) + "\nQUERY GUIDANCE: use invoice_date"
    context = build_bounded_schema_context([section, "TABLE: products\nQUERY GUIDANCE: use stock_quantity"], max_chars=1000)
    assert len(context) <= 1000
    assert "TABLE: invoices" in context
    assert "QUERY GUIDANCE: use invoice_date" in context
    assert "TABLE: products" in context
