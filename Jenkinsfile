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
if ! TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"; then
    echo "ERROR: TASK_PATH cannot be resolved from WORKSPACE"
    echo "WORKSPACE: $WORKSPACE"
    echo "TASK_PATH (requested): $TASK_PATH"
    echo "EFFECTIVE_TASK_PATH: $EFFECTIVE_TASK_PATH"
    echo "PWD: $(pwd)"
    echo "Workspace contents:"
    ls -la
    exit 1
fi

echo "Task absolute path: $TASK_ABS"
if [ ! -d "$TASK_ABS" ]; then
    echo "ERROR: TASK_ABS does not exist: $TASK_ABS"
    exit 1
fi

echo "Checking Docker access..."
if ! docker version >/dev/null 2>&1; then
    echo "ERROR: Jenkins user cannot access Docker."
    echo "To fix: Add the agent service user to the docker group and restart the agent."
    exit 1
fi

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

        stage('Workspace Permissions (read-only)') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs

echo "===== Workspace permissions snapshot =====" | tee logs/permissions.log
echo "Node: $(hostname)" | tee -a logs/permissions.log
echo "User: $(id -un)" | tee -a logs/permissions.log
echo "Umask: $(umask)" | tee -a logs/permissions.log
echo "Workspace: $WORKSPACE" | tee -a logs/permissions.log

ls -ld "$WORKSPACE" | tee -a logs/permissions.log || true
ls -ld "$WORKSPACE/logs" "$WORKSPACE/jobs" 2>/dev/null | tee -a logs/permissions.log || true
ls -lan "$WORKSPACE" | head -n 50 | tee -a logs/permissions.log || true

if command -v getfacl >/dev/null 2>&1; then
    getfacl -p "$WORKSPACE" | tee logs/workspace.acl.txt | tee -a logs/permissions.log || true
    if ls -ld "$WORKSPACE" 2>/dev/null | awk '{print $1}' | grep -Fq '+'; then
        echo "NOTE: ls indicates ACLs (trailing '+')" | tee -a logs/permissions.log
    elif grep -Eq '^(default:|mask:|user:[^:]+:|group:[^:]+:)' logs/workspace.acl.txt 2>/dev/null; then
        echo "NOTE: workspace has extended ACL entries" | tee -a logs/permissions.log
    else
        echo "NOTE: no extended ACL entries detected" | tee -a logs/permissions.log
    fi
else
    echo "NOTE: getfacl not installed" | tee -a logs/permissions.log
fi
echo "===== End snapshot =====" | tee -a logs/permissions.log
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
    -v "$TASK_ABS/tests:/mnt/tests" \
    "$IMAGE_NAME" \
    /bin/bash -c "pip install -q pytest 2>&1 >/dev/null && pytest /mnt/tests/test_outputs.py -v --tb=short" \
    2>&1 | tee logs/baseline-test.log || true

echo ""
echo "===== Baseline Test Summary ====="
grep -E "(PASSED|FAILED|passed|failed)" logs/baseline-test.log | tail -1 || echo "No test summary found"
echo ""
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

echo ""
echo "===== Running solution/solve.sh inside container and re-testing ====="
docker run --rm \
    -v "$TASK_ABS/tests:/mnt/tests" \
    -v "$TASK_ABS/solution:/mnt/solution:ro" \
    "$IMAGE_NAME" \
    /bin/bash -c "
        set -euo pipefail
        echo 'Applying solution fixer to Java migration task'
        if [ -f /mnt/solution/solve.sh ]; then
            # Ensure executable
            chmod +x /mnt/solution/solve.sh
            bash /mnt/solution/solve.sh
        else
            echo 'ERROR: /mnt/solution/solve.sh not found in container'
            exit 1
        fi
        echo 'Re-running tests after fixer'
        pip install -q pytest 2>&1 >/dev/null
        pytest /mnt/tests/test_outputs.py -v --tb=short --junitxml=/mnt/tests/fix-report.xml || true
    " \
    2>&1 | tee logs/fix-and-verify.log || true

# Copy the junit xml from the mounted volume if it exists
if [ -f "$TASK_ABS/tests/fix-report.xml" ]; then
    cp "$TASK_ABS/tests/fix-report.xml" fix-report.xml
fi

