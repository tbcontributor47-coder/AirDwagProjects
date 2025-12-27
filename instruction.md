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

Notes:
- `--ignore` must be followed by a value. If `--ignore` is provided without a following `PREFIX`, that is a usage error.

### Usage errors

If the CLI is invoked incorrectly, exit `2` and print **exactly** this usage line to stderr:

```
Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

No Python traceback may be printed.

## Input

Both inputs are UTF-8 JSON files.

If either input cannot be parsed as JSON due to invalid JSON syntax, that is a **parse error** and the program must exit `2`.

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
- Lists are treated as **atomic** values (no per-index flattening). If two lists differ, the attribute path is the list's key.

### Flattening / attribute path rendering

Flatten nested objects recursively into dot-delimited attribute paths.

**Escaping (literal key characters)**

When rendering a *key name* into a path segment, escape characters in this order:

1) Escape backslashes: `\` becomes `\\`
2) Escape dots: `.` becomes `\.`

Example: key `Environment.Name` under `tags` becomes `tags.Environment\.Name`.

Example (backslash + dot): key `path\to.file` under `meta` becomes `meta.path\\to\.file`.

Algorithm (precise):

- To render a literal key name into a single path segment, apply:
  1) Replace every `\` with `\\`.
  2) Then replace every `.` with `\.`.

No other characters are escaped.

**Top-level key handling (important)**

Some snapshots contain already-rendered dot paths as top-level attribute keys.
For top-level attributes (i.e., when the current prefix is empty):

- If the key starts with `config.`: treat it as an already-rendered dot path (do **not** escape the separator dots).
- If the key starts with `tags.`: treat it as an already-rendered dot path *unless* `tags.Env` is present as a top-level key in the same attributes object.
  - If `tags.Env` is present, treat **all** top-level `tags.*` keys as **literal keys** and therefore escape their dots/backslashes as normal.
- Otherwise: treat the key as a literal key name and escape dots/backslashes as above.

Clarification (already-rendered vs literal):

- “Already-rendered dot path” means the key string itself is used as the path prefix *as-is* at the top level (its unescaped dots act as component separators). If its value is a nested object, flatten that object under this prefix, and for those nested keys (prefix is now non-empty) apply the literal escaping rules.
- “Literal key” means the key string is treated as a single key name, so any `.` inside it must be escaped to `\.` and any `\` must be escaped to `\\`.

Example (tags exception): if the top-level attributes contain both `tags.Env` and `tags.Environment`, then both are treated as *literal keys* and their rendered paths are `tags\.Env` and `tags\.Environment`.

For nested objects (i.e., when prefix is non-empty), key names are always treated as literal and must be escaped.

### `--ignore` prefix matching

`--ignore PREFIX` is matched against the **rendered** attribute paths.

Important: ignore matching is **segment-aware**. A prefix must match **path components**, not arbitrary substrings. For example, the ignore prefix `ags` must not match the attribute path `tags.Environment`.

Matching is **component-aware**, where components are separated by **unescaped dots**:

- Unescaped `.` separates components.
- Escaped dots (`\.`) are literal dots within a component.
- Escaped backslashes (`\\`) are literal backslashes within a component.

Parsing rendered paths into components (precise):

- Scan the rendered string left-to-right.
- A `.` character starts a new component **only** when it is **not** escaped.
- A backslash escape is recognized only for these two sequences:
  - `\.` represents a literal `.` within the current component.
  - `\\` represents a literal `\` within the current component.
- Any other `\X` sequence (where `X` is not `.` or `\`) is treated as a literal backslash followed by `X` (i.e., it does **not** form an escape).

Unescaping (used only for the “single component” case below):

- Convert `\\` to `\`, then convert `\.` to `.`.

An ignore prefix matches an attribute path if either:

1) The rendered attribute path is a *single component* (i.e., it contains **no unescaped dots**). In this case, unescape both the rendered attribute path and the provided `PREFIX` (using the unescape procedure above) and treat it as a simple string-prefix match.

2) Otherwise, do component-aware matching:
   - All components except the last must match exactly.
   - For the final component:
     - Exact match is ignored.
     - Additionally, allow a **partial** match where the final component starts with the prefix's final component **and** the next character is an uppercase letter or digit. (This supports patterns like ignoring `tags.Env*` matching `tags.EnvName` but not `tags.Environment`.)

Notes (to avoid substring ambiguity):

- The “partial match” rule applies **only** to the final component, and only with the uppercase/digit lookahead. Otherwise, components must match exactly at component boundaries.
- Example: `--ignore tags.Env` matches `tags.EnvName` (next char after `Env` is `N`) but does **not** match `tags.Environment` (next char after `Env` is `i`).

This component-aware behavior is required so that, for example, `--ignore config.network` ignores `config.network.ip` but does **not** ignore `config.network\.ip` (where the dot is literal/escaped).

### Unicode handling for `--ignore` prefixes (clarification)

Attribute keys and ignore prefixes may contain non-ASCII characters (for example, `café`). To avoid ambiguity about how such characters are matched, the following precise procedure MUST be used when determining whether an ignore prefix matches a rendered attribute path:

1. Rendering and escaping: produce the rendered attribute path exactly as described above (with backslashes and dots escaped per the rules). The matching algorithm works on these rendered strings.

2. Matching-normalization: to produce a stable matching form for both the rendered attribute path and for each provided `PREFIX`, apply the following transforms to each string before performing prefix/component comparisons:
  - Normalize to Unicode Normalization Form C (NFC).
  - Case-fold using Unicode casefolding (i.e., `str.casefold()` semantics) so matching is case-insensitive in a Unicode-aware way.
  - Apply compatibility decomposition (NFKD) and remove all combining marks (Unicode category `Mn`) to strip diacritics (so `café` becomes `cafe`). This makes ignore prefixes with ASCII letters match attributes that differ only by diacritics.

  The result is the "matching key" for that path or prefix.

3. Component splitting: split the rendered attribute path into components on unescaped dots (as described previously). Also split the provided `PREFIX` on unescaped dots. Create matching-key components by applying the matching-normalization above to each component separately.

4. Component-aware comparison: apply the same component-aware matching rules described earlier, but operate on the matching-key components:
  - All components except the final one must match exactly (matching-key equality).
  - For the final component apply either an exact match (matching-key equality) or, when the final matching-key of the attribute starts with the final matching-key of the prefix and the character immediately after the prefix in the original (pre-normalized, rendered) final component is an uppercase letter or a digit, treat that as a valid partial match (this preserves the original rule that allows `tags.Env*` semantics while still using fold/diacritic-insensitive matching for equality/prefix checks).

5. Notes and rationale:
  - The matching process is intentionally diacritic- and case-insensitive to make `--ignore cafe` match both `cafe` and `café` as the test expects.
  - The special-case lookahead (uppercase-or-digit) is evaluated on the original rendered final component (before casefold/diacritic stripping) so it continues to support the original intent of treating `tags.Env*` as matching `tags.EnvName` but not `tags.Environment`.
  - Escaped dots and backslashes are still respected when splitting components and when rendering the report; only the matching step uses the normalized/diacritic-stripped matching keys.

Adding this explicit procedure removes ambiguity around Unicode characters in ignore prefixes while preserving the component-aware and literal-escaping semantics already described.

## Output

On success, print the audit report as JSON to stdout, followed by a newline.

The output must be fully deterministic:

- `audit_timestamp` must be the literal string `STATIC`.
- `missing_resources` and `extra_resources` must be sorted.
- `attribute_drift` keys must be sorted.
- Each resource's drift entries must be sorted by `attribute`.
  - Sorting is lexicographic on the rendered `attribute` string, with a special case: treat spaces as sorting *after* all other characters (i.e., as if `' '` were a very large character) so that keys with spaces come last.

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
- Exit `2` for usage errors or parse errors (including invalid JSON syntax / JSON decoding errors).

### What is a parse error?

Treat each of the following as a **parse error** (exit code `2`):

- **Invalid JSON syntax** (e.g., the file contains malformed JSON like `{`).
- Unsupported schema / missing required keys.
- Duplicate normalized resource identifiers.

On any error:

- Print a human-readable message to stderr.
- Do not print a Python traceback.
