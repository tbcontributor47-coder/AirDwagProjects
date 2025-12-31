# COBOL: Insurance Premium Batch Validator

## Task Overview
Standardize and validate a batch of Insurance Premium records using COBOL. The program must read `insurance.dat`, perform multi-layered fiscal and integrity checks, and output a validation result.

## Record Formats (Fixed Width)

### Header Record (Type 'H')
| Field | Position | Length | Format |
|-------|----------|--------|--------|
| Type | 1 | 1 | 'H' |
| Date | 2-9 | 8 | YYYYMMDD |
| Batch Name | 10-19 | 10 | Alphanumeric |
| State Code | 20-21 | 2 | Alphanumeric |

### Policy Record (Type 'P')
| Field | Position | Length | Format |
|-------|----------|--------|--------|
| Type | 1 | 1 | 'P' |
| Policy No | 2-11 | 10 | 9(10) |
| Holder Name| 12-31 | 20 | Alphanumeric |
| Base Premium| 32-39 | 8 | 9(6)V99 |
| Tax Amount | 40-47 | 8 | 9(6)V99 |
| Total Due | 48-55 | 8 | 9(6)V99 |
| Risk Cat | 56 | 1 | '1', '2', or '3' |
| Country | 57-58 | 2 | Alphanumeric |
| Account No | 59-68 | 10 | 9(10) |
| Age | 69-71 | 3 | 9(3) |

### Trailer Record (Type 'T')
| Field | Position | Length | Format |
|-------|----------|--------|--------|
| Type | 1 | 1 | 'T' |
| Policy Count| 2-6 | 5 | 9(5) |
| Total Prem | 7-18 | 12 | 9(10)V99 |
| Total Tax | 19-30 | 12 | 9(10)V99 |
| Total Due | 31-42 | 12 | 9(10)V99 |

## Validation Rules

1.  **Date Validation**: The Header date must match the current system date.
2.  **Policy Checksum**: The sum of the first 9 digits of the `Policy No` modulo 10 must equal the 10th digit.
3.  **Fiscal Integrity**: `Total Due` must equal `Base Premium + Tax Amount` for every record.
4.  **Tax Calculation**: Tax is calculated based on `Risk Cat`:
    *   Risk '3': 10% of Base Premium.
    *   Risk '2': 5% of Base Premium.
    *   Risk '1': 0% of Base Premium.
    *   Rounding: Use half-up rounding (e.g., .005 becomes .01).
5.  **Premium Cap**: `Base Premium` must not exceed **$100,000.00**.
6.  **Geo-Restriction**: Transactions from countries **'RU'** or **'KP'** are prohibited.
7.  **Account Validation**: `Account No` must be exactly 10 digits and **must start with '9'**.
8.  **Age Constraint**: `Age` must be between **18** and **120** inclusive.
9.  **Batch Totals**: The Trailer must exactly match the count and the sum of all policy components.

## Requirements
- Output exactly one of the following error codes to `STDOUT` if validation fails (in priority order):
    - `DATE_ERR`
    - `FORMAT_ERR` (Account No starts with non-9)
    - `BANNED_ERR` (Country is RU or KP)
    - `AGE_ERR` (Age < 18 or > 120)
    - `COUNT_ERR` (Trailer count mismatch)
    - `FISCAL_ERR` (Policy total due mismatch or Premium > 100k)
    - `TAX_ERR` (Tax calculation mismatch)
    - `CHECKSUM_ERR` (Policy number checksum failure)
    - `BATCH_SUM_ERR` (Trailer sum mismatch)
- If all checks pass, output `VALID`.
- Return exit code `0` on success, and `1` on any validation error.
- Adhere to strict COBOL fixed-format rules (Indicators in Col 7, Area A/B alignment).

## Task
Modify `/app/validate.cbl` to implement the Insurance Validator based on the rules effectively.
The final program must be named `validate.cbl` and reside in the `/app` directory.
