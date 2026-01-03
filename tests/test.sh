#!/bin/bash

# Dummy credentials for Terraform validation
export AWS_ACCESS_KEY_ID=testing
export AWS_SECRET_ACCESS_KEY=testing
export AWS_DEFAULT_REGION=us-east-1

# 0. Tool Installation (Self-contained environment)
# Install system dependencies if missing
if ! command -v curl &> /dev/null || ! command -v unzip &> /dev/null || ! command -v jq &> /dev/null; then
    echo "Installing system dependencies (curl, unzip, jq)..."
    apt-get update >/dev/null 2>&1 && apt-get install -y curl unzip jq >/dev/null 2>&1 || echo "Warning: Could not install system deps."
fi

if ! python3 -c "import yaml" &> /dev/null; then
    echo "Installing pyyaml..."
    pip install pyyaml==6.0.1 >/dev/null 2>&1
fi
if ! command -v terraform &> /dev/null; then
    echo "Installing Terraform..."
    curl -LO https://releases.hashicorp.com/terraform/1.5.7/terraform_1.5.7_linux_amd64.zip >/dev/null 2>&1
    unzip terraform_1.5.7_linux_amd64.zip >/dev/null 2>&1
    chmod +x terraform
    export PATH=$PATH:$(pwd)
    rm terraform_1.5.7_linux_amd64.zip
fi

if ! command -v promtool &> /dev/null; then
    echo "Installing Promtool..."
    curl -LO https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz >/dev/null 2>&1
    tar xvfz prometheus-2.45.0.linux-amd64.tar.gz >/dev/null 2>&1
    chmod +x prometheus-2.45.0.linux-amd64/promtool
    export PATH=$PATH:$(pwd)/prometheus-2.45.0.linux-amd64
    rm prometheus-2.45.0.linux-amd64.tar.gz
fi

echo "=== Running Configuration Tests ==="
FAILURES=0

# Find environment directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Detect environment directory
if [ -d "$TASK_ROOT/environment" ]; then
    ENV_DIR="$TASK_ROOT/environment"
elif [ -d "/app/environment" ]; then
    ENV_DIR="/app/environment"
else
    echo "ERROR: Could not find environment directory"
    exit 1
fi

echo "Using environment directory: $ENV_DIR"

# 1. Check Terraform
echo "Checking Terraform..."
cd "$ENV_DIR/terraform"
terraform init -backend=false > /dev/null 2>&1
if terraform validate; then
    echo "PASS (terraform validate)"
else
    echo "FAIL (terraform validate)"
    FAILURES=$((FAILURES+1))
fi

if terraform plan -refresh=false -out=tfplan > tfplan.out 2>&1; then
    terraform show -json tfplan > tfplan.json
    if python3 "$SCRIPT_DIR/test_outputs.py" --check-iam tfplan.json --check-constraints tfplan.json; then
        echo "PASS (IAM & Constraints)"
    else
        echo "FAIL (IAM & Constraints)"
        FAILURES=$((FAILURES+1))
    fi
else
    echo "FAIL (terraform plan)"
    cat tfplan.out
    FAILURES=$((FAILURES+1))
fi

# 2. Prometheus Validation
echo -n "Checking Prometheus Logic... "
cd "$ENV_DIR/prometheus"
if promtool check config prometheus.yml > /dev/null 2>&1 && python3 "$SCRIPT_DIR/test_outputs.py" --check-prometheus prometheus.yml; then
  echo "PASS"
else
  echo "FAIL"
  FAILURES=$((FAILURES+1))
fi

echo -n "Checking Alert Rules... "
if promtool check rules alerts.yml > /dev/null 2>&1 && python3 "$SCRIPT_DIR/test_outputs.py" --check-prometheus alerts.yml; then
  echo "PASS"
else
  echo "FAIL"
  FAILURES=$((FAILURES+1))
fi

# 3. Grafana JSON Validation
echo -n "Checking Grafana Logic... "
cd "$ENV_DIR/grafana"
if python3 "$SCRIPT_DIR/test_outputs.py" --check-grafana dashboard.json; then
    echo "PASS"
else
    echo "FAIL"
    FAILURES=$((FAILURES+1))
fi

# Summary
echo "==============================="
if [ $FAILURES -eq 0 ]; then
    echo "ALL TESTS PASSED"
    true
else
    echo "$FAILURES TESTS FAILED"
    false
fi

# Final reward reporting
mkdir -p /logs/verifier
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
