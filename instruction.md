# EFT File Validation (Fixed-Width Payments)

You are given a CLI program inside the container at:

- `/app/validate_eft.py`

The program is **buggy**. Fix it.

## Intentional Bugs

The program contains the following bugs that must be fixed:

1. **Record length validation**: `parse_record` uses `<=` instead of strict length check - allows short records to pass
2. **Duplicate detection uses filename**: `check_duplicate` includes filename in SQL WHERE clause; should use hash-only
3. **Retention days parameter ignored**: `__init__` hardcodes `retention_days` to 5, ignoring the `--retention-days` parameter
4. **Hash canonicalization incomplete**: `_compute_hash` doesn't strip trailing whitespace per line before hashing
5. **Clearing account substring matching**: Uses substring matching (`in` operator) instead of exact match
6. **Error messages missing line numbers**: Required field errors don't include "Line N:" prefix

## Hints

- Check `parse_record` method around line 87 - record length validation uses `<=` instead of strict check
- Look at `check_duplicate` method - SQL query includes `filename` in WHERE clause (should be hash-only)
- Review `__init__` constructor - `retention_days` parameter is overwritten with hardcoded value 5
- Examine `_compute_hash` - missing per-line `rstrip(" \t")` before hashing
- Check `validate_accounts` method - clearing account uses substring `in` operator instead of exact match
- Review error message formatting in `parse_record` - missing "Line N:" prefix for required field errors

## CLI

The verifier invokes:

```
python /app/validate_eft.py \
  --file <payment_file.txt> \
  --schema <schema.json> \
  --clearing-accounts <clearing_accounts.txt> \
  --index <index.db> \
  [--retention-days N] \
  [--payees-db payees.db]
```

Requirements:

- Do not print a Python traceback.
- Stdout must contain **only** one JSON object (no extra text). Diagnostics may go to stderr.

## Output

Always print exactly one JSON object to stdout with:

- `duplicate`: boolean
- `n_errors`: int
- `n_warnings`: int (use `0`)
- `errors`: list[str]
- `warnings`: list[str] (use `[]`)
- `file_hash`: 64 lowercase hex chars
- `records_processed`: int

Exit code:

- Exit `0` only if `duplicate == false` AND `n_errors == 0`.
- Otherwise exit non-zero.

## Schema

The schema JSON contains:

- `record_length`: integer `L`
- `fields`: list of field descriptors with:
  - `name`, `start` (0-based), `length`, `type` (`string|decimal|date`), `required`
  - optional `format` for dates (verifier schema uses `%Y-%m-%d`)

Field parsing:

- `raw = line[start : start + length]`
- `value = raw.strip()`

## Records and `records_processed`

Read the payment file as UTF-8 text.

- Normalize line endings: treat `\r\n` and bare `\r` as `\n`.
- Split on `\n`.
- Drop only empty trailing lines at the end of the file.

Clarification (explicit examples):

- Only remove empty lines that occur at the *end* of the file after normalizing line endings. Do not drop empty or short lines that occur in the middle of the file — they count as records and must be validated.
- Example: the text `"LINE1\n\nLINE2\n"` becomes three lines `['LINE1', '', 'LINE2']` and `records_processed` is `3`. The trailing final empty line created by a trailing `\n` after the last line is removed only if it results in an empty last element; i.e. `"LINE1\nLINE2\n"` -> `['LINE1','LINE2']` -> `records_processed=2`.

`records_processed = number of remaining lines after removing only trailing empty lines`.

## Record length handling

Let `L = record_length`.

For each record line:

- If `len(line) < L`: add an error.
- If `len(line) == L`: OK.
- If `len(line) > L`: accept only if `line[L:].strip() == ""` (whitespace padding), else error.

## Hashing and duplicate detection

### `file_hash`

Compute `file_hash` as SHA-256 of canonicalized content:

1. Normalize line endings (`\r\n`→`\n`, then `\r`→`\n`).
2. Split into lines on `\n`.
3. For each line, `rstrip(" \t")` (strip trailing spaces/tabs).
4. Remove empty trailing lines.
5. Join lines with `\n` and append a final `\n` if content exists.
6. Hash the resulting UTF-8 bytes with SHA-256 (lowercase hex).

### Duplicate detection

- Duplicate detection is based on `file_hash` only (filename must not be part of the check).
- Retention window is `--retention-days` (default 5).
- If `retention_days <= 0`, duplicate detection is disabled - always report `duplicate: false` and do not insert DB rows.
- Otherwise, use the SQLite index DB at `--index` to detect duplicates within the retention window.
- Store timestamps in ISO-8601 format.
- A file is duplicate if there exists a prior row with the same `file_hash` and timestamp >= (now - retention_days).

## Validation rules

Validate every record and collect all errors.

Error formatting:

- Every error string must include `Line N` (1-based line number prefix).

### Required fields

If a schema field is `required: true` and its trimmed value is empty, add an error with "Line N:" prefix.

### Field checks

- `eftno`: non-empty and alphanumeric (letters/digits only).
- `bank_code`:
  - must start with a digit (`0`-`9`)
  - must contain only uppercase letters and digits (no lowercase, no punctuation)
  - error must include `must start with a digit` when violated
- `account_no`:
  - must be digits only, length 8..20
  - forbidden prefixes: starts with one of `0000`, `0001`, `0010`, `0100`
  - first-4 rule: first 4 digits must not consist solely of `0` and `1` (error should include `First 4 digits` or `0 and 1`)
  - last-4 rule: the last 4 digits must not contain the digit `0` (i.e. none of the last four characters may be `0`). Error messages for violations should include either `Last 4 digits` or `cannot contain 0` and must include the `Line N:` prefix.
