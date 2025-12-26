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
  }

  environment {
    // This repo IS the Harbor task (root contains instruction.md, task.toml, etc)
    TASK_PATH = '.'
    OPENAI_BASE_URL = 'https://api.portkey.ai/v1'
    // Set to 'true' in Jenkins job env to push logs back to Git.
    PUSH_LOGS_TO_GIT = 'false'
  }

  stages {
    // `Prepare Workspace Permissions` stage removed — no ACL changes performed by Jenkins

    stage('Preflight') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

echo "Node: $(hostname)"
echo "Workspace: $WORKSPACE"
echo "User: $(id -un)"

# Multibranch support: if Jenkins sets BRANCH_NAME and a directory
# with that name exists at repo root, prefer it as the task path.
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
  echo ""
  echo "ERROR: Jenkins user cannot access Docker."
  echo "To fix: Add the agent service user to the docker group and restart the agent."
  echo "Example: sudo usermod -aG docker $(id -un) && sudo systemctl restart jenkins-agent"
  exit 1
fi

# Install Harbor CLI and ensure PATH
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

echo "--- ls -ld workspace (look for trailing '+' indicating ACLs) ---" | tee -a logs/permissions.log
ls -ld "$WORKSPACE" | tee -a logs/permissions.log || true

echo "--- ls -ld logs/ jobs/ (if present) ---" | tee -a logs/permissions.log
ls -ld "$WORKSPACE/logs" "$WORKSPACE/jobs" 2>/dev/null | tee -a logs/permissions.log || true

echo "--- numeric ownership (workspace) ---" | tee -a logs/permissions.log
ls -lan "$WORKSPACE" | head -n 50 | tee -a logs/permissions.log || true

echo "--- filesystem type/mount ---" | tee -a logs/permissions.log
df -Th "$WORKSPACE" | tee -a logs/permissions.log || true
mount | grep "$(df -P "$WORKSPACE" | tail -1 | awk '{print $1}')" -n | tee -a logs/permissions.log || true

if command -v getfacl >/dev/null 2>&1; then
  echo "--- getfacl (workspace) ---" | tee -a logs/permissions.log
  getfacl -p "$WORKSPACE" | tee logs/workspace.acl.txt | tee -a logs/permissions.log || true

  # Heuristic: extended ACLs show as named entries (user:<name>/group:<name>), a mask:, or default: entries.
  # Basic permissions always include user::, group::, other:: and should NOT be flagged.
  if ls -ld "$WORKSPACE" 2>/dev/null | awk '{print $1}' | grep -Fq '+'; then
    echo "NOTE: ls indicates ACLs (trailing '+')" | tee -a logs/permissions.log
  elif grep -Eq '^(default:|mask:|user:[^:]+:|group:[^:]+:)' logs/workspace.acl.txt; then
    echo "NOTE: workspace has extended ACL entries (see logs/workspace.acl.txt)" | tee -a logs/permissions.log
  else
    echo "NOTE: no extended ACL entries detected" | tee -a logs/permissions.log
  fi
else
  echo "NOTE: getfacl not installed; cannot print ACLs" | tee -a logs/permissions.log
fi

echo "===== End snapshot =====" | tee -a logs/permissions.log
'''
      }
    }

    stage('Oracle') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

export PATH="$HOME/.local/bin:$PATH"
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

# To avoid Docker image/tag errors from uppercase characters, copy the task
# to a temporary directory whose basename is lowercased and run Harbor from there.
TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

BASENAME="$(basename "$TASK_ABS")"
BASENAME_LC="$(echo "$BASENAME" | tr '[:upper:]' '[:lower:]')"
TMPDIR="$(mktemp -d /tmp/${BASENAME_LC}.XXXXXX)"
echo "Using temporary lowercase task dir: $TMPDIR"

# Copy files into TMPDIR preserving permissions; ignore failures but try to be robust.
rsync -a --exclude='.git' "$TASK_ABS/" "$TMPDIR/" || cp -a "$TASK_ABS/." "$TMPDIR/" || true

harbor run --agent oracle --path "$TMPDIR" --force-build 2>&1 | tee logs/oracle.log || true

RESULT_JSON="$(awk '/Results written to /{print $NF}' logs/oracle.log | tail -n1)"
if [ -z "$RESULT_JSON" ]; then
  # try to locate a result.json under jobs/
  RESULT_JSON="$(find jobs -name result.json | head -n1 || true)"
fi

if [ -z "$RESULT_JSON" ]; then
  echo "ERROR: Could not find result.json path in logs/oracle.log or jobs/"
  # keep the temporary dir for debugging
  echo "Temporary task dir left at: $TMPDIR"
  exit 1
fi

if [ ! -f "$RESULT_JSON" ] && [ -f "$WORKSPACE/$RESULT_JSON" ]; then
  RESULT_JSON="$WORKSPACE/$RESULT_JSON"
fi

if [ ! -f "$RESULT_JSON" ]; then
  echo "ERROR: Harbor result file not found: $RESULT_JSON"
  echo "Temporary task dir left at: $TMPDIR"
  exit 1
fi

echo ""
echo "========== Harbor Oracle result.json =========="
cat "$RESULT_JSON" || true
echo "========== Harbor Oracle job dir listing =========="
ls -la "$(dirname "$RESULT_JSON")" || true
echo "========== Harbor Oracle job.log =========="
cat "$(dirname "$RESULT_JSON")/job.log" || true
echo "========== Harbor Oracle trial directory =========="
TRIAL_DIR="$(find "$(dirname "$RESULT_JSON")" -mindepth 1 -maxdepth 1 -type d | head -n1)"
if [ -n "$TRIAL_DIR" ]; then
  echo "Trial dir: $TRIAL_DIR"
  ls -laR "$TRIAL_DIR" || true
  echo "--- Trial config.json ---"
  cat "$TRIAL_DIR/config.json" 2>/dev/null || echo "(no config.json)"
  echo "--- Agent oracle.txt ---"
  cat "$TRIAL_DIR/agent/oracle.txt" 2>/dev/null || echo "(no agent/oracle.txt)"
  echo "--- Trial stdout ---"
  cat "$TRIAL_DIR/stdout" 2>/dev/null || echo "(no stdout)"
  echo "--- Trial stderr ---"
  cat "$TRIAL_DIR/stderr" 2>/dev/null || echo "(no stderr)"
  echo "--- Test stdout (verifier/test-stdout.txt) ---"
  cat "$TRIAL_DIR/verifier/test-stdout.txt" 2>/dev/null || echo "(no test-stdout.txt)"
fi
echo "================================================="

# Cleanup temporary dir to avoid filling disk; keep for debugging if needed by setting
# KEEP_TMPDIR=true as a build parameter.
if [ "${KEEP_TMPDIR:-false}" != "true" ]; then
  rm -rf "$TMPDIR" || true
fi

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: python/python3 not found; cannot validate Harbor result.json"
  exit 1
fi

"$PYTHON_BIN" - "$RESULT_JSON" <<'PY'
import json
import sys

if len(sys.argv) < 2:
  print("ERROR: result.json path argument missing")
  sys.exit(1)

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
  data = json.load(f)

def max_errors(node):
  if isinstance(node, dict):
    m = 0
    for k, v in node.items():
      if isinstance(k, str) and k.lower() in ("n_errors", "errors"):
        try:
          m = max(m, int(v))
        except Exception:
          pass
      m = max(m, max_errors(v))
    return m
  if isinstance(node, list):
    return max((max_errors(x) for x in node), default=0)
  return 0

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
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"
harbor run --agent nop --path "$TASK_ABS" --force-build 2>&1 | tee logs/nop.log
'''
      }
    }

      stage('Checks') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

