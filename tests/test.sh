#!/bin/bash
set -e

# Ensure not running from root directory
if [ "$PWD" = "/" ]; then
    echo "Error: Cannot run tests from root directory"
    exit 1
fi

# Create log directories
mkdir -p /logs/verifier
chmod -R a+rwx /logs || true

# Remove old reward file
rm -f /logs/verifier/reward.txt

echo "Running EFT Validator Tests..."

# Run pytest and capture exit code
if python3 -m pytest tests/test_validator.py -v -rA --tb=short; then
    echo "Tests passed"
    echo 1 > /logs/verifier/reward.txt
else
    echo "Tests failed"
    echo 0 > /logs/verifier/reward.txt
fi

# Always exit 0 so Harbor can consume reward
exit 0
