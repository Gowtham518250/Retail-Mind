#!/usr/bin/env python3
"""Verify resolve_shop_id fix — writes evidence to debug-6d3a75.log"""
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from security import resolve_shop_id

LOG_PATH = r"d:\AI_Shop_Latest_Source_June2\lib\debug-6d3a75.log"


def log(hypothesis_id, location, message, data, run_id="post-fix-verify"):
    entry = {
        "sessionId": "6d3a75",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry))


def main():
    # H6: Demonstrate the bug that broke POST /api/invoices/create
    bad_shop_id = {"user_id": 42, "role": "OWNER"}
    log(
        "H6",
        "verify_shop_id:bug_demo",
        "BEFORE FIX shop_id was dict",
        {
            "buggy_shop_id_type": type(bad_shop_id).__name__,
            "buggy_shop_id_value": str(bad_shop_id),
            "would_break_db_insert": True,
        },
    )

    fixed = resolve_shop_id(bad_shop_id)
    log(
        "H6",
        "verify_shop_id:fixed",
        "AFTER FIX shop_id is int",
        {
            "fixed_shop_id": fixed,
            "fixed_type": type(fixed).__name__,
            "fix_valid": fixed == 42,
        },
    )

    assert resolve_shop_id({"user_id": 99, "role": "WORKER"}) == 99
    assert resolve_shop_id(7) == 7
    log(
        "H6",
        "verify_shop_id:assertions",
        "resolve_shop_id assertions passed",
        {"status": "PASS"},
    )


if __name__ == "__main__":
    main()
