pipeline {
    agent {
        label 'Linux-01'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {
        booleanParam(name: 'RUN_ALL_MODES', defaultValue: true, description: 'Run oracle + GPT-5 + Claude (optional)')
        booleanParam(name: 'RUN_CODEX', defaultValue: false, description: 'Run GPT-5 agent run')
        booleanParam(name: 'RUN_CLAUDE', defaultValue: false, description: 'Run Claude Sonnet 4.5 agent run')
        booleanParam(name: 'KEEP_TMPDIR', defaultValue: false, description: 'Keep temporary task directories for debugging')
    }

    environment {
        TASK_PATH = '.'
        OPENAI_BASE_URL = 'https://api.portkey.ai/v1'
    }

    stages {
        stage('Preflight') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
echo "Node: $(hostname)"
echo "Task path: $TASK_PATH"
# Install Harbor CLI
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv tool install harbor==0.1.25 --python 3.13
export PATH="$HOME/.local/bin:$PATH"
harbor --help >/dev/null
'''
            }
        }

        stage('Baseline Test (Buggy)') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
TASK_ABS="$(pwd -P)"
IMAGE_NAME="reconcile-ledger-001:baseline"

echo "===== Building Docker image ====="
docker build -f "$TASK_ABS/environment/Dockerfile" -t "$IMAGE_NAME" "$TASK_ABS/environment"

echo "===== Running tests against BUGGY baseline ====="
docker run --rm \
    -v "$TASK_ABS/tests:/mnt/tests" \
    "$IMAGE_NAME" \
    /bin/bash -c "bash /mnt/tests/test.sh --junitxml=/mnt/tests/baseline-report.xml" \
    2>&1 | tee logs/baseline-test.log || true
'''
            }
        }

        stage('FixAndVerify') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
mkdir -p logs
TASK_ABS="$(pwd -P)"
IMAGE_NAME="reconcile-ledger-001:baseline"

echo "===== Applying solve.sh and re-testing ====="
docker run --rm \
    -v "$TASK_ABS/tests:/mnt/tests" \
    -v "$TASK_ABS/solution:/mnt/solution:ro" \
    "$IMAGE_NAME" \
    /bin/bash -c '
        set -euo pipefail
        bash /mnt/solution/solve.sh
        bash /mnt/tests/test.sh --junitxml=/mnt/tests/fix-report.xml
        cp /logs/verifier/reward.txt /mnt/tests/reward.txt || true
    ' \
    2>&1 | tee logs/fix-and-verify.log || true

if [ -f "$TASK_ABS/tests/fix-report.xml" ]; then
    cp "$TASK_ABS/tests/fix-report.xml" fix-report.xml
fi
'''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'fix-report.xml,logs/fix-and-verify.log', allowEmptyArchive: true
                    catchError(buildResult: 'SUCCESS', stageResult: 'SUCCESS') {
                        junit 'fix-report.xml'
                    }
                }
            }
        }

        stage('Harbor Checks') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
harbor tasks check . --model openai/@openai-tbench/gpt-5 2>&1 | tee logs/checks.log
'''
            }
        }

        stage('Oracle') {
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
harbor run --agent oracle --path . --force-build 2>&1 | tee logs/oracle.log
'''
            }
        }

        stage('Agent Runs') {
            when {
                expression { return params.RUN_ALL_MODES || params.RUN_CODEX || params.RUN_CLAUDE }
            }
            steps {
                sh '''#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
if [ "${RUN_ALL_MODES}" = "true" ] || [ "${RUN_CODEX}" = "true" ]; then
    harbor run -a terminus-2 -m openai/@openai-tbench/gpt-5 -p . 2>&1 | tee logs/agent-gpt5.log
fi
if [ "${RUN_ALL_MODES}" = "true" ] || [ "${RUN_CLAUDE}" = "true" ]; then
    harbor run -a terminus-2 -m openai/@anthropic-tbench/claude-sonnet-4-5-20250929 -p . 2>&1 | tee logs/agent-claude.log
fi
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
