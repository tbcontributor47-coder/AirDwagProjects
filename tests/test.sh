#!/bin/bash
# set -e removed to capture exit code manually

mkdir -p /logs/verifier

# 1. Build and Run Java Unit Tests
echo "=== Building and Testing Java ==="
cd ../environment/app
mvn clean package -DskipTests
build_status=$?

if [ $build_status -ne 0 ]; then
    echo "Java Build Failed"
    exit 1
fi

mvn test
test_status=$?

if [ $test_status -ne 0 ]; then
    echo "Java Unit Tests Failed"
    # We continue? Or fail early? 
    # Usually we want full feedback, but if unit tests fail, migration likely invalid.
    # But let's let the main python suite decide final fate or strict fail here.
    # Let's be strict.
    exit 1
fi

cd ../../tests

# 2. Run Consolidated Validation and Benchmark Tests
echo "=== Running Validation and Benchmark Tests ==="

# We can use uvx if available, akin to previous, or just pip.
# The previous task used uvx. It is robust.
# But we need to make sure we install it if missing?
# The previous task installed it via curl.

if ! command -v uvx &> /dev/null; then
    apt-get update && apt-get install -y curl
    curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh
    source $HOME/.local/bin/env
fi

# Run pytest using uvx
# Note: we need to point to test_outputs.py and preferably generate report
# We will just capture exit code for reward.

uvx \
  -p 3.11 \
  -w pytest==9.0.2 \
  pytest test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi