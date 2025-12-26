# Terraform Drift Audit (State Snapshots)

You are given a small CLI program inside the container at:

- `/app/drift_audit.py`

The program is **buggy**. Fix it.

The tool compares an **ideal** Terraform state snapshot against a **current** snapshot and emits a deterministic drift report.

## CLI

The CLI must be invoked as:

```
python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

- `<ideal_state.json>` and `<current_state.json>` are required.
- `--ignore PREFIX` may be repeated. Any attribute drift whose `attribute` path starts with `PREFIX` is excluded.

### Usage errors

If the CLI is invoked incorrectly, exit `2` and print **exactly** this usage line to stderr:

```
Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

No Python traceback may be printed.

## Input

Both inputs are UTF-8 JSON files.

### Supported snapshot formats

A snapshot may be in either of the following formats:

1) **Simplified format**

```
{
  "resources": [
    {
      "type": "aws_instance",
      "name": "web",
      "attributes": { ... }
    }
  ]
}
```

2) **Terraform-like format** (subset)

```
{
  "values": {
    "root_module": {
      "resources": [
        {
          "type": "aws_instance",
          "name": "web",
          "values": { ... }
        }
      ],
      "child_modules": [ ... same shape recursively ... ]
    }
  }
}
```

### Resource identifier normalization

Every resource must be identified as:

```
<resource_type>.<resource_name>
```

Example: `aws_instance.web`.

If a snapshot contains duplicate identifiers, treat it as a **parse error**.

### Attribute comparison

All attributes present in either snapshot must be compared.

- Compare nested objects recursively.
- Attribute paths in the report must be **dot-delimited** (example: `tags.Environment`).
- **Escaping:** if any attribute key contains `.` or `\`, it must be escaped in the output path using a backslash:
  - `\` becomes `\\`
  - `.` becomes `\.`
  - Example: key `Environment.Name` under `tags` becomes `tags.Environment\.Name`.
- Lists are treated as **atomic** values (no per-index flattening). If two lists differ, the attribute path is the list's key.

`--ignore PREFIX` matching is applied to these rendered (escaped) attribute paths.

## Output

On success, print the audit report as JSON to stdout, followed by a newline.

The output must be fully deterministic:

- `audit_timestamp` must be the literal string `STATIC`.
- `missing_resources` and `extra_resources` must be sorted.
- `attribute_drift` keys must be sorted.
- Each resource's drift entries must be sorted by `attribute`.

### Output schema

The output must follow this schema:

- `audit_timestamp`: string (must be `STATIC`)
- `drift_detected`: boolean
- `missing_resources`: array of strings
- `extra_resources`: array of strings
- `attribute_drift`: object mapping resource id -> list of entries
  - each entry is an object with keys:
    - `attribute` (string)
    - `expected` (any JSON value or null)
    - `actual` (any JSON value or null)

## Drift definition

- **Missing resources**: present in ideal, absent in current.
- **Extra resources**: present in current, absent in ideal.
- **Attribute drift**: for resources present in both, any attribute where `expected != actual`, including:
  - attribute present only in ideal (actual is null)
  - attribute present only in current (expected is null)

`drift_detected` must be `true` if and only if any of the above is non-empty.

## Exit codes / error handling

- Exit `0` on success.
- Exit `1` for file I/O errors (missing file, unreadable file).
- Exit `2` for usage errors or parse errors.

### What is a parse error?

Treat each of the following as a **parse error** (exit code `2`):

- **Invalid JSON syntax** (e.g., the file contains malformed JSON like `{`).
- Unsupported schema / missing required keys.
- Duplicate normalized resource identifiers.

On any error:

- Print a human-readable message to stderr.
- Do not print a Python traceback.
