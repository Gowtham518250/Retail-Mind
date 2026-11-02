# Voice billing and AI Query reliability review

## Speech-to-text guard

The backend requests Groq Whisper `verbose_json` and evaluates segment-level
`no_speech_prob`, `avg_logprob`, and `compression_ratio` before using a
transcript. It also rejects known silence phrases, repetition loops, and
transcription that appears to echo the supplied prompt or shop vocabulary.

This is a conservative heuristic, not an accuracy guarantee. Its defaults
must be calibrated against labelled recordings from actual shops. No real-audio
false-accept, false-reject, or word-error-rate results are claimed. The mobile
app's voice-activity gate is not included in this backend change.

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
