# EFT File Validation (Fixed-Width Payments)

You are given a small CLI program inside the container at:

- `/app/validate_eft.py`

The program is **buggy**. Fix it.

This document is the full runtime contract. Implement exactly what is specified.

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

## Validation rules

Validation is performed per record line. All errors for all records must be collected.

Error message formatting requirements (verifier-checked):

- Every error string must include the 1-based line number prefix `Line N`.
- Some tests look for these substrings in at least one error when relevant:
  - `First 4 digits`
  - `Last 4 digits`
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
  - last 4 digits must not contain `0` (error text must include `Last 4 digits` or `cannot contain 0`)

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
