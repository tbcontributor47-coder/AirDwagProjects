# EFT Payment File Validation

## Background
An insurance company sends Electronic Funds Transfer (EFT) payment files to a bank daily. Each file contains payee details in a fixed-width (mainframe-style) text format. The bank must validate these files before processing payments.

## Problem
The bank needs an automated validation system that:
1. **Detects duplicate files** submitted within the last 5 days
2. **Validates file format** against a fixed-width schema
3. **Validates account numbers** (payee and clearing accounts)

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
Create a validation script (`validate_eft.py`) that:

### 1. Duplicate Detection
- Normalize the file content (trim trailing spaces, canonical line endings)
- Compute SHA-256 hash of normalized content
- Store file metadata (hash, filename, timestamp) in SQLite database
- Flag files as duplicates if the same hash exists within the last 5 days
- Configurable retention window via `--retention-days` parameter

### 2. Format Validation
- Parse each record using the fixed-width schema
- Validate required fields are non-empty
- Check data types and formats:
  - `eftno`: non-empty alphanumeric
  - `account_no`: 8-20 digits
  - `bank_code`: alphanumeric
  - `amount`: valid decimal > 0, max 2 decimal places
  - `clearance_date`: valid date in YYYY-MM-DD format
- Report per-record errors with line numbers

### 3. Account Validation
- `account_no`: must be 8-20 digits
- `clearing_account`: must match one of the allowed clearing accounts in the database or config file

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
- **1** if validation fails (errors found or duplicate detected)

## Environment
- SQLite database: `.eft_index.db` (created if doesn't exist)
- Schema file: `schema.json` (defines field layout)
- Clearing accounts config: `clearing_accounts.txt` (one account per line)

## Testing
Your solution will be tested with:
- Valid payment files
- Duplicate files (same content submitted multiple times)
- Files with format errors (wrong field lengths, invalid dates, bad amounts)
- Files with invalid account numbers
- Files with wrong clearing accounts

## Constraints
- Use Python 3.11+
- Use SQLite for storage (no external database required)
- Must handle files up to 10,000 records
- Processing time: < 30 seconds per file
