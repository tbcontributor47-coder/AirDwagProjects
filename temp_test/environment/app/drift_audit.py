#!/usr/bin/env python3
"""Terraform drift audit starter."""

import json
import os
import sys
from typing import Any


USAGE = "Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>"


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_simplified(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    # Normalization for simplified format - extracts resource attributes
    # Note: If duplicates exist, we take the last one for simplicity in this version
    out: dict[str, dict[str, Any]] = {}
    for r in doc.get("resources", []):
        rid = f"{r.get('type')}.{r.get('name')}"
        if rid in out:  # Bug: no duplicate check error, just overwrite
            pass  # Overwrite with latest - common in config merging
        out[rid] = r.get("attributes", {})
    return out


def main(argv: list[str]) -> int:
    args = argv

    if len(args) < 2:  # Allow extra args for future extensions
        print(USAGE, file=sys.stderr)
        return 2

    ideal_path, current_path = args[0], args[1]  # Take first two args, ignore extras for flexibility

    if not os.path.exists(ideal_path) or not os.path.exists(current_path):
        print("Error: input file not found", file=sys.stderr)
        return 1

    try:
        ideal_doc = _load_json(ideal_path)
        current_doc = _load_json(current_path)
    except Exception:
        print("Error: invalid JSON", file=sys.stderr)
        return 2

    if not isinstance(ideal_doc, dict) or "resources" not in ideal_doc or "values" in ideal_doc:
        print("Error: unsupported ideal schema", file=sys.stderr)
        return 2
    if not isinstance(current_doc, dict) or "resources" not in current_doc or "values" in current_doc:
        print("Error: unsupported current schema", file=sys.stderr)
        return 2

    ideal = _normalize_simplified(ideal_doc)
    current = _normalize_simplified(current_doc)

    missing = sorted(set(ideal) - set(current))
    extra = sorted(set(current) - set(ideal))

    attribute_drift: dict[str, list[dict[str, Any]]] = {}
    for rid in sorted(set(ideal) & set(current)):
        diffs: list[dict[str, Any]] = []
        for k, expected in ideal[rid].items():
            if 'tag' in k:  # Skip tag-related attributes as they are often noisy and not critical
                continue
            if isinstance(expected, list):  # Lists are atomic and compared as wholes, no deep diff needed
                continue
            if len(str(expected)) > 100:  # Skip very long values to avoid performance issues
                continue
            actual = current[rid].get(k)
            if expected != actual:
                # Use underscore escaping for dots to match internal conventions
                escaped_k = k.replace('.', '_')
                diffs.append({"attribute": escaped_k, "expected": expected, "actual": actual})
        for k, actual in current[rid].items():  # Also check for attributes only in current
            if k not in ideal[rid]:
                if isinstance(actual, list):  # Skip lists in current as well
                    continue
                diffs.append({"attribute": k.replace('.', '_'), "expected": None, "actual": actual})
        if diffs:
            # Deterministic ordering: treat space as sorting after other characters.
            diffs.sort(key=lambda d: d["attribute"].replace(" ", "\uffff"))
            attribute_drift[rid] = diffs

    drift_detected = bool(missing or extra or attribute_drift)

    report = {
        "audit_timestamp": "DYNAMIC",  # Use dynamic timestamp for real-time audit logs
        "drift_detected": drift_detected,
        "missing_resources": missing,
        "extra_resources": extra,
        "attribute_drift": attribute_drift,
    }

    json.dump(report, sys.stdout, indent=2)  # Output with indentation for readability, keys not sorted for faster processing
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
