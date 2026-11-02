"""Reject phantom speech-to-text results before they can become bill lines.

Why this exists
---------------
Whisper-family models never return "nothing". Given silence, room noise or a
cough they still emit fluent text: bogus sentences in the hinted language,
YouTube-style sign-offs ("Thank you for watching"), repetition loops, or an echo
of the vocabulary prompt we send. Downstream, a translation LLM can then turn
gibberish into a perfectly plausible sentence ("This is a toothbrush."), and
the extractor happily makes bill lines from it.

The ASR response (``response_format=verbose_json``) already carries per-segment
confidence signals - ``no_speech_prob``, ``avg_logprob`` and ``compression_ratio`` -
that Whisper's own reference decoder uses to skip such segments.  This module
applies them (stricter than the reference, because a wrong bill line costs more
than asking the cashier to speak again) plus a few text-level checks.

Pure functions, no I/O, so every rule is unit-testable.  The thresholds are
engineering defaults that MUST be calibrated on real recordings from the target
shops; see docs/VOICE_AI_EVALUATION.md.  They are not measured accuracy figures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

# Phrases Whisper emits on silence (training-data artefacts).  Compared against the
# WHOLE normalised transcript, so "thank you" inside a real order is unaffected.
_HALLUCINATED_WHOLE = frozenset(
    {
        "thank you", "thanks", "thank you very much", "thanks for watching",
        "thank you for watching", "thank you for watching this video",
        "please subscribe", "subscribe", "like and subscribe", "bye", "bye bye",
        "you", "okay", "ok", "so", "uh", "um", "hmm", "mm", "mhm",
        "ధన్యవాదాలు", "చూసినందుకు ధన్యవాదాలు", "धन्यवाद", "देखने के लिए धन्यवाद",
        "शुक्रिया", "நன்றி", "பார்த்ததற்கு நன்றி", "ಧನ್ಯವಾದಗಳು", "നന്ദി",
    }
)
# Watermark-style fragments: a billing utterance never contains these.
_HALLUCINATED_FRAGMENTS = (
    "amara.org", "subtitles by", "subtitled by", "transcribed by", "www.", "http",
    "subscribe to", "like and subscribe", "thanks for watching", "thank you for watching",
)
_STRIP = " \t\r\n.,!?;:।॥…\"'“”‘’()[]{}-–—"


@dataclass(frozen=True)
class GuardThresholds:
    """Segment rules.  Whisper's reference: skip when no_speech>0.6 AND avg_logprob<-1.0."""

    no_speech_hard: float = 0.85       # a segment this likely to be non-speech is dropped outright
    no_speech_soft: float = 0.50       # ...or this likely AND ...
    logprob_with_no_speech: float = -0.80  # ...the decoder was not confident
    logprob_hard: float = -1.40        # decoder confidence this low is garbage whatever no_speech says
    compression_max: float = 2.40      # Whisper reference: repetitive output loop
    min_speech_seconds: float = 0.30   # total voiced time that survives filtering
    min_audio_seconds: float = 0.40    # shorter recordings are taps, not sentences
    echo_token_ratio: float = 0.70     # share of tokens copied from our own prompt prefix
    echo_catalog_names: int = 8        # consecutive catalog names repeated in prompt order


@dataclass(frozen=True)
class SpeechVerdict:
    accepted: bool
    reason: str
    text: str = ""
    kept_segments: int = 0
    dropped_segments: int = 0
    speech_seconds: float = 0.0
    max_no_speech_prob: Optional[float] = None
    mean_avg_logprob: Optional[float] = None
    scored: bool = False  # False when the provider returned no segment confidences
    drop_reasons: tuple[str, ...] = field(default_factory=tuple)

    def public(self) -> dict[str, Any]:
        """Diagnostics safe to return to the client (no transcript text)."""
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "kept_segments": self.kept_segments,
            "dropped_segments": self.dropped_segments,
            "speech_seconds": round(self.speech_seconds, 2),
            "max_no_speech_prob": self.max_no_speech_prob,
            "mean_avg_logprob": self.mean_avg_logprob,
            "scored": self.scored,
        }


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _tokens(text: str) -> list[str]:
    # str.split + strip, not \w+: Indic vowel signs are combining marks that \w would cut on.
    return [t for t in (raw.strip(_STRIP).casefold() for raw in str(text or "").split()) if t]


def _normalised(text: str) -> str:
    return " ".join(_tokens(text))


def is_known_hallucination(text: str) -> bool:
    norm = _normalised(text)
    if not norm:
        return True
    if norm in _HALLUCINATED_WHOLE:
        return True
    return any(fragment in norm for fragment in _HALLUCINATED_FRAGMENTS)


def has_repetition_loop(text: str, *, min_repeats: int = 4) -> bool:
    """True for 'thank you thank you thank you thank you' or one word repeated 4+ times."""
    tokens = _tokens(text)
    if len(tokens) < min_repeats:
        return False
    run = 1
    for prev, cur in zip(tokens, tokens[1:]):
        run = run + 1 if cur == prev else 1
        if run >= min_repeats:
            return True
    for size in (2, 3):
        if len(tokens) >= size * min_repeats:
            for start in range(0, len(tokens) - size * min_repeats + 1):
                gram = tokens[start:start + size]
                if all(tokens[start + i * size:start + (i + 1) * size] == gram for i in range(min_repeats)):
                    return True
    return False


