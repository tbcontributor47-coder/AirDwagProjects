#!/usr/bin/env python3

import argparse
import json
import sys
from typing import Any


def _dump_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--expected", required=True)
    p.add_argument("--actual", required=True)
    p.add_argument("--tolerance", type=float, default=0.0)
    p.add_argument("--ignore", action="append", default=[])
    return p.parse_args(argv)


def _top_level_ignore(pointer: str, ignores: list[str]) -> bool:
    # BUG: only ignores top-level pointers like "/foo" (no nested ignores).
    if pointer.count("/") > 1:
        return False
    return pointer in ignores


def _first_diff(expected: Any, actual: Any, pointer: str, ignores: list[str]) -> tuple[str, Any, Any] | None:
    if _top_level_ignore(pointer, ignores):
        return None

    if type(expected) is not type(actual):
        return pointer, expected, actual

    if isinstance(expected, dict):
        exp_keys = sorted(expected.keys())
        act_keys = sorted(actual.keys())

        for k in exp_keys:
            child_ptr = pointer + "/" + str(k)
            if k not in actual:
                return child_ptr, expected[k], None
            d = _first_diff(expected[k], actual[k], child_ptr, ignores)
            if d is not None:
                return d

        for k in act_keys:
            if k not in expected:
                child_ptr = pointer + "/" + str(k)
                return child_ptr, None, actual[k]

        return None

    if isinstance(expected, list):
        # BUG: all arrays order-sensitive; no special `/items` or `/entries` handling.
        n = min(len(expected), len(actual))
        for i in range(n):
            child_ptr = pointer + "/" + str(i)
            d = _first_diff(expected[i], actual[i], child_ptr, ignores)
            if d is not None:
                return d
        if len(expected) != len(actual):
            child_ptr = pointer + "/" + str(n)
            exp_v = expected[n] if n < len(expected) else None
            act_v = actual[n] if n < len(actual) else None
            return child_ptr, exp_v, act_v
        return None

    # BUG: no trailing-whitespace normalization and no numeric tolerance.
    if expected != actual:
        return pointer, expected, actual

    return None


def main(argv: list[str]) -> int:
    try:
        args = _parse_args(argv)
    except SystemExit:
        print("Usage: python3 /app/compare_json.py --expected <path> --actual <path> [--tolerance <float>] [--ignore <json-pointer>]...", file=sys.stderr)
        return 1

    try:
        with open(args.expected, "r", encoding="utf-8") as f:
            expected = json.load(f)
        with open(args.actual, "r", encoding="utf-8") as f:
            actual = json.load(f)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    diff = _first_diff(expected, actual, "", args.ignore)
    if diff is None:
        sys.stdout.write("EQUAL\n")
        return 0

    ptr, exp_v, act_v = diff
    if ptr == "":
        ptr = "/"

    sys.stdout.write("NOT_EQUAL\n")
    sys.stdout.write(f"FIRST_DIFF {ptr}\n")
    sys.stdout.write(f"EXPECTED {_dump_json(exp_v)}\n")
    sys.stdout.write(f"ACTUAL {_dump_json(act_v)}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
