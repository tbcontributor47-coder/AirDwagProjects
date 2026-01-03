pipeline {
    agent {
        docker {
            image "gnucobol:latest" // Assuming a standard GnuCOBOL image
            args "-v ${WORKSPACE}:/app -w /app"
        }
    }

    environment {
        TASK_NAME = "cobol-banking-engine"
    }

    stages {
        stage('Preflight') {
            steps {
                sh 'echo "Checking environment for ${TASK_NAME}..."'
                sh 'python3 --version'
                sh 'cobc --version'
            }
        }

        stage('Baseline Test (Buggy)') {
            steps {
                sh 'echo "Running baseline test (should fail logic checks)..."'
                sh 'bash tests/test.sh || true'
            }
        }

        stage('Fix and Verify') {
            steps {
                sh 'echo "Applying solution and verifying..."'
                sh 'bash solution/solve.sh'
                sh 'bash tests/test.sh'
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: '**/reports/*.txt, **/anomalies.dat, **/high_value.dat', allowEmptyArchive: true
        }
    }
}