export PATH="$HOME/.local/bin:$PATH"
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
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
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

if [ "${RUN_ALL_MODES:-false}" = "true" ] || [ "${RUN_CODEX:-false}" = "true" ]; then
  echo "Running GPT-5 agent..."
  harbor run -a terminus-2 -m openai/@openai-tbench/gpt-5 -p "$TASK_ABS" 2>&1 | tee logs/agent-gpt5.log

  RESULT_JSON="$(awk '/Results written to /{print $NF}' logs/agent-gpt5.log | tail -n1)"
  if [ -z "$RESULT_JSON" ]; then
    echo "ERROR: Could not find result.json path in logs/agent-gpt5.log"
    exit 1
  fi
  if [ ! -f "$RESULT_JSON" ] && [ -f "$WORKSPACE/$RESULT_JSON" ]; then
    RESULT_JSON="$WORKSPACE/$RESULT_JSON"
  fi
  if [ ! -f "$RESULT_JSON" ]; then
    echo "ERROR: Harbor result file not found: $RESULT_JSON"
    exit 1
  fi

  echo ""
  echo "========== Harbor Agent (GPT-5) result.json =========="
  cat "$RESULT_JSON" || true
  echo "========== Harbor Agent (GPT-5) job dir listing =========="
  ls -la "$(dirname "$RESULT_JSON")" || true
  echo "========== Harbor Agent (GPT-5) job.log =========="
  cat "$(dirname "$RESULT_JSON")/job.log" || true
  echo "========== Harbor Agent (GPT-5) trial directory =========="
  TRIAL_DIR="$(find "$(dirname "$RESULT_JSON")" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  if [ -n "$TRIAL_DIR" ]; then
    echo "Trial dir: $TRIAL_DIR"
    ls -laR "$TRIAL_DIR" || true
    echo "--- Trial stdout ---"
    cat "$TRIAL_DIR/stdout" 2>/dev/null || echo "(no stdout)"
    echo "--- Trial stderr ---"
    cat "$TRIAL_DIR/stderr" 2>/dev/null || echo "(no stderr)"
  fi
  echo "========================================================"

  PYTHON_BIN="$(command -v python3 || command -v python || true)"
  if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: python/python3 not found; cannot validate Harbor result.json"
    exit 1
  fi

  "$PYTHON_BIN" - "$RESULT_JSON" <<'PY'
import json
import sys

if len(sys.argv) < 2:
    print("ERROR: result.json path argument missing")
    sys.exit(1)

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

def max_errors(node):
    if isinstance(node, dict):
        m = 0
        for k, v in node.items():
            if isinstance(k, str) and k.lower() in ("n_errors", "errors"):
                try:
                    m = max(m, int(v))
                except Exception:
                    pass
            m = max(m, max_errors(v))
        return m
    if isinstance(node, list):
        return max((max_errors(x) for x in node), default=0)
    return 0

err = max_errors(data)
print(f"Harbor reported errors: {err}")
sys.exit(1 if err > 0 else 0)
PY
fi

if [ "${RUN_ALL_MODES:-false}" = "true" ] || [ "${RUN_CLAUDE:-false}" = "true" ]; then
  echo "Running Claude Sonnet 4.5 agent..."
  harbor run -a terminus-2 -m openai/@anthropic-tbench/claude-sonnet-4-5-20250929 -p "$TASK_ABS" 2>&1 | tee logs/agent-claude.log

RESULT_JSON="$(awk '/Results written to /{print $NF}' logs/agent-claude.log | tail -n1)"
if [ -z "$RESULT_JSON" ]; then
  echo "ERROR: Could not find result.json path in logs/agent-claude.log"
  exit 1
fi
if [ ! -f "$RESULT_JSON" ] && [ -f "$WORKSPACE/$RESULT_JSON" ]; then
  RESULT_JSON="$WORKSPACE/$RESULT_JSON"
fi
if [ ! -f "$RESULT_JSON" ]; then
  echo "ERROR: Harbor result file not found: $RESULT_JSON"
  exit 1
fi

echo ""
echo "========== Harbor Agent (Claude) result.json =========="
cat "$RESULT_JSON" || true
echo "========== Harbor Agent (Claude) job dir listing =========="
ls -la "$(dirname "$RESULT_JSON")" || true
echo "========== Harbor Agent (Claude) job.log =========="
cat "$(dirname "$RESULT_JSON")/job.log" || true
echo "========== Harbor Agent (Claude) trial directory =========="
TRIAL_DIR="$(find "$(dirname "$RESULT_JSON")" -mindepth 1 -maxdepth 1 -type d | head -n1)"
if [ -n "$TRIAL_DIR" ]; then
  echo "Trial dir: $TRIAL_DIR"
  ls -laR "$TRIAL_DIR" || true
  echo "--- Trial stdout ---"
  cat "$TRIAL_DIR/stdout" 2>/dev/null || echo "(no stdout)"
  echo "--- Trial stderr ---"
  cat "$TRIAL_DIR/stderr" 2>/dev/null || echo "(no stderr)"
fi
echo "======================================================="

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: python/python3 not found; cannot validate Harbor result.json"
  exit 1
fi

"$PYTHON_BIN" - "$RESULT_JSON" <<'PY'
import json
import sys

if len(sys.argv) < 2:
    print("ERROR: result.json path argument missing")
    sys.exit(1)

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

def max_errors(node):
    if isinstance(node, dict):
        m = 0
        for k, v in node.items():
            if isinstance(k, str) and k.lower() in ("n_errors", "errors"):
                try:
                    m = max(m, int(v))
                except Exception:
                    pass
            m = max(m, max_errors(v))
        return m
    if isinstance(node, list):
        return max((max_errors(x) for x in node), default=0)
    return 0

err = max_errors(data)
print(f"Harbor reported errors: {err}")
sys.exit(1 if err > 0 else 0)
PY
fi
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
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

echo "===== Difficulty Check (5x each) =====" | tee logs/difficulty-5x.log

MODEL_GPT5="openai/@openai-tbench/gpt-5"
MODEL_CLAUDE="openai/@anthropic-tbench/claude-sonnet-4-5-20250929"

