# Voice billing and AI Query reliability review

## Speech-to-text guard

The customer/owner voice-billing audio endpoint currently transcribes with
Sarvam Saaras v4. The adapter returns transcript text and the provider's
detected language, but does not expose per-segment
`no_speech_prob`, `avg_logprob`, or `compression_ratio` values. Therefore
the voice-billing audio endpoint currently runs the text-level ASR guard in
unscored mode; it rejects empty/known hallucinated phrases, repetition loops,
and suspicious vocabulary or prompt echoes when those signals are present.
The segment-level thresholds in `voice_asr_guard.py` are available when an
ASR provider supplies those segment fields, but must not be described as
measured confidence for Saaras transcripts.

This is a conservative heuristic, not an accuracy guarantee. Its defaults
must be calibrated against labelled recordings from actual shops. No real-audio
false-accept, false-reject, or word-error-rate results are claimed. The mobile
app's voice-activity gate is not included in this backend change.

The Saaras keyterm list is capped at 50 entries by the adapter. Cashier-confirmed
shop pronunciation aliases are therefore prioritized ahead of the alphabetical
catalog fallback so approved pronunciations are not silently omitted from larger
shop catalogs.

## Voice billing post-processing

The deterministic layer checks whether proposed custom product names and
quantities are supported by the transcript, resolves each line independently
against the authenticated shop catalog, reports ambiguous catalog matches,
converts compatible mass/volume/count units, and refuses to link incompatible
package units to stock. Packet/box/bottle conversions require explicit pack-size
configuration; no package size is guessed.

The included tests are regression aids. They do not measure Whisper accuracy,
Groq LLM quality, or real checkout correctness. Validate with manually reviewed
shop-floor recordings before production release.

## AI Query date resolution

The added date resolver coverage exercises explicit dates, named months,
relative periods, and requests that should trigger clarification instead of
silently running without a date filter. The tests validate deterministic date
resolution only; they do not prove SQL generation, tenant isolation,
translation, or answer quality.

## Deliberately excluded

A process-local response cache is not used as idempotency protection: it
cannot coordinate concurrent requests, multiple Uvicorn workers, or multiple
Render instances. Reliable cross-instance replay protection needs a shared
Redis/database-backed idempotency record and client-generated request IDs.
The parse endpoint only creates a draft, not an invoice or stock movement,
so idempotency should be designed around the actual invoice/stock commit path
if retry protection is required.


## Multi-item translation and price validation

The translation and structured-extraction output budgets scale with transcript
length, while remaining capped. This avoids using a short single-item output
budget for a long spoken bill. The complete translated search text is retained
for catalog candidate retrieval rather than being clipped to a short UI-summary
length.

Leading INR symbols are preserved through normalization so a phrase such as
`₹50 rice` retains its currency cue for price grounding. A model-declared
ambiguous price falls back to the current catalog price only as a draft value
and now raises an explicit confirmation requirement. When a spoken line total
cannot be represented exactly as a two-decimal per-unit price, the server marks
the line for confirmation instead of silently changing the spoken total.

These are deterministic contract improvements. They do not measure live ASR
word error rate or prove end-to-end cashier accuracy; those require reviewed
recordings and checkout outcome labels.