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
    """One valid record: program returns records_processed=1, no errors, and correct cents total."""
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
    """Blank lines should be ignored for processing count but included in reported line numbers."""
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
    """Zero amounts are validation errors and are not included in the monetary total."""
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


def test_trim_fields_are_allowed():
    """Fields with leading/trailing whitespace should be trimmed before validation."""
    proc = _run_with_input(" 1234567890 | 2024-01-31 | 10.50 | Coffee \n")
    assert proc.returncode == 0, f"Expected 0; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)
    assert out["records_processed"] == 1
    assert out["n_errors"] == 0
    assert out["total_cents"] == 1050


def test_unexpected_field_count_is_error():
    """Lines with more than four fields must raise an unexpected field count error."""
    proc = _run_with_input("1234567890|2024-01-31|10.00|Desc|extra\n")
    assert proc.returncode == 2, f"Expected 2; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)
    assert out["records_processed"] == 1
    assert out["n_errors"] == 1
    assert out["total_cents"] == 0
    assert out["errors"] == ["Line 1: unexpected field count"]


def test_amount_rejects_commas_and_symbols():
    """Amounts containing commas or currency symbols must be rejected as malformed."""
    proc = _run_with_input("1234567890|2024-01-01|1,000.00|Big\n")
    assert proc.returncode == 2, f"Expected 2; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)
    assert out["records_processed"] == 1
    assert out["n_errors"] >= 1
    assert out["total_cents"] == 0


def test_leap_year_date_validation():
    """Accept 2024-02-29 but reject 2023-02-29 (non-leap year)."""
    proc = _run_with_input(
        "1234567890|2024-02-29|1.00|Leap\n"
        "1234567890|2023-02-29|1.00|NotLeap\n"
    )
    assert proc.returncode == 2, f"Expected 2; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)
    assert out["records_processed"] == 2
    assert out["n_errors"] == 1
    assert out["total_cents"] == 100
    assert out["errors"] == ["Line 2: DATE must be a valid calendar date"]


def test_empty_fields_are_errors():
    """Missing required fields (empty after trimming) are validation errors."""
    proc = _run_with_input("1234567890||10.00|Desc\n")
    assert proc.returncode == 2, f"Expected 2; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)
    assert out["records_processed"] == 1
    assert out["n_errors"] >= 1
    assert out["total_cents"] == 0


def test_description_pipe_causes_unexpected_field_count():
    """An unescaped '|' in description should be treated as an extra field (error)."""
    proc = _run_with_input("1234567890|2024-01-01|1.00|Has|Pipe\n")
    assert proc.returncode == 2, f"Expected 2; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)
    assert out["errors"] == ["Line 1: unexpected field count"]


def test_accept_windows_line_endings():
    """Files using CRLF line endings should be accepted."""
    proc = _run_with_input("1234567890|2024-01-31|10.50|Coffee\r\n")
    assert proc.returncode == 0, f"Expected 0; got {proc.returncode}; stderr: {proc.stderr}"
    out = _parse_json_line(proc.stdout)
    assert out["records_processed"] == 1
    assert out["n_errors"] == 0
    assert out["total_cents"] == 1050
