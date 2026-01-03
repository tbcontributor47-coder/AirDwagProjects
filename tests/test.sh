#!/bin/bash
# Reconcile Ledger Test Runner
set -e

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

# Run pytest using pre-installed uv
uvx \
  --python 3.11 \
  --with pytest==8.4.1 \
  --with pytest-json-ctrf==0.3.5 \
  pytest --ctrf /logs/verifier/ctrf.json "$TEST_FILE" -rA "$@"

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi