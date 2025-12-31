import subprocess
import os

def test_merge_logic():
    """Test that the COBOL merge program correctly synchronizes three files using Balance Line algorithm."""
    # 1. Compile
    compile_cmd = ["cobc", "-x", "-o", "merge_app", "merge.cbl"]
    try:
        subprocess.run(compile_cmd, check=True, cwd="environment/app", capture_output=True)
    except subprocess.CalledProcessError as e:
        assert False, f"Compilation failed: {e.stderr.decode()}"

    # 2. Run
    try:
        subprocess.run(["./merge_app"], check=True, cwd="environment/app", capture_output=True)
    except subprocess.CalledProcessError as e:
        assert False, f"Execution failed: {e.stderr.decode()}"

    # 3. Verify Output
    report_path = "environment/app/report.txt"
    assert os.path.exists(report_path), "Output report.txt not found"

    with open(report_path, "r") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]

    expected = [
        "00001 | TS:0000560.00",
        "00002 | TS:0000400.00",
        "00003 | TS:0000020.00",
        "00004 | TS:0000030.00",
        "00005 | TS:0000620.00"
    ]

    assert lines == expected, f"Output mismatch.\nGot: {lines}\nExpected: {expected}"
