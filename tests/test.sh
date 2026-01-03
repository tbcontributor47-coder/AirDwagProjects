#!/bin/bash
# Bank Reconciliation Test Runner
set -e

echo "Starting verifier..."
echo "Current directory: $(pwd)"
echo "Listing files in current directory:"
ls -R .

# Pin pytest
pip install -q pytest==9.0.2

# Determine test file path
TEST_FILE="tests/test_outputs.py"
if [ ! -f "$TEST_FILE" ] && [ -f "/mnt/tests/test_outputs.py" ]; then
    TEST_FILE="/mnt/tests/test_outputs.py"
fi

if [ ! -f "$TEST_FILE" ]; then
    echo "ERROR: Test file $TEST_FILE not found!"
    exit 1
fi

echo "Running tests from $TEST_FILE..."
# Use python3 -m pytest to ensure we use the installed version
if python3 -m pytest "$TEST_FILE" -vv --tb=short; then
    echo "Tests passed!"
    if [ -d "/logs/verifier" ]; then
        echo "1.0" > /logs/verifier/reward.txt
    fi
    echo "1.0" > reward.txt
    exit 0
else
    echo "Tests failed!"
    if [ -d "/logs/verifier" ]; then
        echo "0.0" > /logs/verifier/reward.txt
    fi
    echo "0.0" > reward.txt
    exit 1
fi
