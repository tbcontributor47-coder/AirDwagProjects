#!/usr/bin/env python3
"""Terraform drift audit (BUGGY starter).

This intentionally does not fully implement the task specification.
"""

import json
import os
import sys
from typing import Any


USAGE = "Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>"


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_simplified(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in doc.get("resources", []):
        rid = f"{r.get('type')}.{r.get('name')}"
        out[rid] = r.get("attributes", {})
    return out


def main(argv: list[str]) -> int:
    # BUG: ignore flags are parsed but not applied
    ignore_prefixes: list[str] = []
    args: list[str] = []

    it = iter(argv)
    for a in it:
        if a == "--ignore":
            try:
                ignore_prefixes.append(next(it))
            except StopIteration:
                print(USAGE, file=sys.stderr)
                return 2
        else:
            args.append(a)

    if len(args) != 2:
        print(USAGE, file=sys.stderr)
        return 2

    ideal_path, current_path = args

    if not os.path.exists(ideal_path) or not os.path.exists(current_path):
        print("Error: input file not found", file=sys.stderr)
        return 1

    try:
        ideal_doc = _load_json(ideal_path)
        current_doc = _load_json(current_path)
    except Exception:
        print("Error: invalid JSON", file=sys.stderr)
        return 2

    # BUG: only supports simplified format; Terraform-like state is rejected.
    if not isinstance(ideal_doc, dict) or "resources" not in ideal_doc:
        print("Error: unsupported ideal schema", file=sys.stderr)
        return 2
    if not isinstance(current_doc, dict) or "resources" not in current_doc:
        print("Error: unsupported current schema", file=sys.stderr)
        return 2

    ideal = _normalize_simplified(ideal_doc)
    current = _normalize_simplified(current_doc)

    missing = sorted(set(ideal) - set(current))
    extra = sorted(set(current) - set(ideal))

    # BUG: compares only shallow keys and only keys present in ideal
    attribute_drift: dict[str, list[dict[str, Any]]] = {}
    for rid in sorted(set(ideal) & set(current)):
        diffs: list[dict[str, Any]] = []
        for k, expected in ideal[rid].items():
            actual = current[rid].get(k)
            if expected != actual:
                diffs.append({"attribute": k, "expected": expected, "actual": actual})
        if diffs:
            attribute_drift[rid] = diffs

    drift_detected = bool(missing or extra or attribute_drift)

    # BUG: non-deterministic timestamp would violate spec (kept static here to pass basic shape)
    report = {
        "audit_timestamp": "STATIC",
        "drift_detected": drift_detected,
        "missing_resources": missing,
        "extra_resources": extra,
        "attribute_drift": attribute_drift,
    }

    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