run_many() {
  local label="$1"
  local model="$2"
  local n="$3"
  local pass=0

  # NOTE: This function is called inside command substitution; send progress to stderr
  # so Jenkins streams it live, while stdout remains reserved for the final pass count.
  echo "" | tee -a logs/difficulty-5x.log >&2
  echo "--- $label ($model): ${n} runs ---" | tee -a logs/difficulty-5x.log >&2

  for i in $(seq 1 "$n"); do
    echo "Run ${i}/${n}: $label" | tee -a logs/difficulty-5x.log >&2
    harbor run -a terminus-2 -m "$model" -p "$TASK_ABS" 2>&1 | tee "logs/difficulty-${label}-${i}.log" >&2

    RESULT_JSON="$(awk '/Results written to /{print $NF}' "logs/difficulty-${label}-${i}.log" | tail -n1)"
    if [ -z "$RESULT_JSON" ]; then
      echo "ERROR: Could not find result.json path in logs/difficulty-${label}-${i}.log" | tee -a logs/difficulty-5x.log >&2
      continue
    fi
    if [ ! -f "$RESULT_JSON" ] && [ -f "$WORKSPACE/$RESULT_JSON" ]; then
      RESULT_JSON="$WORKSPACE/$RESULT_JSON"
    fi
    if [ ! -f "$RESULT_JSON" ]; then
      echo "ERROR: Harbor result file not found: $RESULT_JSON" | tee -a logs/difficulty-5x.log >&2
      continue
    fi

    # Extract the eval mean (single-trial reward) from result.json.
    MEAN="$(python3 - "$RESULT_JSON" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

stats = data.get('stats', {})
evals = stats.get('evals', {}) if isinstance(stats, dict) else {}
if isinstance(evals, dict) and evals:
    first_eval = next(iter(evals.values()))
    if isinstance(first_eval, dict):
        metrics = first_eval.get('metrics')
        if isinstance(metrics, list) and metrics and isinstance(metrics[0], dict) and 'mean' in metrics[0]:
            print(metrics[0]['mean'])
            raise SystemExit(0)

# Fallback: scan for numeric 'mean' fields.
def scan_means(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == 'mean' and isinstance(v, (int, float)):
                yield v
            yield from scan_means(v)
    elif isinstance(node, list):
        for x in node:
            yield from scan_means(x)

means = list(scan_means(data))
if means:
    print(means[0])
else:
    print('')
PY
) 2>/dev/null)"

    if [ "$MEAN" = "1" ] || [ "$MEAN" = "1.0" ]; then
      pass=$((pass + 1))
      echo "  result: PASS (mean=$MEAN)" | tee -a logs/difficulty-5x.log >&2
    else
      echo "  result: FAIL (mean=${MEAN:-?})" | tee -a logs/difficulty-5x.log >&2
    fi
  done

  echo "$pass"  # stdout-only return value
}

PASS_GPT5="$(run_many gpt5 "$MODEL_GPT5" 5 | tail -n1)"
PASS_CLAUDE="$(run_many claude "$MODEL_CLAUDE" 5 | tail -n1)"

echo "" | tee -a logs/difficulty-5x.log
echo "===== Summary =====" | tee -a logs/difficulty-5x.log
echo "GPT-5:   ${PASS_GPT5}/5 pass" | tee -a logs/difficulty-5x.log
echo "Claude:  ${PASS_CLAUDE}/5 pass" | tee -a logs/difficulty-5x.log

# Do not fail the build here; this stage is informational.
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
echo "Task path: $TASK_PATH" | tee -a logs/consolidate.log

if [ -d jobs ]; then
  echo "" | tee -a logs/consolidate.log
  echo "--- jobs/ tree (top 200 lines) ---" | tee -a logs/consolidate.log
  # NOTE: `head` can trigger SIGPIPE in upstream commands; do not fail the build on that.
  (find jobs -maxdepth 6 -print | sed 's#^#jobs:#' | head -n 200) | tee -a logs/consolidate.log || true

  echo "" | tee -a logs/consolidate.log
  echo "--- result.json files (up to 50) ---" | tee -a logs/consolidate.log
  (find jobs -name result.json -type f | sort | tail -n 50) | tee -a logs/consolidate.log || true

  echo "" | tee -a logs/consolidate.log
  echo "--- last job.log (if any) ---" | tee -a logs/consolidate.log
  LAST_JOB_LOG="$(find jobs -name job.log -type f | sort | tail -n 1)"
  if [ -n "$LAST_JOB_LOG" ]; then
    echo "Last job.log: $LAST_JOB_LOG" | tee -a logs/consolidate.log
    tail -n 200 "$LAST_JOB_LOG" | tee -a logs/consolidate.log || true
  else
    echo "No job.log found under jobs/" | tee -a logs/consolidate.log
  fi
else
  echo "No jobs/ directory found (nothing to consolidate)." | tee -a logs/consolidate.log
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

git status --porcelain

git config user.email "jenkins@local"
git config user.name "jenkins"

# Push logs to a dedicated branch to avoid triggering your main pipeline.
LOG_BRANCH="jenkins-logs"

git fetch origin "+refs/heads/${LOG_BRANCH}:refs/remotes/origin/${LOG_BRANCH}" || true
git checkout -B "${LOG_BRANCH}" || true

git add -A logs

