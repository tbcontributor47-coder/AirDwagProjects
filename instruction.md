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

Note about empty objects:

- An empty JSON object `{}` produces no leaf paths when flattened. In other words, an attribute whose value is an empty object is equivalent (for the purposes of attribute-path comparison) to the attribute being absent, unless the other side contains nested leaf keys under that attribute. This avoids reporting spurious drift for structural container-only keys.

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

Matching semantics (clarified):

- `PREFIX` is written in the rendered attribute-path syntax (escaped dots and backslashes) and is matched against the start of the rendered attribute path.
- Matching is component-aware: a `PREFIX` like `tags.Env` will match `tags.EnvName` only when the `PREFIX` components align with the rendered path components in a sensible way. Implementations should treat the rendered path as a dot-delimited sequence of components (respecting escapes) and perform a prefix match on those components. This prevents arbitrary substring matches that could accidentally ignore unrelated keys.

**Important (verifier-aligned):** The `PREFIX` values are written in the same *rendered attribute path* syntax that appears in the output (i.e., the dotted/escaped form produced by your flattening rules). Do not treat `PREFIX` as a raw JSON key.

#### Component splitting for matching

Split a rendered path string into components by scanning left-to-right:

- An unescaped `.` starts a new component.
- The only recognized escape sequences are:
  - `\.` (literal dot in current component)
  - `\\` (literal backslash in current component)
- Any other `\X` is treated as a literal backslash followed by `X`.

**Edge-case rule (verifier-aligned):** A path like `café\\.au_lait` contains an escaped dot and therefore has **one** component after splitting (the component unescapes to `café.au_lait`).

#### Matching normalization (Unicode)

Ignore matching must be stable for Unicode text. For matching only (not for rendering), transform each component as follows:

1) Normalize with NFC
2) Case-fold (`casefold()`)
3) Normalize with NFKD and remove all combining marks (category `Mn`)

This makes `café` match `cafe`.

#### Matching rule

Let `P = PREFIX components` and `A = attribute components` (after splitting). Matching MUST use the canonical "matching normalization" for comparison, but the lookahead rule that distinguishes `tags.EnvName` from `tags.Environment` operates on the attribute's original (un-normalized) visible characters after unescaping. The algorithm below is authoritative and must be followed exactly.

Canonical matching algorithm (authoritative):

1) Split `PREFIX` and `attribute` into components using the component splitting rules above (respecting `\.` and `\\`).
2) For every component produce two forms:
   - `unescaped`: the component with `\\` → `\` and `\.` → `.` applied (do not interpret any other `\X`).
   - `normalized`: take the `unescaped` string and apply the Matching normalization sequence: NFC, `casefold()`, NFKD, then remove all Unicode characters with general category `Mn` (combining marks), then (optionally) NFC again. Use this `normalized` value for component equality/starts-with checks.
3) Single-component special case: if the rendered attribute has exactly one component (i.e., it contains no unescaped dots), then matching is a normalized prefix match of the whole component: `normalized(attribute_unescaped)` starts with `normalized(prefix_unescaped)`. This preserves the intended behavior that `--ignore café` matches both `café` and `café\.au_lait`.
4) Multi-component matching (general case): let `Pn` be the list of `normalized` components for `PREFIX`, and `An` the list for `attribute`.
   - If len(Pn) > len(An): NO MATCH.
   - For i in [0 .. len(Pn)-2] (all but last component of `P`): require `Pn[i] == An[i]`.
   - For the final component index j = len(Pn)-1, allow match if either:
   a) `Pn[j] == An[j]` (exact match on normalized component), OR
   b) `An[j]` starts with `Pn[j]` (normalized prefix match) AND the next character in the attribute's original `unescaped` final component (the character immediately following the matched prefix, as measured in the `unescaped` string, not the `normalized` form) exists and is either an ASCII uppercase letter `A`-`Z` or an ASCII digit `0`-`9`.

Notes about the lookahead check:

- The lookahead must operate on the `unescaped` final component (before normalization) so that case folding or combining-mark removal does not hide the presence of an uppercase ASCII letter or digit. For example, do not perform the `A`-`Z` check on the `normalized` string.
- If the matched prefix consumes the entire `unescaped` final component, there is no lookahead character and therefore partial-match condition (b) does not apply; only exact matches succeed in that case.

This rule guarantees the intended behavior: `--ignore tags.Env` matches `tags.EnvName` (because `Name` begins with `N` which is an uppercase ASCII letter), but does NOT match `tags.Environment` (because the next character after the matched prefix is a lowercase `i`).

### Verifier-aligned examples (these are tested)

These examples correspond to real verifier tests and should be used as “golden” behaviors.

1) Unicode ignore prefix ignores accent variants and escaped-dot single-component paths

- Drift contains both `café` and `café\\.au_lait` (escaped dot means the final component is `café.au_lait`).
- Running:

```
python /app/drift_audit.py --ignore café <ideal> <current>
```

must ignore drift entries for **both** `café` and `café\\.au_lait`.

2) Multi-prefix ignores + config rendered paths vs literal-dot component

- Drift contains `config.network.ip` and `config.network\\.ip`.
- Running:

```
python /app/drift_audit.py --ignore config.network <ideal> <current>
```

must ignore `config.network.ip` but must **not** ignore `config.network\\.ip` (because the second component unescapes to `network.ip`, and the lookahead character after the matched prefix is `.` which is not `[A-Z0-9]`).

Pseudocode (Python-like) for matching a single `PREFIX` against an `attribute` string:

```
def normalize_for_match(s):
  # apply NFC, casefold, NFKD, strip Mn, then NFC
  t = unicodedata.normalize('NFC', s)
  t = t.casefold()
  t = unicodedata.normalize('NFKD', t)
  # remove combining marks
  t = ''.join(ch for ch in t if unicodedata.category(ch) != 'Mn')
  t = unicodedata.normalize('NFC', t)
  return t

