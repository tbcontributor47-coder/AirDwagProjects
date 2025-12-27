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
  /bin/bash -c "pip install -q pytest 2>&1 >/dev/null && pytest /mnt/tests/test_outputs.py -vv --tb=short" \
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
    echo 'Applying solution fixer to /app/drift_audit.py'
    if [ -f /mnt/solution/solve.sh ]; then
      bash /mnt/solution/solve.sh
    else
      echo 'ERROR: /mnt/solution/solve.sh not found in container'
      exit 1
    fi
    echo 'Re-running tests after fixer'
    pip install -q pytest 2>&1 >/dev/null
    pytest /mnt/tests/test_outputs.py -vv --tb=short --junitxml=/mnt/tests/fix-report.xml || true
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
          echo 'FixAndVerify stage completed; see fix-report.xml and logs/fix-and-verify.log for details'
        }
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

# Copy to lowercase temp dir to avoid Docker invalid image name errors
TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

BASENAME="$(basename "$TASK_ABS" | tr '[:upper:]' '[:lower:]')"
SUFFIX="$(openssl rand -hex 6 2>/dev/null || tr -dc 'a-f0-9' < /dev/urandom | head -c6 || echo '000000')"
TMPDIR="/tmp/${BASENAME}.${SUFFIX}"
mkdir -p "$TMPDIR"
echo "Using temporary lowercase task dir: $TMPDIR"

rsync -a --exclude='.git' "$TASK_ABS/" "$TMPDIR/" || cp -a "$TASK_ABS/." "$TMPDIR/" || true

harbor run --agent oracle --path "$TMPDIR" --force-build 2>&1 | tee logs/oracle.log || true

RESULT_JSON="$(awk '/Results written to /{print $NF}' logs/oracle.log | tail -n1)"
[ -z "$RESULT_JSON" ] && RESULT_JSON="$(find jobs -name result.json -type f | head -n1 || true)"

if [ -z "$RESULT_JSON" ] || [ ! -f "$RESULT_JSON" ]; then
  echo "ERROR: Harbor result file not found"
  echo "Temporary task dir left at: $TMPDIR"
  exit 1
fi

echo ""
JOB_DIR="$(dirname "$RESULT_JSON")"

echo "========== Harbor Oracle result.json =========="
cat "$RESULT_JSON" || true
echo ""

echo "========== Harbor Oracle job dir listing =========="
ls -la "$JOB_DIR" 2>/dev/null || true
echo ""

echo "========== Harbor Oracle job.log =========="
if [ -f "$JOB_DIR/job.log" ]; then
  cat "$JOB_DIR/job.log" || true
else
  echo "(no job.log)"
fi
echo ""

echo "========== Harbor Oracle trial directory =========="
TRIAL_DIR="$(find "$JOB_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | head -n1 || true)"
if [ -z "$TRIAL_DIR" ]; then
  echo "(no trial directory found under $JOB_DIR)"
else
  echo "Trial dir: ${TRIAL_DIR}"
  ls -la "$TRIAL_DIR" 2>/dev/null || true
  echo ""

  if [ -d "$TRIAL_DIR/agent" ]; then
    echo "${TRIAL_DIR}/agent:"
    ls -la "$TRIAL_DIR/agent" 2>/dev/null || true
    echo ""
  fi

  if [ -d "$TRIAL_DIR/verifier" ]; then
    echo "${TRIAL_DIR}/verifier:"
    ls -la "$TRIAL_DIR/verifier" 2>/dev/null || true
    echo ""
  fi

  echo "--- Trial config.json ---"
  if [ -f "$TRIAL_DIR/config.json" ]; then
    cat "$TRIAL_DIR/config.json" || true
  else
    echo "(no config.json)"
  fi

  echo "--- Agent oracle.txt ---"
  if [ -f "$TRIAL_DIR/agent/oracle.txt" ]; then
    cat "$TRIAL_DIR/agent/oracle.txt" || true
  else
    echo "(no oracle.txt)"
  fi

  echo "--- Trial stdout ---"
  TRIAL_STDOUT=""
  for f in "$TRIAL_DIR/stdout.txt" "$TRIAL_DIR/trial-stdout.txt" "$TRIAL_DIR/agent/stdout.txt"; do
    if [ -f "$f" ]; then TRIAL_STDOUT="$f"; break; fi
  done
  if [ -n "$TRIAL_STDOUT" ]; then
    cat "$TRIAL_STDOUT" || true
  else
    echo "(no stdout)"
  fi

  echo "--- Trial stderr ---"
  TRIAL_STDERR=""
  for f in "$TRIAL_DIR/stderr.txt" "$TRIAL_DIR/trial-stderr.txt" "$TRIAL_DIR/agent/stderr.txt"; do
    if [ -f "$f" ]; then TRIAL_STDERR="$f"; break; fi
  done
  if [ -n "$TRIAL_STDERR" ]; then
    cat "$TRIAL_STDERR" || true
  else
    echo "(no stderr)"
  fi

  echo "--- Test stdout (verifier/test-stdout.txt) ---"
  if [ -f "$TRIAL_DIR/verifier/test-stdout.txt" ]; then
    cat "$TRIAL_DIR/verifier/test-stdout.txt" || true
  else
    echo "(no verifier/test-stdout.txt)"
  fi

  echo "--- Test stderr (verifier/test-stderr.txt) ---"
  if [ -f "$TRIAL_DIR/verifier/test-stderr.txt" ]; then
    cat "$TRIAL_DIR/verifier/test-stderr.txt" || true
  else
    echo "(no verifier/test-stderr.txt)"
  fi
fi

echo "================================================="

# Cleanup
[ "${KEEP_TMPDIR:-false}" != "true" ] && rm -rf "$TMPDIR" || true

# Validate no errors
python3 - "$RESULT_JSON" <<'PY'
import json, sys
with open(sys.argv[1]) as f: data = json.load(f)
def max_errors(node):
    if isinstance(node, dict):
        m = max((int(v) for k,v in node.items() if k.lower() in ("n_errors","errors") and str(v).isdigit()), default=0)
        return max(m, max((max_errors(v) for v in node.values()), default=0))
    return max((max_errors(x) for x in node), default=0) if isinstance(node, list) else 0
err = max_errors(data)
print(f"Harbor reported errors: {err}")
sys.exit(1 if err > 0 else 0)
PY
'''
      }
    }

    stage('NOP (optional)') {
      when {
        expression { return params.RUN_ALL_MODES || params.RUN_NOP }
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

# Copy to lowercase temp dir
TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

BASENAME="$(basename "$TASK_ABS" | tr '[:upper:]' '[:lower:]')"
SUFFIX="$(openssl rand -hex 6 2>/dev/null || tr -dc 'a-f0-9' < /dev/urandom | head -c6 || echo '000000')"
TMPDIR="/tmp/${BASENAME}.${SUFFIX}"
mkdir -p "$TMPDIR"
echo "Using temporary lowercase task dir: $TMPDIR"

rsync -a --exclude='.git' "$TASK_ABS/" "$TMPDIR/" || cp -a "$TASK_ABS/." "$TMPDIR/" || true

harbor run --agent nop --path "$TMPDIR" --force-build 2>&1 | tee logs/nop.log || true

# Cleanup
[ "${KEEP_TMPDIR:-false}" != "true" ] && rm -rf "$TMPDIR" || true
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

# Copy to lowercase temp dir to avoid Docker invalid image name errors
TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

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

    stage('Difficulty Check (5x each, optional)') {
      when {
        expression { return env.OPENAI_API_KEY?.trim() && params.RUN_DIFFICULTY_5X }
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

# Copy to lowercase temp dir to avoid Docker invalid image name errors
TASK_ABS="$(cd "$WORKSPACE/$EFFECTIVE_TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

BASENAME="$(basename "$TASK_ABS" | tr '[:upper:]' '[:lower:]')"
SUFFIX="$(openssl rand -hex 6 2>/dev/null || tr -dc 'a-f0-9' < /dev/urandom | head -c6 || echo '000000')"
TMPDIR="/tmp/${BASENAME}.${SUFFIX}"
mkdir -p "$TMPDIR"
echo "Using temporary lowercase task dir: $TMPDIR"

rsync -a --exclude='.git' "$TASK_ABS/" "$TMPDIR/" || cp -a "$TASK_ABS/." "$TMPDIR/" || true

echo "===== Difficulty Check (5x each) =====" | tee logs/difficulty-5x.log

for i in $(seq 1 5); do
  echo "GPT-5 run $i/5"
  harbor run -a terminus-2 -m openai/@openai-tbench/gpt-5 -p "$TMPDIR" 2>&1 | tee "logs/difficulty-gpt5-${i}.log"
done

for i in $(seq 1 5); do
  echo "Claude run $i/5"
  harbor run -a terminus-2 -m openai/@anthropic-tbench/claude-sonnet-4-5-20250929 -p "$TMPDIR" 2>&1 | tee "logs/difficulty-claude-${i}.log"
done

# Cleanup
[ "${KEEP_TMPDIR:-false}" != "true" ] && rm -rf "$TMPDIR" || true

echo "===== Difficulty check complete =====" | tee -a logs/difficulty-5x.log
exit 0
'''
      }
    }

    stage('Consolidate (optional)') {
      when {
        expression { return params.RUN_ALL_MODES || params.RUN_CONSOLIDATE }
      }
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs

echo "===== Consolidated summary =====" | tee logs/consolidate.log
echo "Node: $(hostname)" | tee -a logs/consolidate.log
echo "Workspace: $WORKSPACE" | tee -a logs/consolidate.log

echo "" | tee -a logs/consolidate.log
echo "===== Test Results Comparison =====" | tee -a logs/consolidate.log

if [ -f logs/baseline-test.log ]; then
  echo "" | tee -a logs/consolidate.log
  echo "--- Baseline (Buggy) Test Results ---" | tee -a logs/consolidate.log
  grep -E "(PASSED|FAILED|passed|failed)" logs/baseline-test.log | tail -1 | tee -a logs/consolidate.log || echo "No baseline summary" | tee -a logs/consolidate.log
else
  echo "No baseline test log found" | tee -a logs/consolidate.log
fi

if [ -f logs/oracle.log ]; then
  echo "" | tee -a logs/consolidate.log
  echo "--- Oracle (Fixed) Test Results ---" | tee -a logs/consolidate.log
  # Try to find verifier logs in jobs directory
  VERIFIER_RESULT=$(find jobs -name "test-stdout.txt" -type f 2>/dev/null | head -n1)
  if [ -n "$VERIFIER_RESULT" ] && [ -f "$VERIFIER_RESULT" ]; then
    grep -E "(PASSED|FAILED|passed|failed)" "$VERIFIER_RESULT" | tail -1 | tee -a logs/consolidate.log || echo "No oracle test summary" | tee -a logs/consolidate.log
  else
    echo "No oracle verifier log found" | tee -a logs/consolidate.log
  fi
fi

echo "" | tee -a logs/consolidate.log
echo "Expected: Baseline should have ~5 failures, Oracle should have 0 failures" | tee -a logs/consolidate.log

if [ -d jobs ]; then
  echo "" | tee -a logs/consolidate.log
  echo "--- jobs/ tree ---" | tee -a logs/consolidate.log
  (find jobs -maxdepth 6 -print | head -n 200) | tee -a logs/consolidate.log || true

  echo "" | tee -a logs/consolidate.log
  echo "--- result.json files ---" | tee -a logs/consolidate.log
  (find jobs -name result.json -type f | sort | tail -n 50) | tee -a logs/consolidate.log || true
else
  echo "No jobs/ directory found" | tee -a logs/consolidate.log
fi
'''
      }
    }

    stage('Publish Logs to Git (optional)') {
      when {
        expression { return env.PUSH_LOGS_TO_GIT?.trim()?.toLowerCase() == 'true' }
      }
      steps {
        withCredentials([usernamePassword(credentialsId: 'github-user', usernameVariable: 'GITHUB_USERNAME', passwordVariable: 'GITHUB_TOKEN')]) {
          sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs

git config user.email "jenkins@local"
git config user.name "jenkins"

LOG_BRANCH="jenkins-logs"
git fetch origin "+refs/heads/${LOG_BRANCH}:refs/remotes/origin/${LOG_BRANCH}" || true
git checkout -B "${LOG_BRANCH}" || true
git add -A logs

if git diff --cached --quiet; then
  echo "No log changes to publish."
  exit 0
fi

git commit -m "chore(logs): ${JOB_NAME} #${BUILD_NUMBER} [skip ci]"

REPO_URL="$(git config --get remote.origin.url)"
if [[ "$REPO_URL" =~ ^git@github.com:(.+)$ ]]; then
  REPO_URL="github.com/${BASH_REMATCH[1]}"
elif [[ "$REPO_URL" =~ ^https?://(.+)$ ]]; then
  REPO_URL="${BASH_REMATCH[1]}"
fi

git push "https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@${REPO_URL}" "${LOG_BRANCH}:${LOG_BRANCH}"
'''
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'logs/**,jobs/**', allowEmptyArchive: true
    }
  }
}