if git diff --cached --quiet; then
  echo "No log changes to publish."
  exit 0
fi

git commit -m "chore(logs): ${JOB_NAME} #${BUILD_NUMBER} [skip ci]"

# Use token auth for push
REPO_URL="$(git config --get remote.origin.url)"

# Normalize to https host/path
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
  }

  environment {
    // This repo IS the Harbor task (root contains instruction.md, task.toml, etc)
    TASK_PATH = '.'
    OPENAI_BASE_URL = 'https://api.portkey.ai/v1'
    // Set to 'true' in Jenkins job env to push logs back to Git.
    PUSH_LOGS_TO_GIT = 'false'
  }

  stages {
    // `Prepare Workspace Permissions` stage removed — no ACL changes performed by Jenkins

    stage('Preflight') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

echo "Node: $(hostname)"
echo "Workspace: $WORKSPACE"
echo "User: $(id -un)"

echo "Task path: $TASK_PATH"
if ! TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"; then
  echo "ERROR: TASK_PATH cannot be resolved from WORKSPACE"
  echo "WORKSPACE: $WORKSPACE"
  echo "TASK_PATH: $TASK_PATH"
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
  echo ""
  echo "ERROR: Jenkins user cannot access Docker."
  echo "To fix: Add the agent service user to the docker group and restart the agent."
  echo "Example: sudo usermod -aG docker $(id -un) && sudo systemctl restart jenkins-agent"
  exit 1
fi

# Install Harbor CLI and ensure PATH
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
echo "User: $(id)" | tee -a logs/permissions.log
echo "Umask: $(umask)" | tee -a logs/permissions.log
echo "Workspace: $WORKSPACE" | tee -a logs/permissions.log

echo "--- ls -ld workspace (look for trailing '+' indicating ACLs) ---" | tee -a logs/permissions.log
ls -ld "$WORKSPACE" | tee -a logs/permissions.log || true

echo "--- ls -ld logs/ jobs/ (if present) ---" | tee -a logs/permissions.log
ls -ld "$WORKSPACE/logs" "$WORKSPACE/jobs" 2>/dev/null | tee -a logs/permissions.log || true

echo "--- numeric ownership (workspace) ---" | tee -a logs/permissions.log
ls -lan "$WORKSPACE" | head -n 50 | tee -a logs/permissions.log || true

echo "--- filesystem type/mount ---" | tee -a logs/permissions.log
df -Th "$WORKSPACE" | tee -a logs/permissions.log || true
mount | grep "$(df -P "$WORKSPACE" | tail -1 | awk '{print $1}')" -n | tee -a logs/permissions.log || true

if command -v getfacl >/dev/null 2>&1; then
  echo "--- getfacl (workspace) ---" | tee -a logs/permissions.log
  getfacl -p "$WORKSPACE" | tee logs/workspace.acl.txt | tee -a logs/permissions.log || true

  # Heuristic: extended ACLs show as named entries (user:<name>/group:<name>), a mask:, or default: entries.
  # Basic permissions always include user::, group::, other:: and should NOT be flagged.
  if ls -ld "$WORKSPACE" 2>/dev/null | awk '{print $1}' | grep -Fq '+'; then
    echo "NOTE: ls indicates ACLs (trailing '+')" | tee -a logs/permissions.log
  elif grep -Eq '^(default:|mask:|user:[^:]+:|group:[^:]+:)' logs/workspace.acl.txt; then
    echo "NOTE: workspace has extended ACL entries (see logs/workspace.acl.txt)" | tee -a logs/permissions.log
  else
    echo "NOTE: no extended ACL entries detected" | tee -a logs/permissions.log
  fi
else
  echo "NOTE: getfacl not installed; cannot print ACLs" | tee -a logs/permissions.log
fi

echo "===== End snapshot =====" | tee -a logs/permissions.log
'''
      }
    }

    stage('Oracle') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

export PATH="$HOME/.local/bin:$PATH"
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"
harbor run --agent oracle --path "$TASK_ABS" --force-build 2>&1 | tee logs/oracle.log

RESULT_JSON="$(awk '/Results written to /{print $NF}' logs/oracle.log | tail -n1)"
if [ -z "$RESULT_JSON" ]; then
  echo "ERROR: Could not find result.json path in logs/oracle.log"
  exit 1
fi

if [ ! -f "$RESULT_JSON" ] && [ -f "$WORKSPACE/$RESULT_JSON" ]; then
  RESULT_JSON="$WORKSPACE/$RESULT_JSON"
fi

if [ ! -f "$RESULT_JSON" ]; then
  echo "ERROR: Harbor result file not found: $RESULT_JSON"
  exit 1
fi

echo ""
echo "========== Harbor Oracle result.json =========="
cat "$RESULT_JSON" || true
echo "========== Harbor Oracle job dir listing =========="
ls -la "$(dirname "$RESULT_JSON")" || true
echo "========== Harbor Oracle job.log =========="
cat "$(dirname "$RESULT_JSON")/job.log" || true
echo "========== Harbor Oracle trial directory =========="
TRIAL_DIR="$(find "$(dirname "$RESULT_JSON")" -mindepth 1 -maxdepth 1 -type d | head -n1)"
if [ -n "$TRIAL_DIR" ]; then
  echo "Trial dir: $TRIAL_DIR"
  ls -laR "$TRIAL_DIR" || true
  echo "--- Trial config.json ---"
  cat "$TRIAL_DIR/config.json" 2>/dev/null || echo "(no config.json)"
  echo "--- Agent oracle.txt ---"
  cat "$TRIAL_DIR/agent/oracle.txt" 2>/dev/null || echo "(no agent/oracle.txt)"
  echo "--- Trial stdout ---"
  cat "$TRIAL_DIR/stdout" 2>/dev/null || echo "(no stdout)"
  echo "--- Trial stderr ---"
  cat "$TRIAL_DIR/stderr" 2>/dev/null || echo "(no stderr)"
  echo "--- Test stdout (verifier/test-stdout.txt) ---"
  cat "$TRIAL_DIR/verifier/test-stdout.txt" 2>/dev/null || echo "(no test-stdout.txt)"
fi
echo "================================================="

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: python/python3 not found; cannot validate Harbor result.json"
  exit 1
fi

"$PYTHON_BIN" - "$RESULT_JSON" <<'PY'
import json
import sys

if len(sys.argv) < 2:
    print("ERROR: result.json path argument missing")
    sys.exit(1)

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

def max_errors(node):
    if isinstance(node, dict):
        m = 0
        for k, v in node.items():
            if isinstance(k, str) and k.lower() in ("n_errors", "errors"):
                try:
                    m = max(m, int(v))
                except Exception:
                    pass
            m = max(m, max_errors(v))
        return m
    if isinstance(node, list):
        return max((max_errors(x) for x in node), default=0)
    return 0

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
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"
harbor run --agent nop --path "$TASK_ABS" --force-build 2>&1 | tee logs/nop.log
'''
      }
    }

      stage('Checks') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs

export PATH="$HOME/.local/bin:$PATH"
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
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
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

if [ "${RUN_ALL_MODES:-false}" = "true" ] || [ "${RUN_CODEX:-false}" = "true" ]; then
  echo "Running GPT-5 agent..."
  harbor run -a terminus-2 -m openai/@openai-tbench/gpt-5 -p "$TASK_ABS" 2>&1 | tee logs/agent-gpt5.log

  RESULT_JSON="$(awk '/Results written to /{print $NF}' logs/agent-gpt5.log | tail -n1)"
  if [ -z "$RESULT_JSON" ]; then
    echo "ERROR: Could not find result.json path in logs/agent-gpt5.log"
    exit 1
  fi
  if [ ! -f "$RESULT_JSON" ] && [ -f "$WORKSPACE/$RESULT_JSON" ]; then
    RESULT_JSON="$WORKSPACE/$RESULT_JSON"
  fi
  if [ ! -f "$RESULT_JSON" ]; then
    echo "ERROR: Harbor result file not found: $RESULT_JSON"
    exit 1
  fi

  echo ""
  echo "========== Harbor Agent (GPT-5) result.json =========="
  cat "$RESULT_JSON" || true
  echo "========== Harbor Agent (GPT-5) job dir listing =========="
  ls -la "$(dirname "$RESULT_JSON")" || true
  echo "========== Harbor Agent (GPT-5) job.log =========="
  cat "$(dirname "$RESULT_JSON")/job.log" || true
  echo "========== Harbor Agent (GPT-5) trial directory =========="
  TRIAL_DIR="$(find "$(dirname "$RESULT_JSON")" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  if [ -n "$TRIAL_DIR" ]; then
    echo "Trial dir: $TRIAL_DIR"
    ls -laR "$TRIAL_DIR" || true
    echo "--- Trial stdout ---"
    cat "$TRIAL_DIR/stdout" 2>/dev/null || echo "(no stdout)"
    echo "--- Trial stderr ---"
    cat "$TRIAL_DIR/stderr" 2>/dev/null || echo "(no stderr)"
  fi
  echo "========================================================"

  PYTHON_BIN="$(command -v python3 || command -v python || true)"
  if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: python/python3 not found; cannot validate Harbor result.json"
    exit 1
  fi

  "$PYTHON_BIN" - "$RESULT_JSON" <<'PY'
import json
import sys

if len(sys.argv) < 2:
    print("ERROR: result.json path argument missing")
    sys.exit(1)

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

