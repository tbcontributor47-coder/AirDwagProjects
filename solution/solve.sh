#!/bin/bash
set -euo pipefail

TARGET_FILE="/app/app/deployment.yaml"

# 1. Fix Port Conflict: 80 -> 8080 (Non-root users cannot bind to <1024)
sed -i 's/containerPort: 80/containerPort: 8080/g' "$TARGET_FILE"
sed -i 's/port: 80/port: 8080/g' "$TARGET_FILE"

# 2. Fix OOM Limit: 16Mi -> 128Mi
sed -i 's/memory: "16Mi"/memory: "128Mi"/g' "$TARGET_FILE"
