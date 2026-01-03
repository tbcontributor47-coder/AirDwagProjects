# COBOL Banking Transaction Reconciliation Engine

## Background
You are a legacy systems engineer working for a major retail bank. The bank uses a COBOL-based batch processing system to reconcile daily transactions. Recently, the reconciliation engine has been producing incorrect balances and failing to flag high-value transactions accurately.

## Problem Statement
The current COBOL program `reconcile.cbl` is buggy. It incorrectly calculates the net balance of batches, fails to validate trailers correctly, and contains a memory-safety bug (array overflow) when processing large numbers of transactions. Additionally, it lacks a mandatory IBAN-style checksum validation for account IDs.

## Data Format
The system processes a fixed-width file (`input.dat`) with the following record types:

### Header Record (Type 01)
- `RE-TYPE` (01-02): Always "01"
- `RE-BATCH-ID` (03-12): Batch identifier
- `RE-DATE` (13-20): Date (YYYYMMDD)
- `FILLER` (21-100)

### Transaction Record (Type 02)
- `RE-TYPE` (01-02): Always "02"
- `RE-ACC-ID` (03-12): Account ID (Must be 10 numeric digits)
- `RE-AMOUNT` (13-27): Amount (13 digits, 2 decimals implied, e.g., 000000000123456 = 1234.56)
- `RE-DC-FLAG` (28-28): 'D' for Debit, 'C' for Credit
- `RE-REF` (29-48): Transaction reference
- `FILLER` (49-100)

### Trailer Record (Type 03)
- `RE-TYPE` (01-02): Always "03"
- `RE-COUNT` (03-07): Total count of Type 02 records
- `RE-NET-BALANCE` (08-23): Net Balance (Credits - Debits). 15 digits total (13 integer, 2 decimal), sign is leading separate.
- `FILLER` (24-100)

## Mandatory Output Contract

**CRITICAL: All output files must adhere to the exact format specified below. These are not examples; they are strict machine-parsable requirements. Any deviation in line count, line length, or label text will result in total failure.**

### Balanced Report (balanced_report.txt)
If the batch satisfies all integrity checks, the report must contain **exactly 3 lines**, each separated by a system line break (`\n` or `\r\n`). Each line must be exactly **100 characters** wide (including the labels, padded with trailing spaces).

1. `BALANCED REPORT SUMMARY`
2. `TOTAL COUNT: NNNNN` (where `NNNNN` is a 5-digit zero-padded count of valid transactions)
3. `TOTAL NET: SNNNNNNNNNNNNNNN` (where `S` is the sign `+` or `-`, followed by 15 digits including 2 implied decimals)

If the batch is rejected (due to trailer mismatch), the report must contain **exactly 1 line** of 100 characters (with no trailing newline required for the final line, but allowed):
`BATCH REJECTED`

### High-Value Report (high_value.dat)
- **STRICT REQUIREMENT**: Every line must be exactly 100 characters long.
- Contains the original Type 02 record (the full 100-character line) for every valid transaction where the amount is strictly greater than **10,000.00**.

### Anomaly Log (anomalies.dat)
- **STRICT REQUIREMENT**: Every line must be exactly 100 characters long.
- Contains the original Type 02 record (the full 100-character line) for every transaction that failed the Modulo 97 checksum.

## Task
Fix the `reconcile.cbl` program located in `/app/environment/app/` to correctly implement the following business logic:


1.  **Transaction Processing**:
    -   Parse Type 02 records.
    -   Validate the Account ID using Modulo 97 (Valid if `ID mod 97 = 1`).
    -   Calculate the Net Balance as `Total Credits - Total Debits`.
    -   Support up to **1,000** transactions in a single batch without memory overflow.
2.  **Batch Integrity**:
    -   Verify that the total count of Type 02 records (valid and invalid) matches `RE-COUNT` in the Type 03 trailer.
    -   Verify that the calculated Net Balance matches `RE-NET-BALANCE` in the Type 03 trailer.
    -   If either check fails, reject the entire batch by writing `BATCH REJECTED` to the report.

## Success Criteria
The task is successful if the `reconcile.cbl` is fixed such that:
- It produces a `balanced_report.txt` with the correct final statistics following the **strict 3-line schema**.
- It correctly identifies and writes transactions > 10,000.00 to `high_value.dat`.
- It rejects batches with incorrect trailers by writing `BATCH REJECTED` to the report.
- It identifies invalid Account IDs (checksum fail) and logs them to `anomalies.dat`.
- The program compiles and runs without memory errors for batches of up to 1,000 transactions.

## Constraints
- Do NOT change the input file format.
- Maintain the fixed-width output format for reports.
- Use only standard COBOL-85/2002 features compatible with GnuCOBOL.

## Hints
1. COBOL arithmetic precision matters—be careful with intermediate results.
2. The Modulo 97 check can be implemented by treating the Account ID string as a large numeric field.
3. Check the `OCCURS` clause size in the working storage.
4. To ensure exact 100-character line widths for reports, consider using `ORGANIZATION IS SEQUENTIAL` instead of `LINE SEQUENTIAL` if your compiler strips trailing spaces on write.
