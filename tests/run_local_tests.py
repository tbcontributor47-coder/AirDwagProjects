
import sys
import os
import pytest
import subprocess

# Add the tests directory to sys.path so we can import test_outputs
sys.path.append(os.path.join(os.getcwd(), 'tests'))

# Import the test file
import test_outputs

# Path to the local drift_audit.py
DRIFT_AUDIT_PATH = os.path.abspath(os.path.join(os.getcwd(), 'environment', 'app', 'drift_audit.py'))

def mock_run_audit(args):
    """Mock for test_outputs.run_audit that calls the local python script."""
    # args is a list of strings
    cmd = [sys.executable, DRIFT_AUDIT_PATH] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr

# Monkeypatch the run_audit function in test_outputs module
test_outputs.run_audit = mock_run_audit

if __name__ == "__main__":
    # Run pytest on the imported module
    sys.exit(pytest.main(["tests/test_outputs.py", "-v"]))
