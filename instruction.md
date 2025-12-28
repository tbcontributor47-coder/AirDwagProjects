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
