# EFT File Validation (Fixed-Width Payments)

You are given a small CLI program inside the container at:

- `/app/validate_eft.py`

The program is **buggy**. Fix it.

This document is the full runtime contract. Implement exactly what is specified.

## Step-by-step implementation checklist (required)

Implement `/app/validate_eft.py` exactly as this pipeline. This section is intentionally procedural to reduce ambiguity for agents.

### Step 0: parse CLI args

The verifier supplies valid arguments, but your code must still be robust and must not print a Python traceback.

Read:

- `file_path`
- `schema_path`
- `clearing_accounts_path`
- `index_db_path`
- `retention_days` (default 5)
- optional `payees_db_path`

### Step 1: load schema JSON

1) Read `schema_path` as UTF-8 JSON.
2) Validate required keys:
   - `record_length` is an integer `L`.
   - `fields` is a list.
3) For each field descriptor in `fields`, validate:
   - `name` string
   - `start` int
   - `length` int
   - `type` in `{string, decimal, date}`
   - `required` boolean
   - optional `pattern` string
   - optional `format` string

If schema cannot be loaded/parsed, treat it as a validation failure (non-zero) and still print exactly one JSON report.

### Step 2: load clearing accounts

1) Read the clearing accounts file as UTF-8 text.
2) Split into lines.
3) For each line, compute `acct = line.strip()`.
4) Keep `acct` if it is non-empty.

Result: `allowed_clearing_accounts: set[str]`.

### Step 3: read payment file bytes and compute `file_hash`

Compute `file_hash` before validation so it is always present.

Use the canonicalization rules exactly as specified in the “Canonicalization (exact)” section below.

**Important (verifier-aligned):**

- Stdout must contain **only** the single JSON report (no log lines, no extra text).
- If you need to print diagnostics, print them to stderr.
- Always compute and include `file_hash` in the report, even when validation fails.

## Authoritative execution order (to avoid ambiguity)

The verifier expects these values to be consistent with each other:

1) Compute `file_hash` from the canonicalized file content (Step 3).
2) Parse records to compute `records_processed` (Step 5.1) and collect `errors` (Steps 5.2–5.6).
3) Perform duplicate detection using the `file_hash` and retention logic (Step 4).
  - You MAY query for duplicates earlier, but you MUST NOT attempt to insert the index row until after `records_processed` is known.
4) Build the JSON report (Step 6) and decide exit code (Step 7).

This ordering ensures `record_count` written to SQLite always equals the `records_processed` you report.

### Step 4: duplicate detection (SQLite index)

If `retention_days <= 0`:

- Set `duplicate = false`.
- Skip duplicate checks.

Else:

1) Open SQLite DB at `index_db_path` (create if missing).
2) Ensure the table `file_index` exists (create if missing).
3) Determine a cutoff timestamp `cutoff = now - retention_days`.
   - Store timestamps in ISO-8601 (use `datetime.now().isoformat()` for insertion).
  - For comparison, parse ISO timestamps into datetimes.
4) Query for any prior submission with the same `file_hash` and a timestamp >= cutoff.
   - If any exists: set `duplicate = true`.
   - Else: `duplicate = false`.
5) If `duplicate` is false, insert a new row with:
   - `file_hash`
   - `filename` (input filename or full path)
   - `timestamp` (ISO-8601 now)
   - `record_count` (records_processed)

Timestamp parsing rule (to avoid edge-case ambiguity):

- If an existing row’s timestamp cannot be parsed as ISO-8601, ignore that row for retention comparisons.

Important:

- Duplicate is based on `file_hash` only (filename must not affect the duplicate decision).
- Same content under different filenames must still be detected.

**Retention disable rule (verifier-aligned):** when `retention_days <= 0`, duplicate detection is disabled:

- Always report `duplicate: false`.
- Do not query the DB for duplicates.
- Do not insert anything into the DB.

### Step 5: parse records and validate

Let `L = record_length` from schema.

5.1) Split records

