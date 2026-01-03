#!/bin/bash
# Bank Reconciliation Test Runner
set -e

# Pin pytest
pip install -q pytest==9.0.2

# Search for test_outputs.py in absolute paths first (Harbor style)
# Harbor mounts tests to /tests
if [ -f "/tests/test_outputs.py" ]; then
    TEST_FILE="/tests/test_outputs.py"
elif [ -f "/mnt/tests/test_outputs.py" ]; then
    TEST_FILE="/mnt/tests/test_outputs.py"
elif [ -f "tests/test_outputs.py" ]; then
    TEST_FILE="tests/test_outputs.py"
else
    echo "ERROR: test_outputs.py not found!"
    # Print some debug info to help find it
    find / -name "test_outputs.py" 2>/dev/null | head -n 5
    exit 1
fi

echo "Running tests from $TEST_FILE..."
# Pass all script arguments to pytest
if python3 -m pytest "$TEST_FILE" -vv --tb=short "$@"; then
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
