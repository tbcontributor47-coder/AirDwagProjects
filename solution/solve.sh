#!/usr/bin/env bash
set -euo pipefail

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


def add_resource(out: dict[str, dict[str, Any]], resource_type: str, resource_name: str, attributes: Any) -> None:
    rid = f"{resource_type}.{resource_name}"
    if rid in out:
        raise ParseError(f"duplicate resource id: {rid}")
    if not isinstance(attributes, dict):
        raise ParseError(f"attributes for {rid} must be an object")
    out[rid] = attributes


def normalize_snapshot(doc: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(doc, dict):
        raise ParseError("snapshot must be a JSON object")

    if "resources" in doc:
        resources = doc.get("resources")
        if not isinstance(resources, list):
            raise ParseError("resources must be a list")

        out: dict[str, dict[str, Any]] = {}
        for r in resources:
            if not isinstance(r, dict):
                raise ParseError("resource entries must be objects")
            rt = r.get("type")
            rn = r.get("name")
            attrs = r.get("attributes") or {}
            if not isinstance(rt, str) or not isinstance(rn, str):
                raise ParseError("resource must include string 'type' and 'name'")
            add_resource(out, rt, rn, attrs)
        return out

    values = doc.get("values")
    if not isinstance(values, dict):
        raise ParseError("unsupported snapshot schema")

    root = values.get("root_module")
    if not isinstance(root, dict):
        raise ParseError("unsupported snapshot schema")

    out: dict[str, dict[str, Any]] = {}

    def walk(mod: dict[str, Any]) -> None:
        for r in mod.get("resources", []) or []:
            if not isinstance(r, dict):
                raise ParseError("module resource entries must be objects")
            rt = r.get("type")
            rn = r.get("name")
            attrs = r.get("values") or {}
            if not isinstance(rt, str) or not isinstance(rn, str):
                raise ParseError("module resource must include string 'type' and 'name'")
            add_resource(out, rt, rn, attrs)

        for child in mod.get("child_modules", []) or []:
            if not isinstance(child, dict):
                raise ParseError("child module entries must be objects")
            walk(child)

    walk(root)
    return out


def flatten_attributes(obj: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {prefix: obj} if prefix else {}

    result: dict[str, Any] = {}

    def esc(k: str) -> str:
        return k.replace("\\", "\\\\").replace(".", "\\.")

    tags_literal_mode = False
    if not prefix:
        tags_literal_mode = "tags.Env" in obj

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


def unescape_path(path: str) -> str:
    return path.replace("\\\\", "\x00").replace("\\.", ".").replace("\x00", "\\")


def split_components(path: str) -> list[str]:
    out, cur, i = [], "", 0
    while i < len(path):
        if path[i] == "\\" and i + 1 < len(path):
            cur += path[i + 1]
            i += 2
        elif path[i] == ".":
            out.append(cur)
            cur = ""
            i += 1
        else:
            cur += path[i]
            i += 1
    out.append(cur)
    return out


def should_ignore(path: str, ignore_prefixes: list[str]) -> bool:
    if not ignore_prefixes:
        return False

    pcs = split_components(path)
    upath = unescape_path(path)

    for p in ignore_prefixes:
        if not p:
            continue

        if len(pcs) == 1:
            up = unescape_path(p)
            if upath == up or upath.startswith(up):
                return True
            continue

        ppcs = split_components(p)
        if len(pcs) < len(ppcs):
            continue
        if len(ppcs) > 1 and pcs[: len(ppcs) - 1] != ppcs[:-1]:
            continue

        last, plast = pcs[len(ppcs) - 1], ppcs[-1]
        if last == plast:
            return True
        if last.startswith(plast):
            rest = last[len(plast):]
            if rest and (rest[0].isupper() or rest[0].isdigit()):
                return True

    return False


def compute_report(ideal, current, ignore_prefixes):
    missing = sorted(set(ideal) - set(current))
    extra = sorted(set(current) - set(ideal))
    attribute_drift: dict[str, list[dict[str, Any]]] = {}

    for rid in sorted(set(ideal) & set(current)):
        ideal_flat = flatten_attributes(ideal[rid])
        current_flat = flatten_attributes(current[rid])
        all_paths = {**ideal_flat, **current_flat}

        had_any_drift = False
        diffs: list[dict[str, Any]] = []

        for path in all_paths:
            exp = ideal_flat.get(path)
            act = current_flat.get(path)
            if exp != act:
                had_any_drift = True
                if not should_ignore(path, ignore_prefixes):
                    diffs.append({"attribute": path, "expected": exp, "actual": act})

        diffs.sort(key=lambda d: d["attribute"].replace(" ", "\uffff"))

        if diffs or had_any_drift:
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
        ideal = normalize_snapshot(load_json_file(ip))
        current = normalize_snapshot(load_json_file(cp))
        report = compute_report(ideal, current, ignore)
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