- Read the payment file as UTF-8 text.
- Normalize line endings (`\r\n` and `\r` to `\n`).
- Split on `\n`.
- Remove empty trailing lines at the end (lines that are `""` after removing the line ending).

Notes (verifier-aligned):

- Only remove **trailing** empty lines at the end.
- Do NOT drop empty lines in the middle; they count as records and will typically fail the length rule (`len(line) < L`).

Let the remaining list be `records`.

Set:

- `records_processed = len(records)`

5.2) For each record line `records[i]` (1-based line number `line_no = i+1`)

Record length rules (must match verifier):

- If `len(line) < L`: error.
- Else if `len(line) == L`: ok.
- Else (`len(line) > L`):
  - If `line[L:].strip() == ""` (only spaces/tabs): accept, and use `line = line[:L]` for parsing.
  - Otherwise: error.

Field extraction:

- For each field descriptor:
  - `raw = line[start:start+length]`
  - `value = raw.strip()`

Collect all field values into a dict `row` keyed by field name.

5.3) Required-field validation

For each schema field with `required == true`:

- If `row[name] == ""`: add error `Line N: <field> is required`.

5.4) Field-specific validation (verifier-checked)

Validate these names if present in schema:

- `eftno`:
  - must be non-empty
  - must be alphanumeric (letters/digits only)

- `bank_code`:
  - must start with a digit (`0`-`9`) (include substring `must start with a digit` in the error)
  - must contain only uppercase letters and digits
  - lowercase letters are invalid
  - special chars (including spaces or punctuation) are invalid

- `account_no`:
  - must be all digits
  - must be length 8..20 (inclusive)
  - Define the **core account** `acct8 = account_no[:8]` (the leftmost 8 digits).
    - The verifier’s “first 4 digits” and “last digits” rules apply to `acct8`, not the full 8–20 digit string.
    - Rationale (verifier-aligned): the provided `valid_payment.txt` uses 20-digit `account_no` values that may contain `0` in their *overall* trailing digits and must still be considered valid.
  - forbidden prefixes (must error): `acct8[:4]` is any of `0000`, `0001`, `0010`, `0100`
  - first 4 digits must not consist solely of `0` and `1` (apply to `acct8[:4]`; error text must contain `First 4 digits` or `0 and 1`)
  - the last 2 digits must not contain `0` (apply to `acct8[-2:]`; error text must contain `cannot contain 0`)

- `amount`:
  - parse as decimal
  - must be strictly greater than 0 (error text must contain `must be > 0` or `greater than 0`)
  - must have at most 2 digits after the decimal point

- `clearance_date`:
  - parse using schema `format` if present (verifier uses `%Y-%m-%d`)
  - invalid date is an error

- `clearing_account`:
  - after trimming, must be contained in `allowed_clearing_accounts` exactly
  - substring matches must NOT be accepted

5.5) Schema regex validation (optional)

If a field descriptor includes `pattern`, enforce it as a full regex match against the trimmed value.

5.6) Payees DB checks (only when `--payees-db` is provided)

For each record, after `account_no` and `payee_name` are parsed:

1) Query `payees` table by `account_no`.
   - If no row: error containing `not found in payee database` or `Account`.
2) If `fraud_flag == 1`: error containing `fraud` or `risk`.
3) Compare payee names case-insensitively:
   - Normalize both:
     - `strip()`
     - collapse internal whitespace runs to one space
     - compare with `.casefold()`
   - If mismatch: error containing `name mismatch` or `payee name`.

Important note:

- The verifier expects payee name comparison to be case-insensitive (e.g., `john doe` must match `JOHN DOE`).

### Step 6: build the JSON report

Always print one JSON object with the required keys.

Compute:

- `n_errors = len(errors)`
- `n_warnings = 0`

Set `duplicate` based on Step 4.

### Step 7: choose exit code

- If `duplicate == true`: exit non-zero.
- Else if `n_errors > 0`: exit non-zero.
- Else: exit `0`.

Exit-code truth table (authoritative)

