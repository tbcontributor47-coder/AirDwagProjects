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

# Terraform Drift Audit — Concise Runtime Contract

Implement the CLI `/app/drift_audit.py` to compare an **ideal** and **current** Terraform state snapshot and print a deterministic JSON drift report.

Usage (exact):

```
Usage: python /app/drift_audit.py [--ignore PREFIX]... <ideal_state.json> <current_state.json>
```

Behavior summary:

- Exit `2` and print the exact usage line to stderr (and nothing to stdout) on usage errors.
- Exit `1` on file I/O errors (stdout empty, stderr non-empty).
- Exit `2` on parse errors (invalid JSON, unsupported shape, or duplicate resource ids).
- On success exit `0` and print exactly one JSON object to stdout (report) followed by a newline.

Report format (exact keys):

```
{
  "audit_timestamp": "STATIC",
  "drift_detected": <bool>,
  "missing_resources": [<resource_id>...],
  "extra_resources": [<resource_id>...],
  "attribute_drift": { <resource_id>: [ {"attribute": <path>, "expected": <val|null>, "actual": <val|null>}, ... ] }
}
```

Core rules (concise):

1) Input formats: support two snapshot shapes:
   - Simplified: top-level `resources` list with objects containing `type` (str), `name` (str), and `attributes` (object).
   - Terraform-like: `values.root_module` with nested `resources` (attributes under `values`) and `child_modules` recursively.
   - Normalise either form into a map resource_id -> attributes where resource_id is `type.name`. Duplicate ids in one snapshot are a parse error.

2) Attribute flattening and path rendering:
   - Flatten nested objects into dot-delimited paths; lists are atomic values.
   - When escaping literal key names: first escape backslashes (`\`→`\\`), then dots (`.`→`\.`).
   - Top-level keys starting with `config.` or `tags.` are treated as already-rendered prefixes (used as-is, with their internal `.` as separators).

3) Drift computation:
   - Missing/extra resources are computed from resource id sets and sorted.
   - For shared resources flatten both attribute objects and compare the union of paths. When values differ produce drift entries with `expected` or `actual` set to `null` for missing sides.

4) Ignore filtering:
   - `--ignore PREFIX` filters drift entries after flattening by removing any entry whose rendered attribute path equals or has the ignore prefix as a path-component prefix (i.e., exact or descendant match using rendered paths).

5) Deterministic ordering:
   - Sort resource ids lexicographically for `attribute_drift` keys.
   - For each resource, sort its drift entries by `attribute` using standard lexicographic ordering except treat the space character `' '` as greater than any other character when comparing.

6) Output:
   - `audit_timestamp` must be `STATIC`.
   - `drift_detected` is true iff there are any missing/extra resources or any remaining attribute drift entries after ignores.

Errors: do not print Python tracebacks; use concise stderr messages and correct exit codes.

This concise spec contains the behaviors the verifier tests exercise. Implement these precisely.

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

