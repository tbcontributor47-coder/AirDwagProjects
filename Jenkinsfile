pipeline {
    agent {
        label 'Linux-01'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    environment {
        TASK_PATH = '.'
    }

    stages {
        stage('Preflight') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
echo "Node: $(hostname)"
echo "Workspace: $WORKSPACE"

# Multibranch support
echo "BRANCH_NAME: ${BRANCH_NAME:-<unset>}"
if [ -n "${BRANCH_NAME:-}" ] && [ -d "$WORKSPACE/$BRANCH_NAME" ]; then
    echo "Detected branch-named task directory: $BRANCH_NAME"
    EFFECTIVE_TASK_PATH="$BRANCH_NAME"
else
    EFFECTIVE_TASK_PATH="$TASK_PATH"
fi

echo "Task path: $EFFECTIVE_TASK_PATH"
if ! TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"; then
    echo "ERROR: TASK_PATH cannot be resolved from WORKSPACE"
    exit 1
fi
echo "Task absolute path: $TASK_ABS"
'''
            }
        }

        stage('Baseline Test (Buggy)') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs

# Multibranch support
if [ -n "${BRANCH_NAME:-}" ] && [ -d "$WORKSPACE/$BRANCH_NAME" ]; then
    EFFECTIVE_TASK_PATH="$BRANCH_NAME"
else
    EFFECTIVE_TASK_PATH="$TASK_PATH"
fi

TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"
BASENAME="$(basename "$TASK_ABS" | tr '[:upper:]' '[:lower:]')"
IMAGE_NAME="${BASENAME}:baseline-test"

echo "===== Building Docker image for baseline testing ====="
docker build -f "$TASK_ABS/environment/Dockerfile" -t "$IMAGE_NAME" "$TASK_ABS/environment" 2>&1 | tee logs/baseline-build.log

echo ""
echo "===== Running tests against BUGGY baseline (should have failures) ====="
docker run --rm \
    -v "$TASK_ABS/tests:/app/tests" \
    "$IMAGE_NAME" \
    /bin/bash /app/tests/test.sh \
    2>&1 | tee logs/baseline-test.log || true
'''
            }
        }

        stage('FixAndVerify') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs

# Multibranch support
if [ -n "${BRANCH_NAME:-}" ] && [ -d "$WORKSPACE/$BRANCH_NAME" ]; then
    EFFECTIVE_TASK_PATH="$BRANCH_NAME"
else
    EFFECTIVE_TASK_PATH="$TASK_PATH"
fi

TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"
BASENAME="$(basename "$TASK_ABS" | tr '[:upper:]' '[:lower:]')"
IMAGE_NAME="${BASENAME}:baseline-test"

echo ""
echo "===== Running solution/solve.sh inside container and re-testing ====="
docker run --rm \
    -v "$TASK_ABS/tests:/app/tests" \
    -v "$TASK_ABS/solution:/mnt/solution:ro" \
    "$IMAGE_NAME" \
    /bin/bash -c "
        set -euo pipefail
        if [ -f /mnt/solution/solve.sh ]; then
            bash /mnt/solution/solve.sh
        else
            echo 'ERROR: /mnt/solution/solve.sh not found in container'
            exit 1
        fi
        bash /app/tests/test.sh
    " \
    2>&1 | tee logs/fix-and-verify.log
'''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'logs/**', allowEmptyArchive: true
        }
    }
}