- If `duplicate` is `true` → exit code is non-zero (the verifier only checks “non-zero”, you may use `1`).
- Else if `n_errors > 0` → exit code is non-zero.
- Else (`duplicate == false` AND `n_errors == 0`) → exit code is exactly `0`.

This is the logic behind tests like `test_valid_file_validation` (expects `0`) and `test_duplicate_detection` (expects non-zero on the second run).

## CLI contract

The verifier invokes the program as:

```
python /app/validate_eft.py --file <payment_file.txt> --schema <schema.json> --clearing-accounts <clearing_accounts.txt> --index <index.db> [--retention-days N] [--payees-db payees.db]
```

Arguments:

- `--file`: path to the fixed-width text file to validate
- `--schema`: path to a JSON schema file (described below)
- `--clearing-accounts`: path to a text file containing allowed clearing accounts (one per line)
- `--index`: path to a SQLite DB used for duplicate detection
- `--retention-days`: optional integer; default is `5`
- `--payees-db`: optional path to a SQLite DB containing payee records (the verifier passes `payees.db`)

The verifier always passes valid CLI arguments. You still must avoid printing a Python traceback.

## Output contract

For every invocation (success, validation failure, or duplicate), print exactly one JSON object to stdout.

The JSON object must contain at least these keys:

- `duplicate`: boolean
- `n_errors`: integer
- `n_warnings`: integer
- `errors`: array of strings
- `warnings`: array of strings
- `file_hash`: string (64 lowercase hex characters)
- `records_processed`: integer

Notes:

- The verifier parses stdout as JSON even on failures.
- Set `n_warnings = 0` and `warnings = []`.

### Exit code

- Exit `0` only if:
  - `duplicate` is `false`, and
  - `n_errors` is `0`.
- Exit non-zero if either:
  - `duplicate` is `true`, or
  - `n_errors` is greater than `0`.

## Input files

### 1) Payment file (`--file`)

The payment file is UTF-8 text. It contains fixed-width records, one record per line.

Line ending handling:

- Treat `\r\n` and bare `\r` as `\n`.

Trailing empty lines:

- Ignore empty trailing lines at the end of the file for both hashing and `records_processed`.

### 2) Schema JSON (`--schema`)

The validator must use the provided schema file for parsing.

The schema JSON has this shape:

```json
{
  "record_length": 296,
  "fields": [
    {
      "name": "eftno",
      "start": 0,
      "length": 12,
      "type": "string",
      "required": true,
      "pattern": "^...$",
      "format": "%Y-%m-%d"
    }
  ]
}
```

Rules:

- `record_length` is an integer.
- `fields` is a list of objects.
- Each field object contains:
  - `name` (string)
  - `start` (integer, 0-based offset)
  - `length` (integer)
  - `type` (string): one of `string`, `decimal`, `date`
  - `required` (boolean)
  - Optional `pattern` (string regex) for `string` fields
  - Optional `format` (strftime format string) for `date` fields

Parsing a field:

- Slice `raw = line[start : start + length]`.
- The value used for validation is `raw.strip()`.

### 3) Clearing accounts file (`--clearing-accounts`)

This is a UTF-8 text file with one allowed clearing account per line.

- Each line is trimmed with `strip()`.
- Empty lines are ignored.
- A record’s `clearing_account` must match one of these allowed values **exactly** after trimming (no substring matching).

## Record handling and `records_processed`

Let `L = record_length` from the schema.

For each non-empty record line (after removing the line ending):

- If `len(line) < L`: this record is invalid.
- If `len(line) > L`:
  - If the suffix `line[L:]` contains any non-whitespace character after `strip()` (i.e., not purely padding spaces/tabs), this record is invalid.
  - Otherwise, treat the record content as `line[:L]` for parsing.

`records_processed` is the count of records processed after dropping trailing empty lines.

## File hashing and duplicate detection

Duplicate detection is based on the file’s **normalized content** and is independent of filename.

### Canonicalization (exact)

Compute `file_hash` as SHA-256 over the canonicalized UTF-8 bytes.

Canonicalization steps:

1) Read file bytes and decode as UTF-8.
2) Normalize line endings:
   - Convert all `\r\n` to `\n`.
   - Convert remaining bare `\r` to `\n`.
3) Split into lines on `\n`.
4) For each line, remove trailing spaces and tabs:
   - `rstrip(" \t")`
5) Remove empty trailing lines at the end (lines that become `""`).
6) If there is at least one remaining line, join them with `\n` and append exactly one final `\n`.
   If there are no remaining lines, the canonical content is the empty string.
7) Hash the canonical content with SHA-256 and format as 64 lowercase hex characters.

This makes these logically equivalent for hashing:

- `\n` vs `\r\n`
- trailing spaces at end of line
- extra empty lines at end
- presence/absence of a final newline

### Retention window

Duplicate detection considers only submissions within the last `N` days:

- `N` is `--retention-days` if provided, else default `5`.
- If `N <= 0`, duplicate detection is **disabled**:
  - Always report `duplicate: false`.
  - Do not fail an otherwise-valid file as duplicate.

### SQLite index (`--index`)

The validator stores submissions in a SQLite DB. Create the DB and table if needed.

The verifier may pre-create the DB. Your code must work with a schema at least as capable as:

```sql
CREATE TABLE IF NOT EXISTS file_index (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_hash TEXT NOT NULL,
  filename TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  record_count INTEGER,
  UNIQUE(file_hash, timestamp)
);
```

Required behavior:

- A file is a duplicate if there exists a prior row whose `file_hash` equals the current `file_hash` and whose `timestamp` is within the last `N` days.
- The filename must not be part of the duplicate key. Same content under a different filename must still be detected.
- On first-seen (non-duplicate) files, insert a row with:
  - `file_hash`
  - `filename` (can be the input basename or full path)
  - `timestamp` in ISO-8601 (any `datetime.now().isoformat()`-style string is acceptable)
  - `record_count` equal to `records_processed`

### Ignore-prefix matching and Unicode normalization (optional `--ignore` semantics)

Some tests (and implementers) expect an optional ignore-style matching feature when comparing identifiers, paths, or other componentized strings. If your implementation supports an `--ignore`-style list of JSON Pointer-like prefixes (or any component-path prefixes used when comparing values), it MUST follow the precise Unicode normalization and matching semantics described here. Even if you do not expose `--ignore`, these rules clarify how to implement any component-aware matching used by the validator.

Canonicalization steps for each path component
- For any component string used in prefix matching, apply these transformations in this exact order:
  1. Normalize to NFC (Unicode Normalization Form C).
  2. Apply Unicode case-folding (use `str.casefold()` or equivalent).
  3. Normalize to NFKD (Compatibility Decomposition).
  4. Remove all combining marks (Unicode category `Mn`).
  5. Normalize back to NFC.

Rationale: this sequence (NFC → casefold → NFKD → strip `Mn` → NFC) ensures composed/decomposed forms, case differences, and common accent/diacritic variations are handled consistently (for example, `café`, `café` (decomposed), and `CAFE` all canonicalize to the same token `cafe`).

Component-aware prefix matching rules
- When matching a candidate component path against an ignore prefix, first split both into components (for JSON Pointer-style paths: unescape per RFC6901, then split on `/`; for dotted or other separator-based paths, split on the separator after applying the same unescape rules used by your code).
- Normalize every component using the canonicalization steps above and then compare component-by-component.
- Standard prefix match: the ignore prefix `I = [i0..iM]` matches candidate path `P = [p0..pN]` if `M <= N` and for all k in 0..M-1, `normalize(i_k) == normalize(p_k)`.

Single-component special-case
- If the ignore prefix has exactly one non-empty component (i.e., length 1 after splitting), treat it as a component-level match that succeeds if any component of the candidate path, after normalization, equals that single normalized component. For example, an ignore `/café` should match `/users/café/id` and `/users/cafe/id` and `/users/CAFE/id`.

