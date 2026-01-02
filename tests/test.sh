#!/bin/bash

# Dummy credentials for Terraform validation
export AWS_ACCESS_KEY_ID=testing
export AWS_SECRET_ACCESS_KEY=testing
export AWS_DEFAULT_REGION=us-east-1

# 0. Tool Installation (Self-contained environment)
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

# 1. Terraform Validation
echo -n "Checking Terraform... "
cd environment/terraform
terraform init -backend=false > /dev/null 2>&1
if terraform validate > /dev/null; then
  echo "PASS"
else
  echo "FAIL (terraform validate)"
  FAILURES=$((FAILURES+1))
fi

# 2. Check IAM Policies (Manual check for wildcard resource)
# We export plan to JSON and verify with python script
if terraform plan -out=tfplan > /dev/null 2>&1; then
    terraform show -json tfplan > tfplan.json
    if python3 ../../tests/validator.py --check-iam tfplan.json; then
        echo "PASS (IAM Policy)"
    else
        echo "FAIL (IAM Policy - Too Permissive)"
        FAILURES=$((FAILURES+1))
    fi
else
    echo "FAIL (terraform plan)"
    FAILURES=$((FAILURES+1))
fi

# 3. Prometheus Validation
echo -n "Checking Prometheus Config... "
cd ../prometheus
if promtool check config prometheus.yml > /dev/null 2>&1; then
  echo "PASS"
else
  echo "FAIL (promtool check config)"
  FAILURES=$((FAILURES+1))
fi

echo -n "Checking Alert Rules... "
if promtool check rules alerts.yml > /dev/null 2>&1 && python3 ../../tests/validator.py --check-prometheus alerts.yml; then
  echo "PASS"
else
  echo "FAIL (promtool check rules)"
  FAILURES=$((FAILURES+1))
fi

# 4. Grafana JSON Validation
echo -n "Checking Grafana JSON... "
cd ../grafana
if python3 ../../tests/validator.py --check-grafana dashboard.json; then
    echo "PASS"
else
    echo "FAIL (Grafana JSON/PromQL)"
    FAILURES=$((FAILURES+1))
fi

# Summary
echo "==============================="
if [ $FAILURES -eq 0 ]; then
    echo "ALL TESTS PASSED"
    # Create reward file for TerminalBench
    mkdir -p /logs/verifier
    echo 1 > /logs/verifier/reward.txt
    exit 0
else
    echo "$FAILURES TESTS FAILED"
    mkdir -p /logs/verifier
    echo 0 > /logs/verifier/reward.txt
    exit 1
fi
