pipeline {
    agent {
        label 'Linux-01'
    }

    environment {
        TASK_PATH = 'cobol-banking-engine'
    }

    stages {
        stage('Preflight') {
            steps {
                sh 'echo "Node: $(hostname)"'
            }
        }

        stage('Baseline Test (Buggy)') {
            steps {
                sh '''#!/usr/bin/env bash
                set -euo pipefail
                TASK_ABS="$WORKSPACE/$TASK_PATH"
                IMAGE_NAME="cobol-banking:baseline"
                docker build -f "$TASK_ABS/environment/Dockerfile" -t "$IMAGE_NAME" "$TASK_ABS/environment"
                docker run --rm -v "$TASK_ABS/tests:/app/tests" "$IMAGE_NAME" /bin/bash -c "bash /app/tests/test.sh" || true
                '''
            }
        }

        stage('Fix and Verify') {
            steps {
                sh '''#!/usr/bin/env bash
                set -euo pipefail
                TASK_ABS="$WORKSPACE/$TASK_PATH"
                IMAGE_NAME="cobol-banking:baseline"
                docker run --rm \
                    -v "$TASK_ABS/tests:/app/tests" \
                    -v "$TASK_ABS/solution:/mnt/solution:ro" \
                    "$IMAGE_NAME" \
                    /bin/bash -c "bash /mnt/solution/solve.sh && bash /app/tests/test.sh"
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: '**/reports/*.txt, **/anomalies.dat, **/high_value.dat', allowEmptyArchive: true
        }
    }
}
