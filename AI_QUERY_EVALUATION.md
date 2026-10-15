# AI query answer evaluation

This evaluator measures the answer-verification contract for a labelled Retail Mind question set. It runs offline against JSON Lines files and does not call the production API.

## Build a labelled set

Create one case object per question in a private JSONL file. Assign a stable case_id. expected_answer should be the exact result a shop owner verified against the shop's source records, or null when the correct behavior is to ask for clarification. Use anonymized source record identifiers; do not commit customer names, phone numbers, invoices, tokens, database exports, or other private shop data to the repository.

Example case fields:

    {"case_id":"sales-today","question":"What were sales today?","expected_answer":"1200.00","requires_clarification":false,"expected_date_range":{"start":"2026-10-15","end":"2026-10-15"},"expected_source_record_ids":["INV-101"],"must_be_shop_scoped":true}

The question set must be reviewed and labelled by a person with access to the shop's actual records before its accuracy score is treated as a real-shop result. The repository does not include a real shop dataset.

## Capture result metadata

Export one result object per case_id with fields answer, needs_clarification, shop_scope_valid, date_range, and source_record_ids. shop_scope_valid must come from an independently verified server/query audit, not from the model's own claim. date_range should be an object with start and end keys. source_record_ids should be the identifiers of records actually used to form the answer.

## Run the evaluator

    python tools/ai_query_eval.py --cases private_cases.jsonl --results captured_results.jsonl --min-critical-pass-rate 0.85

The report includes answer accuracy, clarification accuracy, shop-scope accuracy, date-range accuracy, source precision/recall, and critical-pass rate. A missing result is scored as a failure. Exit code 1 is returned when a requested minimum critical-pass rate is missed. Do not claim the target is reached until the labelled set is real-shop validated, the captured metadata is independently checked, and the run meets the target.
