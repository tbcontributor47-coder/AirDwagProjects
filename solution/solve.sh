#!/usr/bin/env bash
set -euo pipefail

cat > /app/drift_audit.py <<'PY'
#!/usr/bin/env python3

import json
import os
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
            resource_type = r.get("type")
            resource_name = r.get("name")
            attributes = r.get("attributes")
            if not isinstance(resource_type, str) or not isinstance(resource_name, str):
                raise ParseError("resource must include string 'type' and 'name'")
            if attributes is None:
                attributes = {}
            add_resource(out, resource_type, resource_name, attributes)
        return out

    # Terraform-like subset: values.root_module.(resources, child_modules)
    values = doc.get("values")
    if not isinstance(values, dict):
        raise ParseError("unsupported snapshot schema")

    root = values.get("root_module")
    if not isinstance(root, dict):
        raise ParseError("unsupported snapshot schema")

    out: dict[str, dict[str, Any]] = {}

    def walk_module(mod: dict[str, Any]) -> None:
        res_list = mod.get("resources", [])
        if res_list is None:
            res_list = []
        if not isinstance(res_list, list):
            raise ParseError("module resources must be a list")

        for r in res_list:
            if not isinstance(r, dict):
                raise ParseError("module resource entries must be objects")
            resource_type = r.get("type")
            resource_name = r.get("name")
            attrs = r.get("values")
            if not isinstance(resource_type, str) or not isinstance(resource_name, str):
                raise ParseError("module resource must include string 'type' and 'name'")
            if attrs is None:
                attrs = {}
            add_resource(out, resource_type, resource_name, attrs)

        children = mod.get("child_modules", [])
        if children is None:
            children = []
        if not isinstance(children, list):
            raise ParseError("child_modules must be a list")
        for child in children:
            if not isinstance(child, dict):
                raise ParseError("child module entries must be objects")
            walk_module(child)

    walk_module(root)
    return out


def flatten_attributes(obj: Any, prefix: str = "") -> dict[str, Any]:
    def escape_key(key: str) -> str:
        # For keys in nested objects, escape dots and backslashes
        # Dots become \. and backslashes become \\
        return key.replace("\\", "\\\\").replace(".", "\\.")

    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                key = str(k)
            else:
                key = k
            
            if prefix:
                # We're in a nested context - escape the key
                key_escaped = escape_key(key)
                path = f"{prefix}.{key_escaped}"
            else:
                # Top-level key - treat dots as path separators, don't escape
                # The key itself might have escaped dots (\.) which represent literal dots
                path = key
            
            if isinstance(v, dict):
                out.update(flatten_attributes(v, path))
            else:
                # Lists are treated as atomic values
                out[path] = v
    else:
        if prefix:
            out[prefix] = obj
    return out


def unescape_path(path: str) -> str:
    """Unescape backslash-escaped dots and backslashes in a path."""
    # Replace \. with . and \\ with \
    # Process \\ first to avoid double-unescaping
    return path.replace("\\\\", "\x00").replace("\\.", ".").replace("\x00", "\\")


def should_ignore(path: str, ignore_prefixes: list[str]) -> bool:
    # Match against both escaped and unescaped paths
    # Escaped path matching: for cases where user provides escaped prefixes
    # Unescaped path matching: for logical component-based matching
    for prefix in ignore_prefixes:
        # Try exact match or prefix followed by dot on escaped path
        if path == prefix or path.startswith(prefix + "."):
            return True
        
        # Unescape both for logical matching
        unescaped_path = unescape_path(path)
        unescaped_prefix = unescape_path(prefix)
        
        # Check if prefix is an exact match or a component prefix
        if unescaped_path == unescaped_prefix:
            return True
        if unescaped_path.startswith(unescaped_prefix + "."):
            return True
    return False


def compute_report(ideal: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]], ignore_prefixes: list[str]) -> dict[str, Any]:
    ideal_ids = set(ideal)
    current_ids = set(current)

    missing_resources = sorted(ideal_ids - current_ids)
    extra_resources = sorted(current_ids - ideal_ids)

    attribute_drift: dict[str, list[dict[str, Any]]] = {}

    for rid in sorted(ideal_ids & current_ids):
        ideal_flat = flatten_attributes(ideal[rid])
        current_flat = flatten_attributes(current[rid])

        # Preserve order: iterate through ideal first, then current-only paths
        # Use dict to preserve insertion order (Python 3.7+)
        all_paths_dict = {**ideal_flat, **current_flat}
        diffs: list[dict[str, Any]] = []
        has_any_diff = False

        for path in all_paths_dict:
            expected = ideal_flat.get(path)
            actual = current_flat.get(path)
            if expected != actual:
                has_any_diff = True
                if not should_ignore(path, ignore_prefixes):
                    diffs.append({"attribute": path, "expected": expected, "actual": actual})

        # Include resource in attribute_drift if there were any diffs (even if all ignored)
        if has_any_diff:
            attribute_drift[rid] = diffs

    drift_detected = bool(missing_resources or extra_resources or attribute_drift)

    return {
        "audit_timestamp": "STATIC",
        "drift_detected": drift_detected,
        "missing_resources": missing_resources,
        "extra_resources": extra_resources,
        "attribute_drift": attribute_drift,
    }


def parse_args(argv: list[str]) -> tuple[list[str], str, str]:
    ignore_prefixes: list[str] = []
    positional: list[str] = []

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--ignore":
            if i + 1 >= len(argv):
                raise ParseError("missing value for --ignore")
            ignore_prefixes.append(argv[i + 1])
            i += 2
            continue
        positional.append(a)
        i += 1

    if len(positional) != 2:
        raise ParseError("usage")

    return ignore_prefixes, positional[0], positional[1]


def main(argv: list[str]) -> int:
    try:
        ignore_prefixes, ideal_path, current_path = parse_args(argv)
    except ParseError:
        eprint(USAGE_LINE)
        return 2

    try:
        ideal_doc = load_json_file(ideal_path)
        current_doc = load_json_file(current_path)
    except OSError as exc:
        eprint(f"Error: {exc}")
        return 1
    except ParseError as exc:
        eprint(f"Error: {exc}")
        return 2

    try:
        ideal = normalize_snapshot(ideal_doc)
        current = normalize_snapshot(current_doc)
        report = compute_report(ideal, current, ignore_prefixes)
    except ParseError as exc:
        eprint(f"Error: {exc}")
        return 2

    json.dump(report, sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
PY

chmod +x /app/drift_audit.py
