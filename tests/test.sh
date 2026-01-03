#!/bin/bash
# Bank Reconciliation Test Runner
set -e

# Pin pytest
pip install -q pytest==9.0.2

# Search for test_outputs.py in absolute paths first (Harbor style)
if [ -f "/tests/test_outputs.py" ]; then
    TEST_FILE="/tests/test_outputs.py"
elif [ -f "/mnt/tests/test_outputs.py" ]; then
    TEST_FILE="/mnt/tests/test_outputs.py"
elif [ -f "tests/test_outputs.py" ]; then
    TEST_FILE="tests/test_outputs.py"
else
    echo "ERROR: test_outputs.py not found!"
    exit 1
fi

echo "Running tests from $TEST_FILE..."
set +e
# Must use -rA as required by static checks
python3 -m pytest "$TEST_FILE" -vv --tb=short -rA "$@"

# Must follow the exact reward section format for static checks
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