echo ""
echo "===== FixAndVerify Test Summary ====="
grep -E "(PASSED|FAILED|passed|failed)" logs/fix-and-verify.log | tail -1 || echo "No test summary found"
echo ""
'''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'fix-report.xml,logs/fix-and-verify.log', allowEmptyArchive: true
                    // Publish junit but do not change overall build status if tests fail here
                    catchError(buildResult: 'SUCCESS', stageResult: 'SUCCESS') {
                        junit 'fix-report.xml'
                    }
                }
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

dump_harbor_run_from_log() {
    local log_file="$1"
    local label="$2"

    if [ ! -f "$log_file" ]; then
        return 0
    fi

    echo ""
    echo "--- ${label} ---"
    echo "Log: $log_file"

    local result_json
    result_json="$(awk '/Results written to /{print $NF}' "$log_file" | tail -n1)"
    if [ -z "$result_json" ]; then
        echo "No 'Results written to ...' line found in $log_file"
        return 0
    fi

    if [ ! -f "$result_json" ] && [ -f "$WORKSPACE/$result_json" ]; then
        result_json="$WORKSPACE/$result_json"
    fi

    if [ ! -f "$result_json" ]; then
        echo "Result file not found: $result_json"
        return 0
    fi

    echo "result.json: $result_json"
    cat "$result_json" 2>/dev/null || true

    local job_dir
    job_dir="$(dirname "$result_json")"
    echo "job dir: $job_dir"
    ls -la "$job_dir" 2>/dev/null || true

    if [ -f "$job_dir/job.log" ]; then
        echo "--- $job_dir/job.log (tail 200) ---"
        tail -n 200 "$job_dir/job.log" 2>/dev/null || true
    fi

    local trial_dir
    trial_dir="$(find "$job_dir" -mindepth 1 -maxdepth 1 -type d -print -quit 2>/dev/null || true)"
    if [ -z "$trial_dir" ]; then
        echo "No trial dir found under: $job_dir"
        return 0
    fi

    echo "trial dir: $trial_dir"
    ls -la "$trial_dir" 2>/dev/null || true

    for f in \
        "$trial_dir/config.json" \
        "$trial_dir/agent/oracle.txt" \
        "$trial_dir/agent/stdout.txt" \
        "$trial_dir/agent/stderr.txt" \
        "$trial_dir/stdout.txt" \
        "$trial_dir/stderr.txt" \
        "$trial_dir/verifier/test-stdout.txt" \
        "$trial_dir/verifier/test-stderr.txt" \
        ; do
        if [ -f "$f" ]; then
            echo "--- $f (first 2000 lines) ---"
            sed -n '1,2000p' "$f" 2>/dev/null || true
        fi
    done
}

harbor run --agent oracle --path "$TMPDIR" --force-build 2>&1 | tee logs/oracle.log || true

dump_harbor_run_from_log logs/oracle.log "Oracle Agent Run"

[ "${KEEP_TMPDIR:-false}" != "true" ] && rm -rf "$TMPDIR" || true
'''
            }
        }

        stage('Agent Runs (optional)') {
            when {
                expression { return env.OPENAI_API_KEY?.trim() && (params.RUN_ALL_MODES || params.RUN_CODEX || params.RUN_CLAUDE) }
            }
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
echo "Using temporary lowercase task dir: $TMPDIR"

rsync -a --exclude='.git' "$TASK_ABS/" "$TMPDIR/" || cp -a "$TASK_ABS/." "$TMPDIR/" || true

if [ "${RUN_ALL_MODES:-false}" = "true" ] || [ "${RUN_CODEX:-false}" = "true" ]; then
    echo "Running GPT-5 agent..."
    harbor run -a terminus-2 -m openai/@openai-tbench/gpt-5 -p "$TMPDIR" 2>&1 | tee logs/agent-gpt5.log
fi

if [ "${RUN_ALL_MODES:-false}" = "true" ] || [ "${RUN_CLAUDE:-false}" = "true" ]; then
    echo "Running Claude Sonnet 4.5 agent..."
    harbor run -a terminus-2 -m openai/@anthropic-tbench/claude-sonnet-4-5-20250929 -p "$TMPDIR" 2>&1 | tee logs/agent-claude.log
fi

# Cleanup
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