def max_errors(node):
    if isinstance(node, dict):
        m = 0
        for k, v in node.items():
            if isinstance(k, str) and k.lower() in ("n_errors", "errors"):
                try:
                    m = max(m, int(v))
                except Exception:
                    pass
            m = max(m, max_errors(v))
        return m
    if isinstance(node, list):
        return max((max_errors(x) for x in node), default=0)
    return 0

err = max_errors(data)
print(f"Harbor reported errors: {err}")
sys.exit(1 if err > 0 else 0)
PY
fi

if [ "${RUN_ALL_MODES:-false}" = "true" ] || [ "${RUN_CLAUDE:-false}" = "true" ]; then
  echo "Running Claude Sonnet 4.5 agent..."
  harbor run -a terminus-2 -m openai/@anthropic-tbench/claude-sonnet-4-5-20250929 -p "$TASK_ABS" 2>&1 | tee logs/agent-claude.log

RESULT_JSON="$(awk '/Results written to /{print $NF}' logs/agent-claude.log | tail -n1)"
if [ -z "$RESULT_JSON" ]; then
  echo "ERROR: Could not find result.json path in logs/agent-claude.log"
  exit 1
fi
if [ ! -f "$RESULT_JSON" ] && [ -f "$WORKSPACE/$RESULT_JSON" ]; then
  RESULT_JSON="$WORKSPACE/$RESULT_JSON"
fi
if [ ! -f "$RESULT_JSON" ]; then
  echo "ERROR: Harbor result file not found: $RESULT_JSON"
  exit 1
fi

echo ""
echo "========== Harbor Agent (Claude) result.json =========="
cat "$RESULT_JSON" || true
echo "========== Harbor Agent (Claude) job dir listing =========="
ls -la "$(dirname "$RESULT_JSON")" || true
echo "========== Harbor Agent (Claude) job.log =========="
cat "$(dirname "$RESULT_JSON")/job.log" || true
echo "========== Harbor Agent (Claude) trial directory =========="
TRIAL_DIR="$(find "$(dirname "$RESULT_JSON")" -mindepth 1 -maxdepth 1 -type d | head -n1)"
if [ -n "$TRIAL_DIR" ]; then
  echo "Trial dir: $TRIAL_DIR"
  ls -laR "$TRIAL_DIR" || true
  echo "--- Trial stdout ---"
  cat "$TRIAL_DIR/stdout" 2>/dev/null || echo "(no stdout)"
  echo "--- Trial stderr ---"
  cat "$TRIAL_DIR/stderr" 2>/dev/null || echo "(no stderr)"
fi
echo "======================================================="

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: python/python3 not found; cannot validate Harbor result.json"
  exit 1
fi

"$PYTHON_BIN" - "$RESULT_JSON" <<'PY'
import json
import sys

if len(sys.argv) < 2:
    print("ERROR: result.json path argument missing")
    sys.exit(1)

path = sys.argv[1]

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

def max_errors(node):
    if isinstance(node, dict):
        m = 0
        for k, v in node.items():
            if isinstance(k, str) and k.lower() in ("n_errors", "errors"):
                try:
                    m = max(m, int(v))
                except Exception:
                    pass
            m = max(m, max_errors(v))
        return m
    if isinstance(node, list):
        return max((max_errors(x) for x in node), default=0)
    return 0

err = max_errors(data)
print(f"Harbor reported errors: {err}")
sys.exit(1 if err > 0 else 0)
PY
fi
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
if [ -f "$HOME/.local/bin/env" ]; then
  source "$HOME/.local/bin/env"
fi

command -v harbor >/dev/null || { echo "harbor not found in PATH (did Preflight run?)"; exit 127; }

TASK_ABS="$(cd "$WORKSPACE/$TASK_PATH" 2>/dev/null && pwd -P)"
echo "Task absolute path: $TASK_ABS"

echo "===== Difficulty Check (5x each) =====" | tee logs/difficulty-5x.log

MODEL_GPT5="openai/@openai-tbench/gpt-5"
MODEL_CLAUDE="openai/@anthropic-tbench/claude-sonnet-4-5-20250929"