def is_prompt_echo(
    text: str,
    prompt_prefix: str,
    catalog_names: Iterable[str] = (),
    thresholds: GuardThresholds = GuardThresholds(),
) -> bool:
    """True when the transcript is (mostly) our own ASR prompt read back to us."""
    tokens = _tokens(text)
    if not tokens:
        return False
    prefix_tokens = set(_tokens(prompt_prefix))
    if prefix_tokens and len(tokens) >= 2:
        copied = sum(1 for t in tokens if t in prefix_tokens)
        if copied / len(tokens) >= thresholds.echo_token_ratio:
            return True
    names = [_normalised(n) for n in catalog_names]
    names = [n for n in names if n]
    need = thresholds.echo_catalog_names
    if len(names) >= need and not any(ch.isdigit() for ch in str(text)):
        norm = _normalised(text)
        for start in range(0, len(names) - need + 1):
            if " ".join(names[start:start + need]) in norm:
                return True
    return False


def _segment_drop_reason(segment: dict[str, Any], t: GuardThresholds) -> Optional[str]:
    text = str(segment.get("text") or "").strip()
    if not _tokens(text):
        return "empty_segment"
    no_speech = _num(segment.get("no_speech_prob"))
    logprob = _num(segment.get("avg_logprob"))
    compression = _num(segment.get("compression_ratio"))
    if no_speech is not None and no_speech >= t.no_speech_hard:
        return "no_speech"
    if no_speech is not None and logprob is not None and no_speech >= t.no_speech_soft and logprob <= t.logprob_with_no_speech:
        return "no_speech"
    if logprob is not None and logprob <= t.logprob_hard:
        return "low_confidence"
    if compression is not None and compression >= t.compression_max:
        return "repetition"
    if is_known_hallucination(text):
        return "known_hallucination"
    return None


def assess_transcription(
    payload: dict[str, Any],
    *,
    prompt_prefix: str = "",
    catalog_names: Iterable[str] = (),
    thresholds: GuardThresholds = GuardThresholds(),
) -> SpeechVerdict:
    """Decide whether a Whisper ``verbose_json`` payload contains real speech.

    The returned ``text`` is rebuilt from the segments that survived, so a single
    confident phrase is not poisoned by a hallucinated tail (and vice versa).
    """
    if not isinstance(payload, dict):
        return SpeechVerdict(False, "invalid_payload")
    t = thresholds
    segments = [s for s in (payload.get("segments") or []) if isinstance(s, dict)]
    full_text = str(payload.get("text") or "").strip()
    duration = _num(payload.get("duration"))

    if duration is not None and duration < t.min_audio_seconds:
        return SpeechVerdict(False, "too_short")

    if not segments:
        # Provider gave no confidences: apply the text-only rules and say so.
        if not _tokens(full_text):
            return SpeechVerdict(False, "empty")
        if is_known_hallucination(full_text):
            return SpeechVerdict(False, "known_hallucination")
        if has_repetition_loop(full_text):
            return SpeechVerdict(False, "repetition")
        if is_prompt_echo(full_text, prompt_prefix, catalog_names, t):
            return SpeechVerdict(False, "prompt_echo")
        return SpeechVerdict(True, "ok_unscored", text=full_text, scored=False)

    kept: list[dict[str, Any]] = []
    drops: list[str] = []
    for segment in segments:
        reason = _segment_drop_reason(segment, t)
        if reason is None:
            kept.append(segment)
        else:
            drops.append(reason)

    no_speech_values = [v for v in (_num(s.get("no_speech_prob")) for s in segments) if v is not None]
    logprob_values = [v for v in (_num(s.get("avg_logprob")) for s in kept) if v is not None]
    max_nsp = round(max(no_speech_values), 3) if no_speech_values else None
    mean_lp = round(sum(logprob_values) / len(logprob_values), 3) if logprob_values else None

    def verdict(accepted: bool, reason: str, text: str = "", speech: float = 0.0) -> SpeechVerdict:
        return SpeechVerdict(
            accepted, reason, text=text, kept_segments=len(kept), dropped_segments=len(drops),
            speech_seconds=speech, max_no_speech_prob=max_nsp, mean_avg_logprob=mean_lp,
            scored=True, drop_reasons=tuple(drops),
        )

    if not kept:
        # Report the most informative reason (silence beats generic low confidence).
        for preferred in ("no_speech", "known_hallucination", "repetition", "low_confidence"):
            if preferred in drops:
                return verdict(False, preferred)
        return verdict(False, "empty")

    speech_seconds = 0.0
    for segment in kept:
        start, end = _num(segment.get("start")), _num(segment.get("end"))
        if start is not None and end is not None and end > start:
            speech_seconds += end - start
    text = " ".join(str(s.get("text") or "").strip() for s in kept).strip()
    has_timing = any(_num(s.get("end")) is not None for s in kept)
    if has_timing and speech_seconds < t.min_speech_seconds:
        return verdict(False, "too_short", speech=speech_seconds)
    if has_repetition_loop(text):
        return verdict(False, "repetition", speech=speech_seconds)
    if is_prompt_echo(text, prompt_prefix, catalog_names, t):
        return verdict(False, "prompt_echo", speech=speech_seconds)
    return verdict(True, "ok", text=text, speech=speech_seconds)


# Single user-facing message so the app can show one clear instruction.
NO_SPEECH_MESSAGE = (
    "No clear speech was detected, so nothing was added. "
    "Tap the microphone, speak the items and quantities, then tap again."
)