def unescape_component(comp):
  # only convert \\ -> \ and \. -> . ; leave any other backslash sequences as-is
  return comp.replace('\\\\', '\\').replace('\\.', '.')

def split_components(rendered_path):
  # implement the same scanner used by your renderer: split on unescaped '.'
  ...

def prefix_matches(prefix, attribute):
  P = split_components(prefix)
  A = split_components(attribute)
  P_un = [unescape_component(x) for x in P]
  A_un = [unescape_component(x) for x in A]
  Pn = [normalize_for_match(x) for x in P_un]
  An = [normalize_for_match(x) for x in A_un]

  # single-component special-case
  if len(A_un) == 1:
    return An[0].startswith(Pn[0])

  if len(Pn) > len(An):
    return False

  for i in range(len(Pn)-1):
    if Pn[i] != An[i]:
      return False

  j = len(Pn)-1
  # exact normalized match
  if Pn[j] == An[j]:
    return True

  # normalized prefix + lookahead on unescaped attribute final component
  if An[j].startswith(Pn[j]):
    # Important: the lookahead is performed on the *unescaped* final attribute component
    # and the matched prefix length is measured on the *unescaped prefix* (not the
    # normalized string). Use Python-like character indexing (codepoints), not byte offsets.
    prefix_len = len(P_un[j])
    # If the matched prefix consumes the entire unescaped final component, there is
    # no lookahead character and the partial-match rule does not apply. Only an
    # exact normalized equality (handled above) succeeds in that case.
    if prefix_len < len(A_un[j]):
      next_ch = A_un[j][prefix_len]
      # The lookahead succeeds only when the immediate next character is an ASCII
      # uppercase letter A-Z or an ASCII digit 0-9. Do not case-fold or normalize
      # for this check; inspect the raw `unescaped` character as-is.
      if ('A' <= next_ch <= 'Z') or ('0' <= next_ch <= '9'):
        return True
  return False

```

Edge-case clarifications (authoritative):

- Measuring the prefix length: when computing `prefix_len` use the length of the
  `unescaped` prefix string (the component from `P_un[j]`) measured in Unicode
  codepoints (i.e., `len()` in Python). Do NOT use the normalized or NFKD-decomposed
  lengths for this measurement.
- When `prefix_len == len(A_un[j])` (the matched prefix consumes the entire
  unescaped final component) the partial-match rule with lookahead does NOT apply.
  In that case, the only way the component matches is if the normalized forms are
  exactly equal (the exact-match branch above).
- The single-component special-case (when the rendered attribute contains no
  unescaped dots) uses a normalized prefix comparison of the entire final component
  (i.e., `An[0].startswith(Pn[0])`). This still allows a prefix that equals the whole
  component to match (because it is a normalized starts-with check), which is the
  intended behavior for `--ignore café` matching `café` and `café\.au_lait` when
  the latter is rendered as a single escaped component.

Concrete examples to illustrate the rules (authoritative):

- `--ignore tags.Env` vs attribute `tags.EnvName`:
  - `P_un = ["tags", "Env"]`; `A_un = ["tags", "EnvName"]`
  - Normalized prefix `Pn[1] == "env"`, `An[1] == "envname"` so `An[1]` starts
    with `Pn[1]`. `prefix_len = len("Env") == 3 < len("EnvName")` and the
    next character is `"N"` (ASCII uppercase) → match.

- `--ignore tags.Env` vs attribute `tags.Environment`:
  - `An[1]` starts with `Pn[1]` but the next unescaped character is `"i"` (lowercase)
    → lookahead fails → no match.

- `--ignore cafe` vs attribute `tags.café` or `tags.cafe\u0301Env`:
  - Normalization makes `Pn[-1]` and `An[-1]` comparable; lookahead rules use the
    unescaped attribute final component for the case/digit check, so `--ignore cafe`
    can match `tags.cafeName` (if next unescaped char is `N`) but not `tags.cafee`.

These clarifications remove ambiguity about which string form is used for length
measurement and lookahead, and what happens when the prefix exactly equals the
final component length.
```

Additional examples demonstrating Unicode interaction:

