# COBOL Batch Processing: The 3-File Merge Challenge

Your task is to fix a legacy COBOL program that merges compensation data from three different sources.

## Current State
The program `merge.cbl` attempts to read three sequential files:
1. `data/salary.dat` (Base salary)
2. `data/comm.dat` (Commissions)
3. `data/bonus.dat` (Bonuses)

It is supposed to produce a single report `report.txt` containing the total compensation for **every unique employee** found in **any** of the files.

## The Problem
The current implementation is **buggy**. It assumes that:
- Every employee ID exists in all three files.
- The files are perfectly synchronized.

In reality, an employee might have a salary but no bonus, or a commission but be missing from the salary file (e.g., a contractor). 

## Requirements
1. **Full Outer Join**: You must include every `EMP-ID` that appears in at least one of the three input files.
2. **Missing Data**: If an employee is missing from a specific file, treat their amount for that category as **0.00**.
3. **Sorting**: The input files are already sorted by `EMP-ID` (ascending). Your output MUST also be sorted by `EMP-ID` (ascending).
4. **Output Format**: Each line in `report.txt` must follow this exact format:
   `ID | TS:TOTAL`
   - `ID`: 5-digit employee ID (e.g., `00001`)
   - `TOTAL`: Total compensation (Salary + Commission + Bonus) formatted as `9999999.99`
   - Example: `00010 | TS:0005500.50`

## Technical Details
- **Compiler**: GnuCOBOL (cobc)
- **Organization**: All input files are `LINE SEQUENTIAL`.
- **Fields**:
  - `EMP-ID`: 5 digits (`PIC 9(5)`)
  - `AMOUNT`: 5 integer digits, 3 decimal digits (`PIC 9(5)V999`)

## Task
Modify `/app/merge.cbl` so that it correctly handles the "Balance Line" logic required to merge three sorted files with missing records.

Ensure your code is strictly compliant with COBOL formatting rules (Area A starts at column 8, Area B at column 12).
