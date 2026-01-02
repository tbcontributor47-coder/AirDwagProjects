# COBOL to Java Migration: Insurance Validator

## Task Overview
1.  **Fix Bugs in COBOL**: A legacy COBOL program (`validate.cbl`) validates insurance premium batch files. It contains several critical bugs (logic and validation gaps). You must find and fix them to make the COBOL tests pass.
2.  **Migrate to Java**: Port the fixed logic to a modern Java 17 application. The Java version must function identically to the fixed COBOL version.
3.  **Performance Optimization**: The Java implementation must be highly optimized. Its execution time must be **almost equal** to the COBOL version (within a 1.5x factor) when processing large datasets.

## validation Rules (The Source of Truth)
The program reads `insurance.dat` (fixed width) and validates it.

### Record Formats
-   **Header ('H')**: Date (YYYYMMDD), Batch Name, State.
-   **Policy ('P')**: Policy No (10), Name (20), Prem (8), Tax (8), Total (8), Risk (1), Country (2), Account (10), Age (3).
-   **Trailer ('T')**: Count, Total Prem, Total Tax, Total Due.

### Logic & Checks
1.  **Header Check**: Date must match system date.
2.  **Account Check**: Must be 10 digits and start with '9'.
3.  **Banned Countries**: 'RU', 'KP' are banned.
4.  **Age Check**: 18-120.
5.  **Fiscal Integrity**: `Total Due` = `Prem` + `Tax`.
6.  **Tax Calculation**:
    -   Risk '3': 10%
    -   Risk '2': 5%
    -   Risk '1': 0%
    -   Rounding: Half-Up. (e.g. 100.05 * 0.10 = 10.005 -> 10.01)
7.  **Checksum**: Policy No mod 10 check.
8.  **Trailer**: Counts and Sums must match.
9.  **Error Priority**: If multiple errors exist, report the highest priority (lowest code):
    -   DATE_ERR (1)
    -   FORMAT_ERR (2)
    -   BANNED_ERR (3)
    -   AGE_ERR (4)
    -   COUNT_ERR (5)
    -   FISCAL_ERR (6)
    -   TAX_ERR (7)
    -   CHECKSUM_ERR (8)
    -   BATCH_SUM_ERR (9)

## Intentional Bugs in Baseline Code

The provided `validate.cbl` contains **4 intentional bugs** that you must identify and fix:

1. **Missing Date Validation** (Priority 1): The header date check against the system date is commented out, allowing invalid dates to pass validation.
2. **Missing Account Numeric Check** (Priority 2): The validation to ensure the account field contains only numeric digits is commented out, allowing non-numeric characters.
3. **Incorrect Tax Rate for Risk '2'** (Priority 7): The tax calculation uses 4% (0.04) instead of the correct 5% (0.05) for Risk category '2'.
4. **Wrong Age Upper Limit** (Priority 4): The age validation uses an upper limit of 150 instead of the correct 120.

**Your Task**: Fix all 4 bugs in the COBOL code and implement the corrected logic in Java.

## Java Requirements
-   **Class**: `com.tbench.insurance.Validator`
-   **Input**: Read from `stdin` or file args (match COBOL behavior).
-   **Output**: `STDOUT` (exactly matching error codes or "VALID").
-   **Build**: Maven will package the application as an uber JAR at `target/validator.jar` using the maven-shade-plugin.
-   **Invocation**: `java -jar target/validator.jar [optional-file-path]`
-   **Performance**: Use efficient I/O (Buffered), avoid heavy regex where simple char checks suffice, and use `BigDecimal` efficiently or long/int for fixed-point math if precise.

## Verification
-   `tests/test_cobol.py`: Verifies the COBOL fix.
-   `tests/test_java.sh`: Verifies the Java correctness.
-   `tests/benchmark.sh`: Compares execution speed on 500k records. Java Time <= 1.5 * COBOL Time.
