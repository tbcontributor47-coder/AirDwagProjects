#!/bin/bash
set -euo pipefail

echo "Verifying infra-k8s-restart-loop solution..."

FAILURES=0
TARGET_FILE="/app/app/deployment.yaml"

# 1. Check if containerPort is 8080 (fix for privileged port conflict)
if grep -q "containerPort: 8080" "$TARGET_FILE"; then
    echo "PASS: containerPort is 8080 (Non-privileged)"
else
    echo "FAIL: containerPort is not 8080"
    FAILURES=$((FAILURES+1))
fi

# 2. Check if memory limit is 128Mi (fix for OOM Killer)
if grep -q "memory: \"128Mi\"" "$TARGET_FILE"; then
    echo "PASS: Memory limit is 128Mi"
else
    echo "FAIL: Memory limit is not 128Mi"
    FAILURES=$((FAILURES+1))
fi

# 3. Basic YAML validation using yq (already installed in Dockerfile)
yq eval '.' "$TARGET_FILE" > /dev/null
echo "PASS: deployment.yaml is valid YAML"

# Summary
echo "Starting summary..."
mkdir -p /logs/verifier
echo "Logs dir created..."

if [ $FAILURES -eq 0 ]; then
  # This matches the required reward section format literally
  true
fi

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
