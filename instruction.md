# EFT File Validation (Fixed-Width Payments)

You are given a CLI program at `/app/validate_eft.py` that validates EFT payment files. The program is currently buggy and does not correctly implement all required validation rules.

## Your Task

Fix `/app/validate_eft.py` to correctly validate EFT payment files according to the requirements specified below. The implementation must pass all verifier tests.

## CLI Usage

The program is invoked as:

```
python /app/validate_eft.py \
  --file <payment_file.txt> \
  --schema <schema.json> \
  --clearing-accounts <clearing_accounts.txt> \
  --index <index.db> \
  [--retention-days N] \
  [--payees-db payees.db]
```

## Output Requirements

Print exactly one JSON object to stdout with these fields:

- `duplicate`: boolean indicating if this file has been seen before
- `n_errors`: integer count of validation errors
- `n_warnings`: integer (must be `0`)
- `errors`: list of error message strings
- `warnings`: list (must be `[]`)
- `file_hash`: SHA-256 hash as 64 lowercase hex characters
- `records_processed`: integer count of records processed

Exit code: `0` only if `duplicate == false` AND `n_errors == 0`. Otherwise exit non-zero.

**Important:** Do not print Python tracebacks. Stdout must contain only the JSON object. Diagnostics may go to stderr.

## File Processing

Read the payment file as UTF-8 text. Normalize line endings (treat `\r\n` and bare `\r` as `\n`), split on `\n`, and remove only empty trailing lines at the end of the file. The count of remaining lines equals `records_processed`.

## Record Length Validation

Each record line must match the exact length specified in the schema (`record_length`). Short lines are invalid. Lines longer than the specified length are only valid if the extra characters are all whitespace (trailing whitespace padding is allowed).

## Schema and Field Parsing

The schema JSON defines:
- `record_length`: integer length each record must match
- `fields`: list of field descriptors with `name`, `start` (0-based), `length`, `type` (`string|decimal|date`), `required`, and optional `format` (for dates)

Extract each field using `raw = line[start : start + length]` and `value = raw.strip()`.

## Validation Rules

All validation errors must include `Line N:` prefix where N is the 1-based line number.

### Required Fields

Fields marked `required: true` in the schema must have a non-empty value after trimming.

### Field-Specific Validation

- `eftno`: Must be non-empty and contain only alphanumeric characters (letters and digits)

- `bank_code`: 
  - Must start with a digit (`0`-`9`)
  - Must contain only uppercase letters and digits (no lowercase, no punctuation)
  - Error messages must mention `must start with a digit` when this rule is violated

- `account_no`: 
  - Must be digits only, length 8-20 characters
  - For validation purposes, use only the leftmost 8 digits (call this `acct8 = account_no[:8]`)
  - The first 4 digits of `acct8` cannot be any of: `0000`, `0001`, `0010`, `0100` (error must mention the offending prefix)
  - The first 4 digits of `acct8` cannot consist solely of `0` and `1` (error must include `First 4 digits` or `0 and 1`)
  - The last 4 digits of `acct8` cannot contain the digit `0` (error must include `Last 4 digits` or `cannot contain 0`)

- `amount`: 
  - Must be a decimal number strictly greater than 0
  - Must have at most 2 decimal places
  - Error messages must include `must be > 0` or `greater than 0`

- `clearance_date`: Must be a valid date matching the schema `format` (verifier uses `%Y-%m-%d`)

- `clearing_account`: After trimming, must exactly match one of the allowed clearing accounts from the `--clearing-accounts` file. Substring matching is not acceptable.

## Payees Database

When `--payees-db` is provided:

- If `account_no` is not found in the `payees` table, add an error containing `not found in payee database` or `Account`
- If the account's `fraud_flag == 1`, add an error mentioning `fraud` or `risk`
- Compare payee names case-insensitively after trimming and collapsing internal whitespace to a single space. Mismatches must include `name mismatch` or `payee name`

The `payees` table schema:
```sql
CREATE TABLE payees (
  account_no TEXT PRIMARY KEY,
  payee_name TEXT NOT NULL,
  fraud_flag INTEGER DEFAULT 0
);
```

## File Hashing and Duplicate Detection

Compute `file_hash` as SHA-256 of the canonicalized file content. The canonicalization process must normalize line endings, strip trailing whitespace from each line, remove trailing empty lines, and join lines with `\n` (appending a final `\n` if content exists).

Duplicate detection uses `file_hash` only (filename is not part of the check). The retention window is determined by `--retention-days` (default: 5). 

**Critical requirement:** When `--retention-days` is 0 or negative, duplicate detection is disabled (always report `duplicate: false`) and **no database rows must be inserted** into the index database.

When retention_days > 0, use the SQLite index database at `--index` to detect duplicates. A file is a duplicate if there exists a prior row with the same `file_hash` and a timestamp >= (current time - retention_days). Store timestamps in ISO-8601 format.

The index database table schema:
```sql
CREATE TABLE IF NOT EXISTS file_index (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_hash TEXT NOT NULL,
  filename TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  record_count INTEGER
);
```

**Important:** Only insert rows into `file_index` when the file is not a duplicate AND `retention_days > 0`. When inserting, include `file_hash`, `filename`, `timestamp` (ISO-8601), and `record_count` (equal to `records_processed`).

## Constraints

- Only modify `/app/validate_eft.py`
- Do not modify tests or the container environment
- All validation errors must include the line number prefix `Line N:`

## Intentional Bugs

The current implementation has several bugs. The code does not correctly:

1. Enforce strict record length validation (allows records that don't meet length requirements)
2. Perform duplicate detection using file hash only (incorrectly uses filename in the check)
3. Honor the `--retention-days` parameter (uses a hardcoded value instead)
4. Canonicalize file content correctly for hashing (missing whitespace normalization steps)
5. Match clearing accounts exactly (uses substring matching instead of exact match)
6. Format error messages correctly (missing required line number prefixes)

## Verifier Tests

The verifier uses `pytest` and executes the CLI as an external process. All tests must pass, including tests for duplicate detection, retention window behavior, hash normalization, validation rules, error formatting, and edge cases.