- `--ignore café` should match an attribute whose final component is `café` (composed U+00E9) and also match `cafe\u0301Env` (decomposed `e` + combining acute + `Env`) because normalization + strip-Mn makes `café` and `cafe\u0301` equivalent for matching purposes.
- `--ignore cafe` will match `café` after normalization (so a user may choose to ignore accent variants by supplying the unaccented prefix), but the lookahead rule still inspects the original unescaped final component: `--ignore cafe` will ignore `tags.cafeName` (next char `N` uppercase) but will not ignore `tags.cafee` if the next character is lowercase.
- Escaped-dot example: if the attribute is `config.network\\.ip` (rendered component contains a literal dot), then `--ignore config.network` must NOT match `config.network\\.ip` because the final component is `network.ip` as a single component only if the dot is unescaped; the escape prevents component splitting and the matching semantics behave accordingly.

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

## Verifier tests (required coverage)

The verifier uses `pytest` and runs the CLI as a subprocess:

```
python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

### How the verifier runs (step-by-step)

1) Writes temporary JSON snapshots to disk (both supported formats are used).
2) Calls the CLI with different argument combinations (including usage errors and `--ignore`).
3) For exit `0`, parses stdout JSON and checks schema + determinism (ordering and static timestamp).
4) For non-zero exits, asserts stdout is empty and stderr is non-empty (and for usage errors, stderr must be exactly the usage line).

### Complete test list (all tests must pass)

- `test_usage_message_is_exact` — Usage errors exit `2`, stdout empty, stderr is exactly `USAGE_LINE + "\n"`.
- `test_missing_file_is_io_error_no_traceback` — Missing files are I/O errors (exit `1`) with no traceback.
- `test_invalid_json_is_parse_error_no_traceback` — Invalid JSON is a parse error (exit `2`) with no traceback.
- `test_simplified_format_drift_report_is_deterministic` — Format A drift detection + deterministic ordering and expected drift entries.
- `test_nested_attributes_are_flattened_and_lists_are_atomic` — Nested dicts flatten to dot paths; lists compare atomically.
- `test_attributes_present_only_on_one_side_are_reported_as_null` — Attributes missing on one side report `null` expected/actual.
- `test_ignore_prefix_filters_attribute_drift_entries` — `--ignore` removes matching drift entries.
- `test_terraform_like_format_is_supported_and_child_modules_are_walked` — Format B supported; walks child modules.
- `test_duplicate_resource_ids_are_parse_errors` — Duplicate `<type>.<name>` ids in one snapshot are parse errors.
- `test_attribute_paths_escape_dots_in_keys` — Escapes dots in literal keys using `\.`.
- `test_attribute_paths_escape_backslashes_then_dots` — Escapes backslashes first, then dots.
- `test_ignore_prefix_matches_escaped_attribute_paths` — Ignore matching works on rendered/escaped attribute paths.
- `test_deeply_nested_attributes_flattened_correctly` — Deep nesting produces correct flattened paths.
- `test_complex_lists_with_dicts_are_atomic` — Lists that contain dicts remain atomic (no flattening inside lists).
- `test_unicode_and_special_chars_in_keys` — Handles Unicode/special characters in keys for both render and compare.
- `test_multiple_child_modules_with_conflicts` — Multiple modules + conflicts are handled correctly.
- `test_ignore_with_partial_prefix_matches` — Ignore matching is component-aware and respects partial match rules.
- `test_mixed_formats_in_same_snapshot` — Mixed snapshot shapes are treated per spec (parse errors as applicable).
- `test_very_deep_nesting` — Stress test for flattening/recursion depth.
- `test_many_attributes` — Handles many attributes deterministically.
- `test_unicode_in_values` — Unicode values compare properly (no coercion).
- `test_special_chars_in_keys` — Special characters in keys render/compare properly.
- `test_child_modules_deep` — Deep child-module traversal is correct.
- `test_ignore_partial_matches` — Validates the lookahead rule for partial final-component matches.
- `test_escaped_dots_complex` — Complex escaping scenarios behave as specified.
- `test_lists_with_nested_dicts_atomic` — Additional list atomicity coverage.
- `test_null_values` — Correct handling of `null` values.
- `test_empty_strings` — Empty strings compare correctly and are not dropped.
- `test_large_numbers` — Large numeric values compare correctly without type coercion.
- `test_case_sensitivity` — Ensures case sensitivity is preserved for drift (no unintended normalization in rendering).
- `test_mixed_formats_with_child_modules` — Mixed formats + child modules work together.
- `test_ignore_with_unicode` — Ignore matching handles Unicode normalization rules.
- `test_boolean_values` — Booleans compare correctly with no coercion to numbers.
- `test_type_coercion_traps` — Ensures strings/numbers/bools aren’t coerced.
- `test_extreme_nesting_50_levels` — Extreme nesting stress test.
- `test_ignore_edge_cases` — Edge cases around ignore parsing and matching.
- `test_unicode_bombs` — Robustness against tricky Unicode forms.
- `test_large_inputs_1000_attributes` — Performance/determinism with very large attribute sets.
- `test_seeded_generated_nested_drift_and_ignore_is_not_trivially_hardcoded` — Seeded randomized drift/ignore coverage to prevent hardcoding.

