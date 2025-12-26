pipeline {
    agent any
    
    parameters {
        string(name: 'BRANCH_NAME', defaultValue: 'main', description: 'Branch to test')
        booleanParam(name: 'KEEP_TMPDIR', defaultValue: false, description: 'Keep temporary directory after build')
    }
    
    environment {
        TASK_NAME = 'eft-file-validation'
        TASK_BASE = "${WORKSPACE}/TerminalBench"
    }
    
    stages {
        stage('Preflight') {
            steps {
                script {
                    // Determine effective task path (prefer branch-named folder)
                    def branchName = params.BRANCH_NAME ?: env.BRANCH_NAME ?: 'main'
                    def taskPath = "${TASK_BASE}/${TASK_NAME}"
                    
                    if (branchName && branchName != 'main') {
                        def branchTaskPath = "${TASK_BASE}/${branchName}_${TASK_NAME}"
                        if (fileExists(branchTaskPath)) {
                            taskPath = branchTaskPath
                            echo "Using branch-specific task: ${branchTaskPath}"
                        }
                    }
                    
                    env.EFFECTIVE_TASK_PATH = taskPath
                    env.TASK_ABS = taskPath
                    
                    echo "Task path: ${env.EFFECTIVE_TASK_PATH}"
                    
                    // Create lowercase temporary directory for Harbor (Docker requires lowercase image names)
                    def taskBasename = new File(env.TASK_NAME).name.toLowerCase()
                    def randomSuffix = sh(script: "openssl rand -hex 4 2>/dev/null || cat /dev/urandom | tr -dc 'a-f0-9' | head -c 8", returnStdout: true).trim()
                    env.TMPDIR = "/tmp/${taskBasename}.${randomSuffix}"
                    
                    sh """
                        mkdir -p ${env.TMPDIR}
                        cp -r ${env.TASK_ABS}/* ${env.TMPDIR}/
                        echo "Working in temporary directory: ${env.TMPDIR}"
                    """
                }
            }
        }
        
        stage('Oracle (Solution)') {
            steps {
                script {
                    sh """
                        cd ${env.TMPDIR}
                        harbor run --task-dir . --solution-dir solution --output oracle_result.json
                    """
                    
                    // Validate oracle result
                    sh '''
                        python3 -c "
import json, sys
with open('${TMPDIR}/oracle_result.json') as f:
    result = json.load(f)
if result.get('n_errors', 1) != 0:
    print('Oracle validation failed!')
    sys.exit(1)
print('Oracle passed: {} records processed'.format(result.get('records_processed', 0)))
"
                    '''
                }
            }
        }
        
        stage('Agent Runs') {
            parallel {
                stage('GPT-4 Agent') {
                    steps {
                        script {
                            sh """
                                cd ${env.TMPDIR}
                                harbor run --task-dir . --agent gpt-4 --output agent_gpt4_result.json || true
                            """
                        }
                    }
                }
                stage('Claude Agent') {
                    steps {
                        script {
                            sh """
                                cd ${env.TMPDIR}
                                harbor run --task-dir . --agent claude --output agent_claude_result.json || true
                            """
                        }
                    }
                }
            }
        }
        
        stage('Difficulty Check') {
            steps {
                script {
                    sh """
                        cd ${env.TMPDIR}
                        harbor difficulty --task-dir . --runs 5 --output difficulty_result.json
                    """
                }
            }
        }
        
        stage('Consolidate') {
            steps {
                script {
                    sh """
                        cd ${env.TMPDIR}
                        python3 -c "
import json, glob
results = {}
for f in glob.glob('*_result.json'):
    with open(f) as fh:
        results[f] = json.load(fh)
with open('consolidated_results.json', 'w') as out:
    json.dump(results, out, indent=2)
print('Consolidated {} result files'.format(len(results)))
"
                    """
                }
            }
        }
        
        stage('Publish Logs') {
            steps {
                script {
                    // Copy results back to workspace
                    sh "cp ${env.TMPDIR}/*_result.json ${WORKSPACE}/ || true"
                    sh "cp ${env.TMPDIR}/consolidated_results.json ${WORKSPACE}/ || true"
                    
                    archiveArtifacts artifacts: '*_result.json', allowEmptyArchive: true
                    
                    echo "Results published to workspace"
                }
            }
        }
    }
    
    post {
        always {
            script {
                if (!params.KEEP_TMPDIR && env.TMPDIR) {
                    sh "rm -rf ${env.TMPDIR} || true"
                    echo "Cleaned up temporary directory"
                } else if (env.TMPDIR) {
                    echo "Temporary directory preserved: ${env.TMPDIR}"
                }
            }
        }
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check logs for details.'
        }
    }
}