Edge cases and implementation notes
- The root prefix (`/` or empty components list) matches all paths.
- Always apply identical normalization to both the ignore prefixes and the candidate paths.
- Implementations must not treat the matching as a simple substring search — it must be component-aware unless a single-component special-case applies as above.

Pseudocode (Python-style) for component normalization and matching

```
import unicodedata

def normalize_component(s: str) -> str:
  s = unicodedata.normalize('NFC', s)
  s = s.casefold()
  s = unicodedata.normalize('NFKD', s)
  s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
  return unicodedata.normalize('NFC', s)

def matches_ignore(ignore_components: list[str], candidate_components: list[str]) -> bool:
  I = [normalize_component(c) for c in ignore_components]
  P = [normalize_component(c) for c in candidate_components]
  if len(I) == 0:
    return True
  if len(I) == 1:
    return any(pc == I[0] for pc in P)
  if len(I) > len(P):
    return False
  return all(I[k] == P[k] for k in range(len(I)))
```

Examples
- Ignore `/meta/generated_at` matches `/meta/generated_at` and `/meta/generated_at/2025`.
- Ignore `/café` (single-component) matches `/users/café/id`, `/users/cafe/id`, and `/users/CAFE/id`.

Testing
- If you add or rely on ignore behavior in your implementation, include unit tests that verify composed and decomposed Unicode forms, case differences, and the single-component special-case.


## Validation rules

Validation is performed per record line. All errors for all records must be collected.

Error message formatting requirements (verifier-checked):

- Every error string must include the 1-based line number prefix `Line N`.
- Some tests look for these substrings in at least one error when relevant:
  - `First 4 digits`
  - `cannot contain 0`
  - `must start with a digit`
  - `must be > 0` (or `greater than 0`)
  - `fraud` or `risk`
  - `name mismatch` or `payee name`

### Required fields

If a field is marked `required: true` in the schema and the parsed value is empty after trimming, that is an error.

### Field-specific checks (required)

These checks are required regardless of whether the schema also provides patterns:

- `eftno`:
  - must be non-empty
  - must be alphanumeric (letters/digits only)

- `bank_code`:
  - must be non-empty
  - must start with a digit (`0`-`9`) (error text must include `must start with a digit`)
  - must contain only uppercase letters (`A`-`Z`) and digits (`0`-`9`)
    - lowercase letters are invalid
    - special characters/spaces are invalid

- `account_no`:
  - must be 8–20 digits only
  - must not start with any forbidden prefix: `0000`, `0001`, `0010`, `0100`
  - first 4 digits must not consist solely of `0` and `1` (error text must include `First 4 digits` or `0 and 1`)
  - Define the core account `acct8 = account_no[:8]`.
  - the last 2 digits of `acct8` must not contain `0` (error text must include `cannot contain 0`)

- `amount`:
  - parse as a decimal number
  - must be strictly greater than 0 (error text must include `must be > 0` or `greater than 0`)
  - must have at most 2 decimal places

- `clearance_date`:
  - parse using the schema field’s `format` if provided (the verifier schema uses `%Y-%m-%d`)
  - invalid dates are errors

- `clearing_account`:
  - must match an allowed account from `--clearing-accounts` exactly after trimming

### Optional regex patterns from schema

If a schema field contains `pattern`, treat it as a full regex that must match the trimmed value exactly.

### Payees database checks (`--payees-db`)

If `--payees-db` is provided, validate each record’s `account_no` against the database.

The DB contains a `payees` table like:

```sql
CREATE TABLE payees (
  account_no TEXT PRIMARY KEY,
  payee_name TEXT NOT NULL,
  home_branch TEXT,
  address TEXT,
  national_id TEXT,
  fraud_flag INTEGER DEFAULT 0
);
```

Rules:

1) Unknown account:
   - If `account_no` is not present in `payees`, that is an error.
   - The error message must include `not found in payee database` or `Account`.

