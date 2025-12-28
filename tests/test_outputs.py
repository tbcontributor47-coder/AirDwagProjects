import json
import subprocess
import tempfile


def _run_with_input(input_text: str):
    with tempfile.NamedTemporaryFile(mode="w", delete=False, dir="/tmp", prefix="cobol_input_", suffix=".txt") as f:
        f.write(input_text)
        input_path = f.name

    proc = subprocess.run(
        ["/bin/bash", "/app/run_cobol.sh", input_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


def _parse_json_line(stdout: str):
    assert stdout.endswith("\n"), f"Expected trailing newline; got: {stdout!r}"
    return json.loads(stdout)


def test_valid_single_record():
    proc = _run_with_input("1234567890|2024-01-31|10.50|Coffee\n")
    assert proc.returncode == 0, f"Expected 0; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)

    assert out == {
        "records_processed": 1,
        "n_errors": 0,
        "total_cents": 1050,
        "errors": [],
    }


def test_blank_lines_ignored_but_line_numbers_count():
    # Two blank lines (one empty, one spaces) before the invalid record.
    proc = _run_with_input("\n   \n123|2024-00-10|1.0|Bad\n")
    assert proc.returncode == 2, f"Expected 2; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)

    assert out["records_processed"] == 1
    assert out["n_errors"] == 3
    assert out["total_cents"] == 0

    # Must include the original file line number (including blank lines): the invalid record is on line 3.
    assert out["errors"] == [
        "Line 3: ACCOUNT must be exactly 10 digits",
        "Line 3: DATE must be a valid calendar date",
        "Line 3: AMOUNT must have exactly 2 decimals",
    ]


def test_amount_zero_is_error_and_excludes_from_total():
    proc = _run_with_input(
        "1234567890|2024-01-01|0.00|Zero\n"
        "1234567890|2024-01-02|1.00|Ok\n"
    )
    assert proc.returncode == 2, f"Expected 2; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)

    assert out["records_processed"] == 2
    assert out["n_errors"] == 1
    assert out["total_cents"] == 100
    assert out["errors"] == ["Line 1: AMOUNT must be > 0"]
