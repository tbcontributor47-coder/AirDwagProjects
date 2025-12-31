# COBOL: Real Estate Site Data Validator and Merger

Your task is to fix a legacy COBOL program used to validate and consolidate real estate site records from multiple regional offices.

## Current State
The program `merge.cbl` is designed to process 5 regional data files:
1. `data/site1.dat`
2. `data/site2.dat`
3. `data/site3.dat`
4. `data/site4.dat`
5. `data/site5.dat`

It is supposed to validate each file's integrity and produce a single master file `all_sites.dat` containing only validated records.

## The Problem
The current implementation is **buggy**. It fails to:
- Process the new Real Estate site data format (Header, Detail, Trailer).
- Validate multiple input files (`data/site1.dat` through `data/site5.dat`).
- Check that the header date matches today's date.
- Verify trailer totals for site values and agreement statuses.
- Merge all valid records into a single consolidated file `all_sites.dat`.

## Input File Format (Real Estate Sites)
Each input file is `LINE SEQUENTIAL`.

### Header Record
- **Date**: YYYYMMDD (Positions 1-8). Must be today's date.
- **Pattern**: "HHHHHHHHHH" (Positions 9-18).

### Detail Record (Length: 152 chars)
- **Owner Name**: PIC X(20) (Pos 1-20)
- **Account Name**: PIC X(20) (Pos 21-40)
- **Site No**: PIC 9(5) (Pos 41-45)
- **Site Location**: PIC X(30) (Pos 46-75)
- **Site Details**: PIC X(50) (Pos 76-125)
- **Agreement Completed**: PIC X (Pos 126, 'Y' or 'N')
- **Phone No**: PIC X(15) (Pos 127-141)
- **Site Value**: PIC 9(9)V99 (Pos 142-152)

### Trailer Record
- **Total Records**: PIC 9(5) (Pos 1-5)
- **Total Value**: PIC 9(9)V99 (Pos 6-16)
- **Total Completed Value**: PIC 9(9)V99 (Pos 17-27, sum of 'Y' records)
- **Total Pending Value**: PIC 9(9)V99 (Pos 28-38, sum of 'N' records)
- **Pattern**: "TTTTTTTTTT" (Pos 39-48).

## Requirements
1.  **Date Validation**: The header date must match the system date (e.g., 20260101).
2.  **Trailer Validation**: After reading all details in a file:
    - Detail count must match `Total Records`.
    - Sum of all values must match `Total Value`.
    - Sum of 'Y' values must match `Total Completed Value`.
    - Sum of 'N' values must match `Total Pending Value`.
3.  **File Aggregation**: If all 5 files pass validation, copy all detail records into `all_sites.dat`. If any validation fails (in any file), the program must **not** produce the `all_sites.dat` file (or must delete/empty it) and must exit with status 1 after displaying a descriptive error message.
    - For header date or pattern issues: Display `INVALID HEADER`.
    - For trailer count or sum mismatches: Display `TRAILER MISMATCH`.
4.  **Formatting**: Stick to Area A/B rules.

## Task
Modify `/app/merge.cbl` to implement the Real Estate validator and merger.
