# COBOL to Java Migration: Insurance Validator

## Task Overview
1.  **Audit and Fix Legacy COBOL**: You are provided with a legacy COBOL program (`validate.cbl`) that validates insurance premium batch files. **The code is known to have multiple critical bugs and deviations from the specification.** You must strictly audit the code against the "Validation Rules" below, identify all logic errors, and fix them.
2.  **Migrate to Java**: Once the COBOL logic is verified and fixed, port it to a modern Java 17 application (`com.tbench.insurance.Validator`).
3.  **Performance Optimization**: The Java implementation must be highly optimized. Its execution time must be **within 1.5x** of the fixed COBOL version when processing large datasets (2,000,000+ records).

## Record Formats (Fixed Width)

The input `insurance.dat` contains three record types:

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

## Validation Rules (The Source of Truth)

The program must output **exactly one** error code to `STDOUT` if validation fails, based on the priority below (1 is highest). If multiple errors occur, report the highest priority one.

| Priority | Error Code | Condition |
| :--- | :--- | :--- |
| 1 | `DATE_ERR` | Header Date must match the current system date. |
| 2 | `FORMAT_ERR` | `Account No` must be exactly 10 digits and **must start with '9'**. |
| 3 | `BANNED_ERR` | Transactions from countries **'RU'** or **'KP'** are prohibited. |
| 4 | `AGE_ERR` | `Age` must be between **18** and **120** inclusive. |
| 5 | `COUNT_ERR` | Trailer `Policy Count` must match actual record count. OR missing trailer. |
| 6 | `FISCAL_ERR` | `Total Due` must equal `Base Premium + Tax Amount`. <br> **Premium Cap**: `Base Premium` must not exceed **$100,000.00**. |
| 7 | `TAX_ERR` | Tax must match calculated value based on Risk Category: <br> - Risk '3': 10% <br> - Risk '2': 5% <br> - Risk '1': 0% <br> **Rounding**: Half-Up (e.g., 0.005 -> 0.01). |
| 8 | `CHECKSUM_ERR` | Policy No check: `Sum(digits 1-9) modulo 10` must equal `digit 10`. |
| 9 | `BATCH_SUM_ERR` | Trailer totals (Prem, Tax, Due) must match sum of all valid policies. |

**Success**: If all checks pass, output `VALID`.

## Legacy Code Audit
The file `/app/validate.cbl` is an older version of the validator. It implements *most* of the logic but is **known to be defective**.
- Do NOT assume the COBOL code is correct.
- You must verify every rule above against the Code.
- Fix ANY logic that contradicts the "Validation Rules".

Note on large benchmarks and trailer width
----------------------------------------
The trailer field `Policy Count` is defined as `PIC 9(5)` (five digits) in the file format. Test generators and performance benchmarks in this task therefore use record counts less than or equal to `99,999` so the trailer can store the full count exactly. If you choose to support larger batch sizes, update the trailer field width in the instruction, COBOL source (`/app/validate.cbl`), and any test generators accordingly.

## Java Requirements
-   **Class**: `com.tbench.insurance.Validator`
-   **Input**: Read from `stdin` or file args (match COBOL behavior).
-   **Output**: `STDOUT` (Error Code or `VALID`).
-   **Build**: Uber-jar at `target/validator.jar`.
-   **Invocation**: `java -jar target/validator.jar [optional-file-path]`
-   **Performance**: Must be within 1.5x of the (fixed) COBOL runtime.
-   **Dependencies**: Only standard Java libraries allowed (no external rules engines).

## Deliverables
1.  **Fixed COBOL**: `/app/validate.cbl` (Passing all tests).
2.  **Java Source**: `src/main/java/com/tbench/insurance/Validator.java`.
3.  **Build Config**: `pom.xml`.
