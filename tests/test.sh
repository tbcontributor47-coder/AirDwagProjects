#!/bin/bash
set -euo pipefail

# Pin pytest for deterministic behavior
pip install -q pytest==9.0.2

# The actual logic is in test_outputs.py (re-compiles and runs the app)
# We use the mounted path if available, otherwise fallback to local
TEST_FILE="tests/test_outputs.py"
if [ ! -f "$TEST_FILE" ] && [ -f "/mnt/tests/test_outputs.py" ]; then
    TEST_FILE="/mnt/tests/test_outputs.py"
fi

pytest "$TEST_FILE" -vv --tb=short
