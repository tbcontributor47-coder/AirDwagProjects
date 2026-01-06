#!/bin/bash
set -euo pipefail

# Build Java (if needed, though solve.sh might have done it)
cd /app/environment/app
mvn clean package -DskipTests

# Run Unit Tests
mvn test

# Run Benchmark/Validation
cd /app/tests
pytest test_outputs.py -v --tb=short