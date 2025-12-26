# EFT Payment File Validation Task

## Overview
This task validates Electronic Funds Transfer (EFT) payment files from an insurance company to a bank. The validator performs three key checks:

1. **Duplicate Detection** - Identifies files submitted within the last 5 days
2. **Format Validation** - Ensures fixed-width records conform to schema
3. **Account Validation** - Verifies payee and clearing account numbers

## Task Difficulty
**Medium** - Requires handling multiple validation layers, SQLite database operations, fixed-width file parsing, and configurable business rules.

## File Format
Fixed-width text format (296 characters per record):

| Field | Position | Length | Type |
|-------|----------|--------|------|
| eftno | 1-12 | 12 | String |
| payee_name | 13-52 | 40 | String |
| account_no | 53-72 | 20 | String |
| bank_name | 73-102 | 30 | String |
| bank_code | 103-114 | 12 | String |
| amount | 115-126 | 12 | Decimal |
| address | 127-186 | 60 | String |
| clearance_date | 187-196 | 10 | Date |
| last_transaction_details | 197-276 | 80 | String |
| clearing_account | 277-296 | 20 | String |

## Quick Start

### Local Testing
```bash
# Run unit tests
python3 -m pytest tests/test_validator.py -v

# Validate a sample file
python3 solution/validate_eft.py --file tests/data/valid_payment.txt

# Validate with custom retention
python3 solution/validate_eft.py --file tests/data/valid_payment.txt --retention-days 7
```

### Docker Testing
```bash
# Build the container
docker build -t eft-validator -f environment/Dockerfile .

# Run tests in container
docker run eft-validator

# Validate a file in container
docker run -v $(pwd)/tests/data:/data eft-validator \
  python3 validate_eft.py --file /data/valid_payment.txt
```

## Solution Implementation

The `validate_eft.py` script must:

1. **Initialize validator with:**
   - Schema file (`schema.json`)
   - SQLite database (`.eft_index.db`)
   - Clearing accounts list (`clearing_accounts.txt`)
   - Retention window (default 5 days)

2. **For duplicate detection:**
   - Normalize file content (trim spaces, normalize line endings)
   - Compute SHA-256 hash
   - Query database for matching hash within retention window
   - Record new files in index

3. **For format validation:**
   - Parse each record using fixed-width offsets
   - Validate field types (string, decimal, date)
   - Check required fields are non-empty
   - Validate patterns (e.g., account_no must be 8-20 digits)
   - Report errors with line numbers

4. **For account validation:**
   - Verify account_no matches pattern `^\d{8,20}$`
   - Verify clearing_account exists in allowed list
   - Report validation failures

5. **Output JSON report:**
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

6. **Exit codes:**
   - `0` - Validation passed
   - `1` - Validation failed (errors or duplicate)

## Test Cases

### Valid File (`tests/data/valid_payment.txt`)
- 3 records with proper formatting
- All accounts valid
- Should process successfully

### Duplicate File (`tests/data/duplicate_payment.txt`)
- 2 valid records
- Will be flagged as duplicate on second submission

### Invalid File (`tests/data/invalid_payment.txt`)
- Record too short (line 1)
- Invalid amount format (line 2)
- Bad date format (line 3)
- Account number contains letters (line 4)
- Wrong clearing account (line 5)

## Database Schema

SQLite database `.eft_index.db` with table:

```sql
CREATE TABLE file_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    filename TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    record_count INTEGER,
    UNIQUE(file_hash, timestamp)
)
```

## Configuration Files

### `schema.json`
Defines field layout with start positions, lengths, types, and validation rules.

### `clearing_accounts.txt`
List of valid clearing account numbers (one per line):
```
12345678901234567890
98765432109876543210
11111111112222222222
```

## CI/Jenkins Integration

The task includes a Jenkinsfile for automated testing. The pipeline:
1. Runs oracle solution against test files
2. Validates format and duplicate detection
3. Runs pytest suite
4. Publishes results

## Development Notes

- Python 3.11+ required
- Dependencies: pytest (for testing only)
- SQLite built-in (no external database)
- Handles up to 10,000 records per file
- Processing time target: < 30 seconds per file

## Scoring

The verifier evaluates:
- Duplicate detection accuracy (25%)
- Format validation completeness (40%)
- Account validation correctness (25%)
- Error reporting quality (10%)

## Author
Manoj Kumar Selvaraj
