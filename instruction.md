# Terraform Drift Audit (State Snapshots)

You are given a small CLI program inside the container at:

- `/app/drift_audit.py`

The program is **buggy**. Fix it.

The tool compares an **ideal** Terraform state snapshot against a **current** snapshot and prints a deterministic drift report as JSON.

This document is the full runtime contract. Do not guess; implement exactly what is specified.

## CLI contract

The CLI must be invoked as:

```
python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

- `<ideal_state.json>` and `<current_state.json>` are required positional arguments.
- `--ignore PREFIX` can be repeated.

### Usage errors

If the CLI is invoked incorrectly (wrong number of args, `--ignore` missing its value, unknown flags, etc.):

- Exit code: `2`
- Stdout: **must be empty**
- Stderr: must be **exactly** the single usage line below, followed by `\n`

```
Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

No Python traceback may be printed.

## Errors and exit codes

The program must never print a Python traceback.

On any non-zero exit:

- Stdout must be **empty**.
- Stderr must be **non-empty** and human-readable.

Exit codes:

- `0`: success (report printed to stdout)
- `1`: file I/O errors (missing file, unreadable file)
- `2`: usage errors or parse errors

### Parse errors (exit 2)

Treat any of the following as a parse error:

- Invalid JSON syntax (JSON decode error)
- Unsupported snapshot shape / missing required keys / wrong types (where required keys must be objects/lists)
- Duplicate normalized resource identifiers within a single snapshot

## Input snapshots

Both inputs are UTF-8 JSON files.

Each snapshot is in one of these supported formats.

### Format A: simplified

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

Requirements:

- Top-level `resources` must exist and be a list.
- Each `resources[*]` must be an object containing:
  - `type` (string)
  - `name` (string)
  - `attributes` (object)