run_many() {
  local label="$1"
  local model="$2"
  local n="$3"
  local pass=0

  # NOTE: This function is called inside command substitution; send progress to stderr
  # so Jenkins streams it live, while stdout remains reserved for the final pass count.
  echo "" | tee -a logs/difficulty-5x.log >&2
  echo "--- $label ($model): ${n} runs ---" | tee -a logs/difficulty-5x.log >&2

  for i in $(seq 1 "$n"); do
    echo "Run ${i}/${n}: $label" | tee -a logs/difficulty-5x.log >&2
    harbor run -a terminus-2 -m "$model" -p "$TASK_ABS" 2>&1 | tee "logs/difficulty-${label}-${i}.log" >&2

    RESULT_JSON="$(awk '/Results written to /{print $NF}' "logs/difficulty-${label}-${i}.log" | tail -n1)"
    if [ -z "$RESULT_JSON" ]; then
      echo "ERROR: Could not find result.json path in logs/difficulty-${label}-${i}.log" | tee -a logs/difficulty-5x.log >&2
      continue
    fi
    if [ ! -f "$RESULT_JSON" ] && [ -f "$WORKSPACE/$RESULT_JSON" ]; then
      RESULT_JSON="$WORKSPACE/$RESULT_JSON"
    fi
    if [ ! -f "$RESULT_JSON" ]; then
      echo "ERROR: Harbor result file not found: $RESULT_JSON" | tee -a logs/difficulty-5x.log >&2
      continue
    fi

    # Extract the eval mean (single-trial reward) from result.json.
    MEAN="$(python3 - "$RESULT_JSON" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

stats = data.get('stats', {})
evals = stats.get('evals', {}) if isinstance(stats, dict) else {}
if isinstance(evals, dict) and evals:
    first_eval = next(iter(evals.values()))
    if isinstance(first_eval, dict):
        metrics = first_eval.get('metrics')
        if isinstance(metrics, list) and metrics and isinstance(metrics[0], dict) and 'mean' in metrics[0]:
            print(metrics[0]['mean'])
            raise SystemExit(0)

# Fallback: scan for numeric 'mean' fields.
def scan_means(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == 'mean' and isinstance(v, (int, float)):
                yield v
            yield from scan_means(v)
    elif isinstance(node, list):
        for x in node:
            yield from scan_means(x)

means = list(scan_means(data))
if means:
    print(means[0])
else:
    print('')
PY
) 2>/dev/null)"

    if [ "$MEAN" = "1" ] || [ "$MEAN" = "1.0" ]; then
      pass=$((pass + 1))
      echo "  result: PASS (mean=$MEAN)" | tee -a logs/difficulty-5x.log >&2
    else
      echo "  result: FAIL (mean=${MEAN:-?})" | tee -a logs/difficulty-5x.log >&2
    fi
  done

  echo "$pass"  # stdout-only return value
}

PASS_GPT5="$(run_many gpt5 "$MODEL_GPT5" 5 | tail -n1)"
PASS_CLAUDE="$(run_many claude "$MODEL_CLAUDE" 5 | tail -n1)"

echo "" | tee -a logs/difficulty-5x.log
echo "===== Summary =====" | tee -a logs/difficulty-5x.log
echo "GPT-5:   ${PASS_GPT5}/5 pass" | tee -a logs/difficulty-5x.log
echo "Claude:  ${PASS_CLAUDE}/5 pass" | tee -a logs/difficulty-5x.log

# Do not fail the build here; this stage is informational.
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
echo "Task path: $TASK_PATH" | tee -a logs/consolidate.log

if [ -d jobs ]; then
  echo "" | tee -a logs/consolidate.log
  echo "--- jobs/ tree (top 200 lines) ---" | tee -a logs/consolidate.log
  # NOTE: `head` can trigger SIGPIPE in upstream commands; do not fail the build on that.
  (find jobs -maxdepth 6 -print | sed 's#^#jobs:#' | head -n 200) | tee -a logs/consolidate.log || true

  echo "" | tee -a logs/consolidate.log
  echo "--- result.json files (up to 50) ---" | tee -a logs/consolidate.log
  (find jobs -name result.json -type f | sort | tail -n 50) | tee -a logs/consolidate.log || true

  echo "" | tee -a logs/consolidate.log
  echo "--- last job.log (if any) ---" | tee -a logs/consolidate.log
  LAST_JOB_LOG="$(find jobs -name job.log -type f | sort | tail -n 1)"
  if [ -n "$LAST_JOB_LOG" ]; then
    echo "Last job.log: $LAST_JOB_LOG" | tee -a logs/consolidate.log
    tail -n 200 "$LAST_JOB_LOG" | tee -a logs/consolidate.log || true
  else
    echo "No job.log found under jobs/" | tee -a logs/consolidate.log
  fi
else
  echo "No jobs/ directory found (nothing to consolidate)." | tee -a logs/consolidate.log
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

git status --porcelain

git config user.email "jenkins@local"
git config user.name "jenkins"

# Push logs to a dedicated branch to avoid triggering your main pipeline.
LOG_BRANCH="jenkins-logs"

git fetch origin "+refs/heads/${LOG_BRANCH}:refs/remotes/origin/${LOG_BRANCH}" || true
git checkout -B "${LOG_BRANCH}" || true

git add -A logs

if git diff --cached --quiet; then
  echo "No log changes to publish."
  exit 0
fi

git commit -m "chore(logs): ${JOB_NAME} #${BUILD_NUMBER} [skip ci]"

# Use token auth for push
REPO_URL="$(git config --get remote.origin.url)"

# Normalize to https host/path
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
