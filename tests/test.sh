#!/bin/bash
set -e

# Verifier runner (matches repo conventions):
# - Writes reward to /logs/verifier/reward.txt
# - Runs pytest from /tests
# - Always exits 0 so the harness can consume reward

if [ "$PWD" = "/" ]; then
    echo "Error: Cannot run tests from root directory"
    exit 1
fi

mkdir -p /logs/verifier
chmod -R a+rwx /logs || true

rm -f /logs/verifier/reward.txt

echo "Running COBOL Buggy Task Tests..."

python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
python3 -m pip install "pytest==8.4.1" >/dev/null 2>&1

if python3 -m pytest /tests/test_outputs.py -v -rA --tb=short; then
    echo "Tests passed"
    echo 1 > /logs/verifier/reward.txt
else
    echo "Tests failed"
    echo 0 > /logs/verifier/reward.txt
fi

exit 0
