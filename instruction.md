# Terraform Drift Audit (State Snapshots)

You are given a small CLI program inside the container at:

- `/app/drift_audit.py`

The program is **buggy**. Fix it.

The tool compares an **ideal** Terraform state snapshot against a **current** snapshot and prints a deterministic drift report as JSON.

This document is the full runtime contract. Do not guess; implement exactly what is specified.

## Step-by-step implementation checklist (required)

Implement `/app/drift_audit.py` exactly as the following pipeline. This section is intentionally redundant and procedural to remove ambiguity.

### Step 0: constants

- Define `USAGE_LINE` exactly:
  `Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>`
- Define `AUDIT_TIMESTAMP` exactly: `STATIC`

### Step 1: parse CLI args

Input: `sys.argv[1:]`.

Output: `(ignore_prefixes: list[str], ideal_path: str, current_path: str)`.

Algorithm:

1) Initialize `ignore_prefixes = []`.
2) While the next token is `--ignore`:
   - Consume `--ignore`.
   - If no next token exists: usage error.
   - Consume the next token as `prefix` and append it to `ignore_prefixes`.
3) After processing `--ignore`, there must be exactly 2 remaining tokens: `ideal_path` then `current_path`.
   - Otherwise: usage error.
4) If any unknown flag is present anywhere: usage error.

Usage error behavior (must match tests):

- Exit `2`
- stdout empty
- stderr equals `USAGE_LINE + "\n"`

### Step 2: read and JSON-decode both files

For each file path:

1) Read the file as UTF-8 text.
   - If the file cannot be opened/read: I/O error (exit `1`), stdout empty, stderr non-empty.
2) Parse JSON.
   - If JSON parsing fails: parse error (exit `2`), stdout empty, stderr non-empty.

Never print a Python traceback.

### Step 3: normalize each snapshot into a resource map

Goal: convert both snapshots into a dict:

`resources: dict[str, dict]` mapping `resource_id` → `attributes_obj`

Where:

- `resource_id = f"{type}.{name}"`
- `attributes_obj` is a JSON object (dict) containing the resource attributes

Algorithm `parse_snapshot(obj) -> dict[str, dict]`:

1) If `obj` has key `resources`:
   - Validate `obj["resources"]` is a list.
   - For each element `r` in the list:
     - Validate `r` is an object.
     - Validate `r["type"]` and `r["name"]` are strings.
     - Validate `r["attributes"]` is an object.
     - Compute `rid = type + "." + name`.
     - If `rid` already exists in the output: parse error.
     - Set `out[rid] = r["attributes"]`.
   - Return `out`.

2) Else if `obj` has nested keys `values.root_module`:
   - Validate `obj["values"]` is an object and `obj["values"]["root_module"]` is an object.
   - Define recursive walk `walk_module(m)`:
     - If `m` has `resources`:
       - Validate it is a list.
       - For each resource `r`:
         - Validate `r["type"]` and `r["name"]` are strings.
         - Validate `r["values"]` is an object.
         - `rid = type + "." + name`.
         - If `rid` already exists: parse error.
         - `out[rid] = r["values"]`.
     - If `m` has `child_modules`:
       - Validate it is a list.
       - For each child module object `c` in the list: call `walk_module(c)`.
   - Call `walk_module(obj["values"]["root_module"])`.
   - Return `out`.

3) Otherwise: parse error.

### Step 4: compute missing/extra resources

Let `ideal_ids = set(ideal_map.keys())` and `current_ids = set(current_map.keys())`.

- `missing_resources = sorted(ideal_ids - current_ids)`
- `extra_resources = sorted(current_ids - ideal_ids)`

### Step 5: compute attribute drift for shared resources

For each resource id in `sorted(ideal_ids ∩ current_ids)`:

1) Flatten both attribute objects into `path -> value` maps (see Step 6).
2) Let `all_paths = set(ideal_paths) ∪ set(current_paths)`.
3) For each path in `all_paths`:
   - `expected = ideal_map.get(path, None)`
   - `actual = current_map.get(path, None)`
   - If `expected != actual`, create a drift entry:
     `{ "attribute": path, "expected": expected_or_null, "actual": actual_or_null }`
     Where missing side uses JSON `null`.

### Step 6: flatten attribute objects (exact)

Flattening produces a mapping from rendered attribute path string → JSON value.

Rules:

- Only JSON objects (dicts) are flattened recursively.
- Lists are atomic values.
- Scalars are atomic values.

Pseudocode:

```
def escape_literal_key(k: str) -> str:
    # order is required
    return k.replace('\\', '\\\\').replace('.', '\\.')

def flatten(obj: dict, prefix: str) -> dict[str, object]:
    out = {}
    for key, value in obj.items():
        if prefix == "":
            rendered_key = render_top_level_key(key)
        else:
            rendered_key = escape_literal_key(key)

        new_prefix = rendered_key if prefix == "" else prefix + "." + rendered_key

        if isinstance(value, dict):
            out.update(flatten(value, new_prefix))
        else:
            out[new_prefix] = value
    return out
```

Top-level key rendering `render_top_level_key(key)`:

- If `key` starts with `config.`: return `key` unchanged.
- Else if `key` starts with `tags.`: return `key` unchanged.
- Else: return `escape_literal_key(key)`.

Concrete flattening examples (must match verifier expectations):

- Input attributes: `{ "tags": { "Environment.Name": "prod" } }`
  - Drift path: `tags.Environment\\.Name`

- Input attributes: `{ "meta": { "path\\to.file": "B" } }`
  - Drift path: `meta.path\\\\to\\.file`

- Input attributes: `{ "key.with.dots": "x" }`
  - Drift path: `key\\.with\\.dots`

- Input attributes: `{ "tags.Environment": "prod" }` (top-level already-rendered)
  - Drift path: `tags.Environment`

### Step 7: apply ignore filtering

Apply ignores after drift entries are created and paths are rendered.

For each drift entry with `attribute = path`, remove it if ANY ignore prefix matches using the matching rules below.

Also remove any `attribute_drift[resource_id]` list if it becomes empty.

### Step 8: deterministic sorting

After ignore filtering:

- Sort drift entries for each resource by `attribute` using the special ordering where space `' '` sorts after all other characters.
- Sort `attribute_drift` keys (resource ids) lexicographically.
- Ensure `missing_resources` and `extra_resources` are sorted.

Special ordering rule for attributes:

- Compare strings lexicographically, but treat `' '` as a character greater than every other character.

### Step 9: build and print the report

Build:

```
report = {
  "audit_timestamp": "STATIC",
  "drift_detected": <computed>,
  "missing_resources": [...],
  "extra_resources": [...],
  "attribute_drift": { ... }
}
```

Print JSON to stdout followed by a newline.

`drift_detected` must be `true` iff any drift exists.

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

## Quick verifier-aligned examples

These are intended as sanity checks for your implementation.

### Example 1: partial ignore (`tags.Env`)

If drift contains `tags.Environment` and `tags.EnvName`, then:

```
python /app/drift_audit.py --ignore tags.Env <ideal> <current>
```

must ignore `tags.EnvName` but must NOT ignore `tags.Environment`.

### Example 2: escaped dot is literal

If a drift path is `config.network\\.ip` (meaning the dot is literal inside the last component), then:

- `--ignore config.network` must match `config.network.ip`
- `--ignore config.network` must NOT match `config.network\\.ip`

