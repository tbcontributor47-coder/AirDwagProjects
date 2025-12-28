import subprocess


def test_cobol_output_is_exact():
    """Compiles and runs `/app/main.cob` via `/app/run_cobol.sh`.

    The baseline image contains an intentionally buggy COBOL program, so this test should
    FAIL until the solver overwrites `/app/main.cob` with a corrected version.
    """
    proc = subprocess.run(['/bin/bash', '/app/run_cobol.sh'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.returncode == 0, f"Non-zero exit: {proc.returncode}; stderr: {proc.stderr}"
    assert proc.stdout == "COBOL: Hello, world\n"
