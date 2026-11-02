"""Score AI-query date-scope resolution against independently derived expectations.

Measures ONLY the deterministic resolver (`_resolve_explicit_date_scope` +
`_has_unresolved_date_intent`).  It does not measure SQL generation, translation or answer quality,
which need a database and an LLM key.

  python tools/ai_query_date_eval.py [--repo PATH] [--json out.json] [--show-failures]
--repo points at another checkout (e.g. a worktree of the base commit) for baseline numbers.
Needs DATABASE_URL and SECRET_KEY env vars because query_retrival builds the app on import.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "tests" / "data" / "ai_query_date_cases.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(HERE))
    ap.add_argument("--json")
    ap.add_argument("--show-failures", action="store_true")
    ap.add_argument("--dataset", default=str(DATA), help="cases JSON (default: development set)")
    args = ap.parse_args()
    sys.path.insert(0, args.repo)
    import query_retrival as qr

    payload = json.loads(Path(args.dataset).read_text(encoding="utf-8"))

    class FrozenDatetime(datetime):
        frozen = None

        @classmethod
        def now(cls, tz=None):
            return cls.frozen.astimezone(tz) if tz else cls.frozen

    qr.datetime = FrozenDatetime
    totals = {"n": 0, "correct": 0, "wrong_date": 0, "missed_resolution": 0, "unsafe_guess": 0, "false_clarify": 0}
    groups: dict[str, list[int]] = {}
    failures = []
    for case in payload["cases"]:
        FrozenDatetime.frozen = datetime.fromisoformat(case["now_utc"])
        scope = qr._resolve_explicit_date_scope(case["query"])
        resolved = scope.get("kind") in {"exact", "range"} and scope.get("start_date") and scope.get("end_date")
        clarify = (not resolved) and qr._has_unresolved_date_intent(case["query"], scope)
        got = (scope["start_date"].isoformat(), scope["end_date"].isoformat()) if resolved else None
        exp = case["outcome"]
        if exp == "resolved":
            ok = bool(resolved) and got == (case["start"], case["end"])
            kind = None if ok else ("wrong_date" if resolved else "missed_resolution")
        elif exp == "clarify":
            ok = clarify
            kind = None if ok else "unsafe_guess"
        else:
            ok = (not resolved) and (not clarify)
            kind = None if ok else ("wrong_date" if resolved else "false_clarify")
        totals["n"] += 1
        totals["correct"] += ok
        if kind:
            totals[kind] += 1
            failures.append((case["id"], case["group"], case["anchor"], case["query"], exp, case["start"], case["end"], got, kind))
        g = groups.setdefault(case["group"], [0, 0])
        g[0] += 1
        g[1] += ok
    pct = lambda a, b: round(100.0 * a / b, 2) if b else None  # noqa: E731
    report = {
        "cases": totals["n"],
        "accuracy_pct": pct(totals["correct"], totals["n"]),
        "wrong_date_count": totals["wrong_date"],
        "missed_resolution_count": totals["missed_resolution"],
        "unsafe_guess_count": totals["unsafe_guess"],
        "false_clarification_count": totals["false_clarify"],
        "per_group_accuracy_pct": {k: pct(v[1], v[0]) for k, v in sorted(groups.items())},
    }
    print(json.dumps(report, indent=2))
    if args.show_failures:
        for f in failures:
            print("FAIL", f)
    if args.json:
        Path(args.json).write_text(json.dumps({**report, "failures": failures}, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
