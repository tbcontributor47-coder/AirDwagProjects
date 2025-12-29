#!/usr/bin/env bash
set -eu
# Enable pipefail when running under bash; plain /bin/sh may not support it.
if [ -n "${BASH_VERSION-}" ]; then
  set -o pipefail
fi

cat > /app/compare_json.py <<'PY'
#!/usr/bin/env python3

import argparse
import json
import math
import sys
from collections import Counter
from typing import Any, Iterable


USAGE = "Usage: python3 /app/compare_json.py --expected <path> --actual <path> [--tolerance <float>] [--ignore <json-pointer>]..."


def _dump_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _join_ptr(base: str, token: str) -> str:
    if base == "":
        return "/" + _escape_pointer_token(token)
    return base + "/" + _escape_pointer_token(token)


def _normalize_string(s: str) -> str:
    # Remove trailing spaces/tabs on each line.
    parts = s.split("\\n")
    parts = [p.rstrip(" \\t") for p in parts]
    return "\\n".join(parts)


def _is_number(x: Any) -> bool:
    # bool is a subclass of int; exclude it.
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _ignored(ptr: str, ignores: set[str]) -> bool:
    if ptr in ignores:
        return True
    for p in ignores:
        if p != "/" and ptr.startswith(p + "/"):
            return True
    return False


def _is_multiset_array_ptr(ptr: str) -> bool:
    return ptr.endswith("/items") or ptr.endswith("/entries")


def _canonicalize(value: Any, ptr: str, tolerance: float, ignores: set[str]) -> Any:
    if _ignored(ptr, ignores):
        return None

    if isinstance(value, str):
        return _normalize_string(value)

    if _is_number(value):
        # Keep as number; tolerance used in comparisons, not here.
        return float(value) if isinstance(value, float) else int(value)

    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, dict):
        out = {}
        for k in sorted(value.keys(), key=lambda x: str(x)):
            if not isinstance(k, str):
                kk = str(k)
            else:
                kk = k
            child_ptr = _join_ptr(ptr, kk)
            if _ignored(child_ptr, ignores):
                continue
            out[kk] = _canonicalize(value[k], child_ptr, tolerance, ignores)
        return out

    if isinstance(value, list):
        if _is_multiset_array_ptr(ptr):
            rendered = []
            for i, v in enumerate(value):
                child_ptr = _join_ptr(ptr, str(i))
                rendered.append(_dump_json(_canonicalize(v, child_ptr, tolerance, ignores)))
            rendered.sort()
            return rendered
        else:
            return [_canonicalize(v, _join_ptr(ptr, str(i)), tolerance, ignores) for i, v in enumerate(value)]

    # Unsupported JSON type (shouldn't happen)
    return value


def _numbers_equal(a: Any, b: Any, tolerance: float) -> bool:
    if not (_is_number(a) and _is_number(b)):
        return False
    return math.fabs(float(a) - float(b)) <= tolerance


def _first_diff(expected: Any, actual: Any, ptr: str, tolerance: float, ignores: set[str]) -> tuple[str, Any, Any] | None:
    if _ignored(ptr, ignores):
        return None

    # Handle None / bool early
    if expected is None or actual is None or isinstance(expected, bool) or isinstance(actual, bool):
        if expected != actual:
            return ptr, expected, actual
        return None

    if isinstance(expected, str) and isinstance(actual, str):
        if _normalize_string(expected) != _normalize_string(actual):
            return ptr, expected, actual
        return None

    if _is_number(expected) and _is_number(actual):
        if not _numbers_equal(expected, actual, tolerance):
            return ptr, expected, actual
        return None

    if isinstance(expected, dict) and isinstance(actual, dict):
        exp_keys = sorted(expected.keys())
        act_keys = sorted(actual.keys())

        # Missing keys (expected has, actual doesn't)
        for k in exp_keys:
            child_ptr = _join_ptr(ptr, k)
            if _ignored(child_ptr, ignores):
                continue
            if k not in actual:
                return child_ptr, expected[k], None
            d = _first_diff(expected[k], actual[k], child_ptr, tolerance, ignores)
            if d is not None:
                return d

        # Extra keys
        for k in act_keys:
            child_ptr = _join_ptr(ptr, k)
            if _ignored(child_ptr, ignores):
                continue
            if k not in expected:
                return child_ptr, None, actual[k]

        return None

    if isinstance(expected, list) and isinstance(actual, list):
        if _is_multiset_array_ptr(ptr):
            # Multiset compare by canonicalized representation.
            exp_repr = [_dump_json(_canonicalize(v, _join_ptr(ptr, str(i)), tolerance, ignores)) for i, v in enumerate(expected)]
            act_repr = [_dump_json(_canonicalize(v, _join_ptr(ptr, str(i)), tolerance, ignores)) for i, v in enumerate(actual)]
            if Counter(exp_repr) != Counter(act_repr):
                return ptr, expected, actual
            return None

        n = min(len(expected), len(actual))
        for i in range(n):
            child_ptr = _join_ptr(ptr, str(i))
            d = _first_diff(expected[i], actual[i], child_ptr, tolerance, ignores)
            if d is not None:
                return d

        if len(expected) != len(actual):
            child_ptr = _join_ptr(ptr, str(n))
            exp_v = expected[n] if n < len(expected) else None
            act_v = actual[n] if n < len(actual) else None
            return child_ptr, exp_v, act_v

        return None

    # Type mismatch or unsupported: treat as different if not equal.
    if expected != actual:
        return ptr, expected, actual

    return None


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--expected", required=True)
    p.add_argument("--actual", required=True)
    p.add_argument("--tolerance", type=float, default=0.0)
    p.add_argument("--ignore", action="append", default=[])

    try:
        args = p.parse_args(argv)
    except SystemExit:
        print(USAGE, file=sys.stderr)
        return 1

    try:
        with open(args.expected, "r", encoding="utf-8") as f:
            expected = json.load(f)
        with open(args.actual, "r", encoding="utf-8") as f:
            actual = json.load(f)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    ignores = set(args.ignore or [])
    diff = _first_diff(expected, actual, "", float(args.tolerance or 0.0), ignores)

    if diff is None:
        sys.stdout.write("EQUAL\\n")
        return 0

    ptr, exp_v, act_v = diff
    if ptr == "":
        ptr = "/"

    sys.stdout.write("NOT_EQUAL\\n")
    sys.stdout.write(f"FIRST_DIFF {ptr}\\n")
    sys.stdout.write(f"EXPECTED {_dump_json(exp_v)}\\n")
    sys.stdout.write(f"ACTUAL {_dump_json(act_v)}\\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
PY

chmod +x /app/compare_json.py
