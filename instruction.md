# COBOL Buggy Task: Transaction Summarizer (Mainframe-style)

You are given a small legacy COBOL program at `/app/main.cob`.

The program is intended to read a pipe-delimited transaction file and print a single-line JSON summary to stdout.
The baseline program contains **multiple intentional bugs** (logic + validation + formatting).

Your job is to fix `/app/main.cob` so it matches the exact contract below.

## CLI

The verifier runs:

```
/bin/bash /app/run_cobol.sh /tmp/input.txt
```

Where `/tmp/input.txt` is created by the tests.

## Input format

The input file is UTF-8 text. Each non-empty line is a record:

```
ACCOUNT|DATE|AMOUNT|DESCRIPTION
```

- `ACCOUNT`: exactly 10 digits (0-9)
- `DATE`: exactly `YYYY-MM-DD`
- `AMOUNT`: decimal with exactly 2 digits after the dot, e.g. `10.50`
- `DESCRIPTION`: any text (may include spaces). It is not used for calculations.

Blank lines (including lines containing only spaces/tabs) must be ignored.

## Output contract

Print exactly one JSON object on stdout, followed by a single newline.

Schema:

- `records_processed` (integer): number of **non-blank** lines processed
- `n_errors` (integer): number of validation errors
- `total_cents` (integer): sum of all **valid** amounts converted to cents
- `errors` (array of strings): each error message must be prefixed with `Line N:` where N is the 1-based line number in the file (including blank lines)

Validation rules:

- If `ACCOUNT` is not exactly 10 digits: error
- If `DATE` is not a valid calendar date in `YYYY-MM-DD`:
	- month must be 01-12
	- day must be 01-31
	- month/day `00` is invalid
- If `AMOUNT` does not have exactly 2 decimals: error
- If `AMOUNT` is negative or zero: error

Only valid records contribute to `total_cents`.

Exit codes:

- `0` if `n_errors == 0`
- `2` if `n_errors > 0`

## Verifier behavior

- `/tests/test.sh` runs `pytest /tests/test_outputs.py` and writes `/logs/verifier/reward.txt`.
- Baseline container should fail tests.
- After applying the fixer `solution/solve.sh` (which overwrites `/app/main.cob`), tests should pass.

## Determinism requirements

- Locale is fixed to `LANG=C.UTF-8` and `LC_ALL=C.UTF-8`.
- No network/time/random usage.
- Output must be deterministic and stable.

## Verifier tests (required coverage)

The verifier uses `pytest` and executes the program through `/bin/bash /app/run_cobol.sh <input>`.

### How the verifier runs (step-by-step)

1) Writes an input file.
2) Runs `/bin/bash /app/run_cobol.sh <input_path>`.
3) Parses stdout as JSON (exactly one line + trailing newline).
4) Validates `records_processed`, `n_errors`, `total_cents`, and `errors`.
5) Validates exit code: `0` iff `n_errors == 0`, else `2`.

### Complete test list (all tests must pass)

- `test_valid_single_record` — One valid record produces correct totals and exit `0`.
- `test_blank_lines_ignored_but_line_numbers_count` — Blank lines don’t increment `records_processed` but still affect `Line N:` numbering.
- `test_amount_zero_is_error_and_excludes_from_total` — `0.00` is an error and is excluded from the cents total.

## Test formatting and agent timeout notes (reviewer feedback)

- The verifier expects the program to print exactly one JSON object on stdout followed by a single trailing newline character ("one-line JSON"). Any extra characters, progress text, or multiple lines will cause the verifier to fail parsing. If you must log diagnostics, write them to stderr only.
- Tests in `tests/test_outputs.py` include docstrings that describe the behavior being validated. Implementations should follow those contracts exactly.
- Agents have been observed to time out under heavier workloads. The reviewer requested increasing the agent runtime budget; the task metadata sets the agent timeout to `900` seconds. Ensure any long-running operations are necessary and avoid network I/O or sleeps.

### Quick checklist for formatting

- Output: single JSON object + trailing `\n` only on stdout.
- Error messages: must be human-readable strings and prefixed with `Line N:` where N is the original 1-based line number in the file (count blank lines).
- Exit codes: `0` when `n_errors == 0`, `2` otherwise.