### Format B: terraform-like (subset)

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
      "child_modules": [ ... ]
    }
  }
}
```

Requirements:

- `values.root_module` must exist and be an object.
- A module object can contain:
  - `resources`: list of resource objects (same `type`/`name`, but attributes are under `values`)
  - `child_modules`: list of module objects (same shape recursively)

Traversal:

- Walk `values.root_module` and all nested modules in depth-first order.
- Collect all resources from every module.

### Mixed formats

The ideal snapshot may be Format A while the current snapshot is Format B (and vice-versa). Handle this.

## Resource identity

Every resource is identified by:

```
<type>.<name>
```

Example: `aws_instance.web`.

If a single snapshot contains the same identifier more than once, that snapshot is a **parse error** (exit `2`).

## Attribute flattening and rendering

Each resource has an attribute object:

- Format A uses `attributes`
- Format B uses `values`

You must compare all attributes present in either snapshot (union).

### Comparison rules

- Nested JSON objects are compared recursively (flattened into paths).
- Lists are **atomic** values (no per-index flattening). If two lists differ, drift is reported at the list key path.
- Do not coerce types. For example, `123` and `"123"` are different.

### Rendered attribute paths

Flatten nested objects into dot-delimited paths.

#### Escaping a literal key name into one path segment

When a key name is treated as a **literal key name** (a single path component), escape it in this exact order:

1) Escape backslashes: `\` → `\\`
2) Escape dots: `.` → `\.`

No other characters are escaped.

Examples:

- Nested key `Environment.Name` under `tags` renders as `tags.Environment\\.Name`.
- Nested key `path\to.file` under `meta` renders as `meta.path\\\\to\\.file`.

#### Top-level special handling

At the **top level only** (i.e., when the current prefix is empty):

- If the key starts with `config.`: treat the key string as an **already-rendered path**.
- If the key starts with `tags.`: treat the key string as an **already-rendered path**.
- Otherwise: treat the key as a **literal key name** and escape it using the literal escaping rules above.

Meaning of “already-rendered path”:

- The top-level key string is used as the path prefix **as-is**.
- Its unescaped `.` characters are path separators.
- The sequences `\.` and `\\` inside that string are treated as the same escape sequences used elsewhere (i.e., an escaped dot is a literal dot inside a component).

If an already-rendered top-level key maps to a nested object, flatten that nested object under this prefix, and for those nested keys (prefix is now non-empty) treat nested keys as literal key names (escape them).

## Drift report

### Drift types

- **Missing resources**: present in ideal, absent in current.
- **Extra resources**: present in current, absent in ideal.
- **Attribute drift**: for resources present in both, any flattened attribute path where expected and actual differ.
  - If an attribute exists only in ideal: `actual` is `null`.
  - If an attribute exists only in current: `expected` is `null`.

### Ignore filtering (`--ignore`)

Each provided `--ignore PREFIX` removes any attribute drift entry whose rendered `attribute` path matches `PREFIX`.

Ignore matching is **segment-aware** (component-aware), not an arbitrary substring match.

#### Component splitting for matching

Split a rendered path string into components by scanning left-to-right:

- An unescaped `.` starts a new component.
- The only recognized escape sequences are:
  - `\.` (literal dot in current component)
  - `\\` (literal backslash in current component)
- Any other `\X` is treated as a literal backslash followed by `X`.

#### Matching normalization (Unicode)

Ignore matching must be stable for Unicode text. For matching only (not for rendering), transform each component as follows:

1) Normalize with NFC
2) Case-fold (`casefold()`)
3) Normalize with NFKD and remove all combining marks (category `Mn`)

This makes `café` match `cafe`.

#### Matching rule

Let `P = PREFIX components` and `A = attribute components` (after splitting). Compare using the normalized forms, but keep the original (pre-normalized) final component around for the lookahead rule.

Single-component special case (required):

- If the rendered attribute path has exactly one component (i.e., it contains **no unescaped dots**), then ignore matching is a plain string prefix match on that single component:
  1) Unescape both strings by converting `\\` → `\` and then `\.` → `.`.
  2) Apply the matching normalization (NFC → casefold → NFKD + strip `Mn`) to the entire unescaped strings.
  3) Treat `PREFIX` as matching if the normalized attribute string starts with the normalized prefix string.

This is required so `--ignore café` matches both `café` and `café\.au_lait`.

`PREFIX` matches `attribute` if:

- `P` is longer than `A`: no match.
- For all components except the last component of `P`: they must match exactly.
- For the final component of `P`, allow either:
  - exact match, OR
  - a partial match where the attribute final component starts with the prefix final component and the next character in the **original rendered attribute final component** (right after the matched prefix) is an uppercase letter (`A`-`Z`) or a digit (`0`-`9`).

This rule is required so `--ignore tags.Env` ignores `tags.EnvName` but does not ignore `tags.Environment`.

### Output JSON schema

On success, print a single JSON object to stdout followed by a newline:

- `audit_timestamp`: string, must be exactly `STATIC`
- `drift_detected`: boolean
- `missing_resources`: array of resource id strings
- `extra_resources`: array of resource id strings
- `attribute_drift`: object mapping resource id → list of drift entries
  - Each drift entry is an object:
    - `attribute`: rendered attribute path (string)
    - `expected`: JSON value or `null`
    - `actual`: JSON value or `null`

`drift_detected` must be `true` iff any of:

- `missing_resources` is non-empty
- `extra_resources` is non-empty
- any `attribute_drift[resource]` list is non-empty

### Deterministic ordering

The output must be fully deterministic:

- `audit_timestamp` is always `STATIC`.
- `missing_resources` and `extra_resources` must be sorted lexicographically.
- The keys of `attribute_drift` must be sorted lexicographically.
- For each resource, its list of drift entries must be sorted by `attribute` using this ordering:
  - primary: lexicographic on the rendered attribute string
  - special-case: treat a space character `' '` as sorting *after* all other characters

Resources with zero drift entries after ignore filtering must not appear in `attribute_drift`.
