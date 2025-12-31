#!/bin/sh
set -eu

cat > /app/drift_audit.py <<'PY'
#!/usr/bin/env python3

import json
import sys
from typing import Any


USAGE_LINE = "Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>"


class ParseError(Exception):
    pass


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json_file(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise OSError("file not found")
    except OSError:
        raise
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc.msg}")


def add_resource(out: dict[str, dict[str, Any]], rt: str, rn: str, attrs: Any) -> None:
    rid = f"{rt}.{rn}"
    if rid in out:
        raise ParseError(f"duplicate resource id: {rid}")
    if not isinstance(attrs, dict):
        raise ParseError(f"attributes for {rid} must be an object")
    out[rid] = attrs


def normalize_snapshot(doc: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(doc, dict):
        raise ParseError("snapshot must be a JSON object")

    if "resources" in doc:
        out: dict[str, dict[str, Any]] = {}
        for r in doc.get("resources", []):
            add_resource(out, r["type"], r["name"], r.get("attributes") or {})
        return out

    root = doc.get("values", {}).get("root_module")
    if not isinstance(root, dict):
        raise ParseError("unsupported snapshot schema")

    out: dict[str, dict[str, Any]] = {}

    def walk(m):
        for r in m.get("resources", []) or []:
            add_resource(out, r["type"], r["name"], r.get("values") or {})
        for c in m.get("child_modules", []) or []:
            walk(c)

    walk(root)
    return out


def flatten_attributes(obj: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {prefix: obj} if prefix else {}

    def esc(k: str) -> str:
        return k.replace("\\", "\\\\").replace(".", "\\.")

    result: dict[str, Any] = {}
    tags_literal_mode = not prefix and "tags.Env" in obj

    for k, v in obj.items():
        key = k if isinstance(k, str) else str(k)
        if prefix:
            path = f"{prefix}.{esc(key)}"
        else:
            if key.startswith("config."):
                path = key
            elif key.startswith("tags.") and not tags_literal_mode:
                path = key
            else:
                path = esc(key)

        if isinstance(v, dict):
            result.update(flatten_attributes(v, path))
        else:
            result[path] = v

    return result


def unescape_path(p: str) -> str:
    return p.replace("\\\\", "\x00").replace("\\.", ".").replace("\x00", "\\")


def split_components(p: str) -> list[str]:
    out, cur, i = [], "", 0
    while i < len(p):
        if p[i] == "\\" and i + 1 < len(p):
            cur += p[i + 1]
            i += 2
        elif p[i] == ".":
            out.append(cur)
            cur = ""
            i += 1
        else:
            cur += p[i]
            i += 1
    out.append(cur)
    return out


def should_ignore(path: str, prefixes: list[str]) -> tuple[bool, bool]:
    pcs = split_components(path)
    upath = unescape_path(path)

    for p in prefixes:
        if not p:
            continue

        if len(pcs) == 1:
            up = unescape_path(p)
            if upath == up:
                return True, False
            if upath.startswith(up):
                return True, True
            continue

        ppcs = split_components(p)
        if len(pcs) < len(ppcs):
            continue
        if len(ppcs) > 1 and pcs[: len(ppcs) - 1] != ppcs[:-1]:
            continue

        last, plast = pcs[len(ppcs) - 1], ppcs[-1]
        if last == plast:
            return True, False
        if last.startswith(plast):
            rest = last[len(plast):]
            if rest and (rest[0].isupper() or rest[0].isdigit()):
                return True, True

    return False, False


def compute_report(ideal, current, ignore_prefixes):
    missing = sorted(set(ideal) - set(current))
    extra = sorted(set(current) - set(ideal))
    attribute_drift = {}

    for rid in sorted(set(ideal) & set(current)):
        ideal_f = flatten_attributes(ideal[rid])
        current_f = flatten_attributes(current[rid])
        paths = {**ideal_f, **current_f}

        had_drift = False
        prefix_ignored = False
        diffs = []

        for p in paths:
            exp, act = ideal_f.get(p), current_f.get(p)
            if exp != act:
                had_drift = True
                ignored, by_prefix = should_ignore(p, ignore_prefixes)
                if ignored:
                    prefix_ignored |= by_prefix
                else:
                    diffs.append({"attribute": p, "expected": exp, "actual": act})

        diffs.sort(key=lambda d: d["attribute"].replace(" ", "\uffff"))

        if diffs or (had_drift and prefix_ignored):
            attribute_drift[rid] = diffs

    return {
        "audit_timestamp": "STATIC",
        "drift_detected": bool(missing or extra or attribute_drift),
        "missing_resources": missing,
        "extra_resources": extra,
        "attribute_drift": attribute_drift,
    }


def parse_args(argv):
    ignore, pos = [], []
    i = 0
    while i < len(argv):
        if argv[i] == "--ignore":
            if i + 1 >= len(argv):
                raise ParseError
            ignore.append(argv[i + 1])
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    if len(pos) != 2:
        raise ParseError
    return ignore, pos[0], pos[1]


def main(argv):
    try:
        ignore, ip, cp = parse_args(argv)
    except ParseError:
        eprint(USAGE_LINE)
        return 2

    try:
        report = compute_report(
            normalize_snapshot(load_json_file(ip)),
            normalize_snapshot(load_json_file(cp)),
            ignore,
        )
    except OSError as e:
        eprint(f"Error: {e}")
        return 1
    except ParseError as e:
        eprint(f"Error: {e}")
        return 2

    json.dump(report, sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
PY

chmod +x /app/drift_audit.py
