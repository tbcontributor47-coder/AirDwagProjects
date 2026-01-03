#!/bin/bash
set -eo pipefail

# Pin pytest
pip install -q pytest==9.0.2

TEST_FILE="tests/test_outputs.py"
if [ ! -f "$TEST_FILE" ] && [ -f "/mnt/tests/test_outputs.py" ]; then
    TEST_FILE="/mnt/tests/test_outputs.py"
fi

# Run tests
if pytest "$TEST_FILE" -vv --tb=short; then
    echo "Tests passed!"
    # Generate reward for Harbor if directory exists
    if [ -d "/logs/verifier" ]; then
        echo "1.0" > /logs/verifier/reward.txt
    fi
    # Also write to local reward.txt if needed
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
