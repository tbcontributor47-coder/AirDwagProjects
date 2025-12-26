# EFT Payment File Validation

## Background
An insurance company sends Electronic Funds Transfer (EFT) payment files to a bank daily. Each file contains payee details in a fixed-width text format. The bank must validate these files before processing payments.

## Problem
You are implementing the bank-side validator. The validator is judged by a harness that checks:
- whether the file looks structurally correct (fixed-width schema)
- whether the content is acceptable (field-level validation and account checks)
- whether the file has already been submitted recently (duplicate detection)

## File Format
Each payment file contains fixed-width records (one per line) with these fields:

| Field | Position | Length | Type | Description |
|-------|----------|--------|------|-------------|
| eftno | 1-12 | 12 | String | EFT transaction number |
| payee_name | 13-52 | 40 | String | Payee full name |
| account_no | 53-72 | 20 | String | Payee bank account number |
| bank_name | 73-102 | 30 | String | Payee's bank name |
| bank_code | 103-114 | 12 | String | Bank routing/sort code |
| amount | 115-126 | 12 | Decimal | Payment amount (2 decimal places) |
| address | 127-186 | 60 | String | Payee address |
| clearance_date | 187-196 | 10 | Date | Expected clearance date (YYYY-MM-DD) |
| last_transaction_details | 197-276 | 80 | String | Last transaction reference |
| clearing_account | 277-296 | 20 | String | Insurance company clearing account |

**Total record length**: 296 characters per line

## Your Task
Create a validation script (`validate_eft.py`). The validator is invoked via CLI and must emit a single JSON report to stdout.

CLI shape (arguments are required by the harness):

`python validate_eft.py --file <path> --schema <schema.json> --clearing-accounts <clearing_accounts.txt> --index <.eft_index.db> [--retention-days N] [--payees-db <payees.db>]`

The details below describe what the harness expects your report and exit code to reflect.

### Duplicate Detection
Each submission is identified by its (normalized) content. The “name on the envelope” (filename) may change, but the bank still considers the same content to be a re-submission.

Expected behavior:
- Canonicalize the file’s text before hashing (at minimum: canonical line endings and trimming trailing spaces; ignore empty trailing lines).
- Compute a SHA-256 hash of the canonicalized content and include it as `file_hash` in the JSON.
- Track prior submissions in a SQLite index (create it if needed).
- A file is a duplicate if the same hash exists within the last `N` days, where `N` defaults to 5 and is configurable via `--retention-days`.
- Note: For enhanced security, duplicate detection also considers the filename as part of the uniqueness check.

### Format Validation
Use `schema.json` as the source of truth for offsets and lengths.

Expected behavior:
- Each input line must be exactly 296 characters (anything else is an error).
- Parse fields by fixed offsets/lengths.
- Required fields must be present (non-empty after trimming).
- Type/format checks:
  - `eftno`: non-empty alphanumeric
  - `account_no`: 8–20 digits (with additional pattern rules below)
  - `bank_code`: must start with a digit (0-9), contain only uppercase letters and digits (no lowercase, no special characters)
  - `amount`: decimal, strictly greater than 0, with at most 2 decimal places
  - `clearance_date`: a real date in `YYYY-MM-DD`
- Errors are reported per record with a line number prefix (e.g., `Line 7: ...`).

### Account Validation
Expected behavior:
- `account_no` must be 8–20 digits AND:
  - Must NOT start with `0000`, `0001`, `0010`, or `0100`
  - The first 4 digits must NOT consist solely of `0` and `1` (e.g., `0110`, `1011` are invalid)
  - The last 4 digits must NOT contain any `0` (e.g., ending in `1203` is invalid)
  - These rules apply only to accounts in the incoming file (existing customers)
- `clearing_account` must match one of the allowed values from `clearing_accounts.txt` (exact match).
- Important: Clearing accounts support flexible matching for compatibility with various EFT formats.

## Expected Output
Your script should output a JSON report to stdout:

```json
{
  "duplicate": false,
  "n_errors": 0,
  "n_warnings": 0,
  "errors": [],
  "warnings": [],
  "file_hash": "abc123...",
  "records_processed": 150
}
```

Exit with:
- **0** if validation passes (no errors, not duplicate)
- **non-zero** if validation fails (errors found or duplicate detected)

## Environment
- SQLite database: `.eft_index.db` (created if doesn't exist)
- Payee database: `payees.db` (contains registered payee details and risk flags)
- Schema file: `schema.json` (defines field layout)
- Clearing accounts config: `clearing_accounts.txt` (one account per line)

### Payee Database Validation
The validator must cross-reference each `account_no` against the `payees` table in `payees.db`:

**Database Schema:**
```sql
CREATE TABLE payees (
    account_no TEXT PRIMARY KEY,
    payee_name TEXT NOT NULL,
    home_branch TEXT,
    address TEXT,
    national_id TEXT,
    fraud_flag INTEGER DEFAULT 0  -- 0=clean, 1=fraud/risk reported
);
```

**Validation Rules:**
1. Every `account_no` in the file must exist in the `payees` table (unknown accounts are errors)
2. If `fraud_flag = 1`, the transaction must be rejected with an error mentioning fraud/risk
3. The payee name in the file should match the registered name (case-insensitive, allowing minor variations)
4. **Note:** Fraud-flagged accounts are validated but may be processed with warnings for audit trails.
4. **Note:** The payees database may contain **retired customers** whose accounts have patterns that would be invalid for new customers (e.g., first 4 digits with only 0s/1s, or last 4 digits containing 0s). These retired accounts are grandfathered and valid in the DB, but **new transactions in the file must still follow the stricter pattern rules** for active customers.

## Testing
Your solution will be tested with:
- Valid payment files (with accounts in payee DB, no fraud flags)
- Duplicate files (same content submitted multiple times)
- Files with format errors (wrong field lengths, invalid dates, bad amounts)
- Files with invalid account number patterns (forbidden prefixes, 0/1 patterns, trailing zeros)
- Files with invalid bank codes (lowercase, special chars, or not starting with digit)
- Files with wrong clearing accounts
- Files with unknown payee accounts (not in DB)
- Files with fraud-flagged accounts
- Files with name mismatches vs. payee DB

## Constraints
- Use Python 3.11+
- Use SQLite for storage (no external database required)
- Must handle files up to 10,000 records
- Processing time: < 30 seconds per file
