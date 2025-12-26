#!/bin/bash
set -e

echo "Running EFT Validator Tests..."

# Run pytest
python3 -m pytest tests/test_validator.py -v --tb=short

echo "All tests passed!"