- `amount`: 
  - decimal, strictly > 0
  - at most 2 decimal places
  - error should include `must be > 0` or `greater than 0`
- `clearance_date`: parse using schema `format` (verifier uses `%Y-%m-%d`).
- `clearing_account`: must match one allowed clearing account exactly after trimming (no substring match).

## Payees DB (`--payees-db`)

Only when `--payees-db` is provided:

- If `account_no` is not found in the `payees` table, add an error containing `not found in payee database` or `Account`.
- If `fraud_flag == 1`, add an error mentioning `fraud` or `risk`.
- Compare payee names case-insensitively after trimming and collapsing internal whitespace to single space; mismatches must include `name mismatch` or `payee name`.

The `payees` table schema:

```sql
CREATE TABLE payees (
  account_no TEXT PRIMARY KEY,
  payee_name TEXT NOT NULL,
  fraud_flag INTEGER DEFAULT 0
);
```

## SQLite Index DB

The validator stores submissions in a SQLite DB. Create the DB and table if needed:

```sql
CREATE TABLE IF NOT EXISTS file_index (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_hash TEXT NOT NULL,
  filename TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  record_count INTEGER
);
```

On first-seen (non-duplicate) files, insert a row with `file_hash`, `filename`, `timestamp` (ISO-8601), and `record_count` (equal to `records_processed`).

## Verifier tests (required coverage)

The verifier uses `pytest` and invokes the CLI as an external process. The following tests verify bug fixes:

### Bug 1: Record Length Validation
- `test_exact_record_length_enforced` - Verifies strict length checking (short and long records rejected)

### Bug 2: Duplicate Detection (Filename)
- `test_duplicate_detection_across_filenames` - Verifies hash-only duplicate detection (filename-independent)

### Bug 3: Retention Days Parameter
- `test_retention_days_ignored_bug` - Verifies `--retention-days` parameter is honored
- `test_retention_days_flag_affects_duplicate_detection` - Verifies retention window behavior

### Bug 4: Hash Canonicalization
- `test_hash_normalization_crlf_and_trailing_spaces` - Verifies trailing whitespace stripping
- `test_crlf_line_endings_with_trailing_spaces` - Verifies canonicalization rules

### Bug 5: Clearing Account Matching
- `test_clearing_account_substring_match_bug` - Verifies exact matching (no substring)

### Bug 6: Error Message Format
- `test_errors_include_line_numbers_and_multiple_issues` - Verifies "Line N:" prefix in errors
- `test_required_fields_empty_are_reported` - Verifies required field errors include line numbers

### Complete test list

All tests must pass:

- `test_valid_file_validation` — Valid input produces correct JSON output and exits 0
- `test_duplicate_detection` — Duplicate detection works for same file submitted twice
- `test_duplicate_detection_across_filenames` — Same content under different filename detected as duplicate
- `test_invalid_file_validation` — Invalid input exits non-zero with errors
- `test_errors_include_line_numbers_and_multiple_issues` — Errors include "Line N:" prefix
- `test_retention_window` — Retention window correctly filters old entries
- `test_retention_days_flag_affects_duplicate_detection` — `--retention-days` parameter affects behavior
- `test_retention_days_ignored_bug` — `--retention-days 0` disables duplicate detection
- `test_hash_normalization_crlf_and_trailing_spaces` — Hash canonicalization handles CRLF and trailing spaces
- `test_randomized_record_not_hardcoded` — Implementation is schema-driven (anti-cheating)
- `test_exact_record_length_enforced` — Record length strictly enforced (short/long rejected)
- `test_exact_length_with_padding` — Records with whitespace padding beyond length are accepted
- `test_required_fields_empty_are_reported` — Required empty fields report errors with line numbers
- `test_account_forbidden_prefixes` — Account numbers with forbidden prefixes rejected
- `test_account_first_four_only_zeros_and_ones` — First 4 digits validation works
- `test_account_last_four_cannot_have_zeros` — Last 4 digits validation works
- `test_bank_code_must_start_with_digit` — Bank code must start with digit
- `test_bank_code_no_lowercase_or_special_chars` — Bank code format validation
- `test_payee_database_unknown_account` — Unknown accounts in payees DB report errors
- `test_payee_fraud_flag_rejection` — Fraud-flagged accounts rejected
- `test_payee_name_mismatch` — Payee name mismatches detected
- `test_valid_active_customer_account` — Valid accounts with matching names pass
- `test_account_no_length_validation` — Account number length validation (8-20 digits)
- `test_amount_must_be_positive` — Amount must be > 0
- `test_invalid_date_format` — Invalid dates rejected
- `test_amount_with_more_than_two_decimals` — Amount decimal places validation
- `test_clearing_account_substring_match_bug` — Clearing account exact match (no substring)
- `test_payee_name_case_insensitive_match` — Payee name case-insensitive matching
- `test_multiple_errors_in_one_record` — Multiple errors per record all reported
- `test_very_large_file` — Performance: handles 1000+ records efficiently
- `test_crlf_line_endings_with_trailing_spaces` — Line ending and whitespace normalization
- `test_empty_lines_at_end` — Trailing empty lines ignored
- `test_special_characters_in_address` — Special characters in optional fields handled
- `test_solution_runtime_within_limit` — Performance: solution completes within time limit

## Constraints

- Do not modify the tests.
- Do not change the container environment.
- Only fix the logic in `/app/validate_eft.py`.

