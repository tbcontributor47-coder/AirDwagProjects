pipeline {
    agent {
        label 'Linux-01'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {
        booleanParam(name: 'RUN_ALL_MODES', defaultValue: true, description: 'Run oracle + nop + GPT-5 + Claude + consolidate (optional)')
        booleanParam(name: 'RUN_NOP', defaultValue: false, description: 'Run Harbor nop agent (optional)')
        booleanParam(name: 'RUN_CODEX', defaultValue: false, description: 'Run GPT-5 agent run (CodeBuild "codex" equivalent)')
        booleanParam(name: 'RUN_CLAUDE', defaultValue: false, description: 'Run Claude Sonnet 4.5 agent run (optional)')
        booleanParam(name: 'RUN_DIFFICULTY_5X', defaultValue: false, description: 'Run 5x GPT-5 + 5x Claude and print pass rates (optional)')
        booleanParam(name: 'RUN_CONSOLIDATE', defaultValue: false, description: 'Print a consolidated jobs/logs summary (optional)')
        booleanParam(name: 'KEEP_TMPDIR', defaultValue: false, description: 'Keep temporary task directories for debugging')
    }

    environment {
        TASK_PATH = '.'
        OPENAI_BASE_URL = 'https://api.portkey.ai/v1'
        PUSH_LOGS_TO_GIT = 'false'
    }

    stages {
        stage('Preflight') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

echo "Node: $(hostname)"
echo "Workspace: $WORKSPACE"
echo "User: $(id -un)"

# Multibranch support
echo "BRANCH_NAME: ${BRANCH_NAME:-<unset>}"
if [ -n "${BRANCH_NAME:-}" ] && [ -d "$WORKSPACE/$BRANCH_NAME" ]; then
    echo "Detected branch-named task directory: $BRANCH_NAME"
    EFFECTIVE_TASK_PATH="$BRANCH_NAME"
else
    EFFECTIVE_TASK_PATH="$TASK_PATH"
fi

echo "Task path: $EFFECTIVE_TASK_PATH"
TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"

echo "Task absolute path: $TASK_ABS"

echo "Checking Docker access..."
docker version >/dev/null 2>&1

# Install Harbor CLI
(
    set -euo pipefail
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env"
    uv tool install harbor==0.1.25 --python 3.13
    export PATH="$HOME/.local/bin:$PATH"
    harbor --help >/dev/null
) 2>&1 | tee logs/preflight.log
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
echo "Task absolute path: $TASK_ABS"

BASENAME="$(basename "$TASK_ABS" | tr '[:upper:]' '[:lower:]')"
IMAGE_NAME="${BASENAME}:baseline-test"

echo "===== Building Docker image for baseline testing ====="
docker build -f "$TASK_ABS/environment/Dockerfile" -t "$IMAGE_NAME" "$TASK_ABS/environment" 2>&1 | tee logs/baseline-build.log

echo ""
echo "===== Running tests against BUGGY baseline (should have failures) ====="
docker run --rm \
    -v "$TASK_ABS/tests:/tests:ro" \
    "$IMAGE_NAME" \
    /bin/bash -c "/tests/test.sh" \
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
echo "Task absolute path: $TASK_ABS"

BASENAME="$(basename "$TASK_ABS" | tr '[:upper:]' '[:lower:]')"
IMAGE_NAME="${BASENAME}:baseline-test"

echo "===== Applying solution fixer and re-running tests ====="
docker run --rm \
    -v "$TASK_ABS/tests:/tests:ro" \
    -v "$TASK_ABS/solution:/mnt/solution:ro" \
    "$IMAGE_NAME" \
    /bin/bash -c "
        set -euo pipefail
        bash /mnt/solution/solve.sh
        /tests/test.sh
    " \
    2>&1 | tee logs/fix-and-verify.log || true
'''
            }
        }

        stage('Checks') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs

export PATH="$HOME/.local/bin:$PATH"
[ -f "$HOME/.local/bin/env" ] && source "$HOME/.local/bin/env"

command -v harbor >/dev/null || { echo "harbor not found in PATH"; exit 127; }

# Multibranch support
if [ -n "${BRANCH_NAME:-}" ] && [ -d "$WORKSPACE/$BRANCH_NAME" ]; then
    EFFECTIVE_TASK_PATH="$BRANCH_NAME"
else
    EFFECTIVE_TASK_PATH="$TASK_PATH"
fi

TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"
harbor tasks check "$TASK_ABS" --model openai/@openai-tbench/gpt-5 2>&1 | tee logs/checks.log
'''
            }
        }

        stage('Oracle') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs

export PATH="$HOME/.local/bin:$PATH"
[ -f "$HOME/.local/bin/env" ] && source "$HOME/.local/bin/env"

command -v harbor >/dev/null || { echo "harbor not found in PATH"; exit 127; }

# Multibranch support
if [ -n "${BRANCH_NAME:-}" ] && [ -d "$WORKSPACE/$BRANCH_NAME" ]; then
    EFFECTIVE_TASK_PATH="$BRANCH_NAME"
else
    EFFECTIVE_TASK_PATH="$TASK_PATH"
fi

TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"
BASENAME="$(basename "$TASK_ABS" | tr '[:upper:]' '[:lower:]')"
SUFFIX="$(openssl rand -hex 6 2>/dev/null || tr -dc 'a-f0-9' < /dev/urandom | head -c6 || echo '000000')"
TMPDIR="/tmp/${BASENAME}.${SUFFIX}"
mkdir -p "$TMPDIR"
rsync -a --exclude='.git' "$TASK_ABS/" "$TMPDIR/" || cp -a "$TASK_ABS/." "$TMPDIR/" || true

harbor run --agent oracle --path "$TMPDIR" --force-build 2>&1 | tee logs/oracle.log || true

[ "${KEEP_TMPDIR:-false}" != "true" ] && rm -rf "$TMPDIR" || true
'''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'logs/**,jobs/**', allowEmptyArchive: true
        }
    }
}
