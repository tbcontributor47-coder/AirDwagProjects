#!/bin/bash
set -euo pipefail

# Compile the COBOL program
cobc -x -o reconcile_app environment/app/reconcile.cbl

# Run the COBOL program
./reconcile_app

# Run the Python logic validator
pip install -q pytest
pytest tests/test_outputs.py -vv --tb=short