2) Fraud flag:
   - If `fraud_flag = 1`, that is an error.
   - The error message must include `fraud` or `risk`.

3) Payee name match:
   - Compare the file’s `payee_name` to the DB `payee_name` case-insensitively.
   - Normalization procedure:
     - trim
     - collapse internal whitespace runs to a single space
     - compare with Unicode-aware `casefold()`
   - If it does not match, that is an error.
   - The error message must include `name mismatch` or `payee name`.

## Performance constraints

- Must handle at least 1,000 records per file.
- Must not be quadratic in number of records.

## Verifier-aligned sanity examples

These are examples of situations the verifier tests.

### Example: CRLF + trailing spaces hash the same

If one file ends with `"...<line>   \r\n\r\n"` and another ends with `"...<line>\n"`, they must produce the same `file_hash` and be treated as duplicates (unless `--retention-days <= 0`).

### Example: extra padding beyond record length

If `record_length == 296`, a line with length 306 containing only spaces after position 296 must be accepted.

If the extra suffix contains any non-whitespace character (e.g., `X`), it must be rejected.

## Verifier tests (required coverage)

The verifier uses `pytest` and invokes the CLI as an external process. Your implementation must satisfy *every* test below.

### How the verifier runs (step-by-step)

1) Creates a temporary directory.
2) Writes a schema JSON and a clearing-accounts text file.
3) Chooses a SQLite index DB path inside the temp directory.
4) Runs the CLI using Python:

```
python /app/validate_eft.py --file <payment_file.txt> --schema <schema.json> --clearing-accounts <clearing_accounts.txt> --index <index.db> [--retention-days N] [--payees-db payees.db]
```

5) Reads stdout and parses it as JSON.
6) Checks exit codes:
  - `0` only when `duplicate == false` AND `n_errors == 0`.
  - Non-zero otherwise.
7) Checks key edge cases: record length handling, hashing canonicalization, duplicate retention window logic, strict field validations, and optional payees DB behavior.

## Tests To Pass (explicit expectations)

The verifier runs a suite of `pytest` tests that invoke the CLI as an external process. Implement the behaviors below exactly; each named test is machine-checked and must pass.

- `test_env` — Test harness fixture: your code must accept the standard CLI arguments and work with temp files and an index DB path supplied by the verifier.
- `test_valid_file_validation` — Valid input must print exactly one JSON object to stdout with keys: `duplicate` (bool), `n_errors` (int), `n_warnings` (int), `errors` (list), `warnings` (list), `file_hash` (64 lowercase hex string), and `records_processed` (int). Process must exit `0`.
- `test_duplicate_detection` / `test_duplicate_detection_across_filenames` — Duplicate detection is based solely on the canonical `file_hash`. Submitting identical canonical content twice within the retention window must set `"duplicate": true` on the second run and exit non-zero. When `--retention-days <= 0`, duplicate detection is disabled: always report `"duplicate": false` and do not insert index rows.
- `test_retention_window` / `test_retention_days_flag_affects_duplicate_detection` — Use `datetime.now().isoformat()` for inserted timestamps. A stored row is considered in-window when its ISO timestamp is **>=** (`now - retention_days`). Ignore rows with unparseable timestamps.
- `test_invalid_file_validation` — Invalid input must exit non-zero and `n_errors > 0` in the reported JSON.
- `test_errors_include_line_numbers_and_multiple_issues` — Every reported error string must include the `Line N` prefix and multiple independent issues for the same record must all appear as separate error entries.
- `test_hash_normalization_crlf_and_trailing_spaces` — `file_hash` must follow the canonicalization rules: normalize CRLF/bare-CR to `\n`, `rstrip(" \t")` per line, drop trailing empty lines, then join with `\n` and append a single final `\n` before SHA-256.
- `test_crlf_line_endings_with_trailing_spaces` — Robustness for mixtures of CRLF, bare CR, trailing spaces/tabs; canonical hash must be identical as specified.
- `test_empty_lines_at_end` — Trailing empty lines are ignored for hashing and for `records_processed`.
- `test_randomized_record_not_hardcoded` — Implementation must be schema-driven and data-driven; do not hardcode sample values.
- `test_exact_record_length_enforced` / `test_exact_length_with_padding` — Enforce `record_length` rules: `len(line) < L` → error; `len(line) == L` → OK; `len(line) > L` → accept only if suffix `line[L:].strip() == ""` (then parse `line[:L]`), else error.
- `test_record_too_short` — Short records are errors.
- `test_record_too_long` — Long records with non-whitespace suffix are errors.
- `test_required_fields_empty_are_reported` — Fields with `required: true` that are empty after trimming must be reported as errors.
- `test_eftno_and_bank_code_alphanumeric_constraints` / `test_eftno_with_special_chars` — `eftno` must be non-empty and alphanumeric; special characters cause errors.
- `test_bank_code_must_start_with_digit` / `test_bank_code_starting_with_letter` — `bank_code` must start with a digit; error text must include `must start with a digit` when violated.
- `test_bank_code_no_lowercase_or_special_chars` / `test_bank_code_with_lowercase` — `bank_code` must contain only uppercase letters and digits; lowercase or special characters are rejected.
- `test_account_no_length_validation` / `test_amount_must_be_positive` — `account_no` must be 8..20 digits only; `amount` must parse as decimal, be > 0, and have at most 2 decimals (errors must reference `must be > 0` or `greater than 0`).
- `test_account_forbidden_prefixes` / `test_account_forbidden_first_four_zeros_ones` — Reject `account_no` prefixes `0000`, `0001`, `0010`, `0100`. First 4 digits must not be only `0` and `1` (error should include `First 4 digits` or `0 and 1`).
- `test_account_last_four_cannot_have_zeros` — Core account last 2 digits must not contain `0` (error should include `cannot contain 0`).
- `test_invalid_date_format` — `clearance_date` parsed by schema `format` (verifier uses `%Y-%m-%d`) and invalid dates are errors.
- `test_amount_with_more_than_two_decimals` — Amounts with >2 decimal places are rejected.
- `test_clearing_account_requires_exact_match_not_substring` / `test_clearing_account_substring_match_bug` — `clearing_account` must match one of the allowed clearing accounts exactly after trimming; substring matches are not accepted.
- `test_payee_database_unknown_account` — With `--payees-db`, unknown `account_no` must report an error (message containing `not found in payee database` or `Account`).
- `test_payee_fraud_flag_rejection` — With `--payees-db`, `fraud_flag == 1` must trigger an error mentioning `fraud` or `risk`.
- `test_payee_name_mismatch` / `test_payee_name_case_insensitive_match` — With `--payees-db`, payee name comparison must be case-insensitive after trimming and collapsing whitespace (use Unicode `casefold()`); mismatches must report `name mismatch` or `payee name`.
- `test_valid_active_customer_account` — With `--payees-db`, a known good account and matching payee name must pass.
- `test_unicode_in_payee_name` — Unicode in payee names must be handled correctly in parsing and in the JSON report.
- `test_multiple_errors_in_one_record` — Multiple independent errors for the same record must all be present in `errors`, each prefixed `Line N`.
- `test_special_characters_in_address` — Address fields may contain special characters; they must not crash the validator.
- `test_duplicate_different_filename_bug` — Duplicate detection must be filename-independent (same canonical content under any filename is detected).
- `test_retention_days_ignored_bug` — Regression: `--retention-days <= 0` disables duplicate detection: report `duplicate: false` and do not insert DB rows.
- `test_very_large_file` — Performance: handle >=1000 records efficiently (no quadratic behavior).

Implementation reminders (verifier-aligned):

- Always compute `file_hash` using the canonicalization rules in this document and include it in the reported JSON even on failures.
- Stdout must contain exactly one JSON object (no extra logs). Send diagnostics to stderr only.
- Exit-code rules (authoritative): if `duplicate == true` → non-zero; else if `n_errors > 0` → non-zero; else `0`.

