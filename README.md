# Jenkins Multibranch Pipeline Setup — terraform-drift-audit

This document explains how to configure a Jenkins *Multibranch Pipeline* that will pick up the `Jenkinsfile` included in this task folder and run the pipeline for branches that match task folder names (i.e. `terraform-drift-audit`).

Goal
- Allow Jenkins to discover and run the pipeline defined in `terraform-drift-audit/Jenkinsfile` when a branch with the same name as the task folder exists in the repository.

Key requirements
- A Jenkins controller/agent with Docker access (agents must be able to run `docker` if the pipeline uses Docker).
- Credentials:
  - GitHub (or Git provider) credential with push/read access (used by Jenkins to scan branches).
  - Optional `OPENAI_API_KEY` (or equivalent) stored as a Jenkins secret if you plan to run agent stages that call external APIs.
  - Optional `github-user` credential (username/password or token) if you want the pipeline to push logs back to the repo (see `PUSH_LOGS_TO_GIT` in the `Jenkinsfile`).

Overview — Multibranch behavior
- Jenkins Multibranch Pipeline scans the repository for branches and automatically creates per-branch jobs.
- Our `Jenkinsfile` supports a branch-named task folder: if the pipeline runs on branch `terraform-drift-audit` and a folder named `terraform-drift-audit` exists at the repo root, that folder is used as the task path.

UI — Create a Multibranch Pipeline (recommended)
1. In Jenkins, click: New Item → enter a name (e.g. `TerminalBench-tasks`) → select **Multibranch Pipeline** → OK.
2. Under **Branch Sources** click **Add source → Git** (or use GitHub/GitLab provider plugin).
   - Repository URL: `https://github.com/<owner>/<repo>.git` (replace with your repo).
   - Credentials: add/select the credential that has read access.
3. Under **Behaviors** (optional): choose discovery strategies (e.g. discover branches, discover pull requests).
4. Save and run **Scan Multibranch Pipeline Now**. Jenkins will create per-branch jobs that run `Jenkinsfile` from the branch root.

REST API / scripted creation (PowerShell example)
Below is an example PowerShell snippet that creates a Multibranch Pipeline job using Jenkins' REST API. It assumes:
- You have admin access to Jenkins and an account with API token.
- The Jenkins server requires a crumb (CSRF protection). The snippet fetches a crumb first.

Replace the placeholders: `$JENKINS_URL`, `$JOB_NAME`, `$JENKINS_USER`, `$JENKINS_TOKEN`, and the repo URL.

```powershell
#$JENKINS_URL: e.g. http://jenkins.example.local:8080
#$JOB_NAME: desired job name (no spaces recommended)
#$JENKINS_USER / $JENKINS_TOKEN: Jenkins user and API token

$JENKINS_URL = 'http://jenkins.example.local:8080'
$JOB_NAME = 'TerminalBench-tasks'
$JENKINS_USER = 'jenkins-user'
$JENKINS_TOKEN = 'your-api-token'
$REPO_URL = 'https://github.com/Manoj-Kumar-Selvaraj/Portfolio.git'

# get crumb
$crumbData = Invoke-RestMethod -Uri "$JENKINS_URL/crumbIssuer/api/json" -Credential (New-Object System.Management.Automation.PSCredential($JENKINS_USER,(ConvertTo-SecureString $JENKINS_TOKEN -AsPlainText -Force)))
$crumb = $crumbData.crumb
$crumbField = $crumbData.crumbRequestField

# Minimal Multibranch job config XML (adjust SCM settings/plugin as needed)
$configXml = @"
<com.cloudbees.hudson.plugins.folder.Folder plugin="cloudbees-folder@6.15">
  <actions/>
  <description>TerminalBench multibranch for tasks</description>
  <properties/>
</com.cloudbees.hudson.plugins.folder.Folder>
"@

# Create the folder (if your Jenkins supports Job DSL, you can create Multibranch more flexibly)
Invoke-RestMethod -Uri "$JENKINS_URL/createItem?name=$JOB_NAME" -Method Post -Body $configXml -ContentType 'application/xml' -Headers @{ $crumbField = $crumb } -Credential (New-Object System.Management.Automation.PSCredential($JENKINS_USER,(ConvertTo-SecureString $JENKINS_TOKEN -AsPlainText -Force)))

Write-Host 'Created folder job. Now visit the UI to add a Multibranch Pipeline inside it (Branch Sources→Git).' -ForegroundColor Green
```

Notes: creating a full Multibranch Pipeline entirely via XML is possible but depends on installed SCM/branch source plugins (GitHub Branch Source, GitLab Branch Source, Bitbucket Branch Source). Using the UI or Job DSL plugin is usually easier.

Push the branch (so Jenkins discovers the branch and the `Jenkinsfile` in it)
1. Create a local branch named exactly like the task folder (example: `terraform-drift-audit`).
2. Ensure the branch contains the `terraform-drift-audit/Jenkinsfile` at the path you expect (already present in `main`/current branch, but Multibranch reads from the branch root; pushing a branch with the same folder keeps behavior predictable).

PowerShell (Git) example — create and push a branch:
```powershell
git checkout -b terraform-drift-audit
git add TerminalBench/terraform-drift-audit/Jenkinsfile TerminalBench/terraform-drift-audit/*.md || true
git commit -m "chore(ci): add Jenkinsfile for terraform-drift-audit"
git push -u origin terraform-drift-audit
```

What to configure in Jenkins for this repo
- `Credentials` → Add:
  - Git credential (username/token) used as Branch Source credential.
  - `OPENAI_API_KEY` (as a secret text credential) if you plan to run agent stages that call external APIs.
  - (Optional) `github-user` username/password or personal access token for `PUSH_LOGS_TO_GIT=true` functionality.
- In the Multibranch job: set **Property strategy** or **Filter by name** if you want to restrict which branches are built.

Validating/Testing the pipeline
1. After creating the Multibranch Pipeline and pushing the branch, run **Scan Multibranch Pipeline Now** in Jenkins. A per-branch job should appear, and you can inspect the job's latest build logs.
2. If builds fail early with errors like "docker: cannot connect to the docker daemon", ensure the Jenkins agent/node running the job has Docker installed and the Jenkins user is in the `docker` group.

Troubleshooting tips
- If Jenkins cannot fetch branches, double-check branch source credentials and repo URL.
- If the job finds the branch but cannot find the task folder, ensure the branch contains the folder at root (e.g. `TerminalBench/terraform-drift-audit`) and that the `Jenkinsfile` exists at `TerminalBench/terraform-drift-audit/Jenkinsfile` or at repo root depending on your job's working-directory assumptions. Our `Jenkinsfile` uses the repo root by default and prefers a branch-named folder when present.
- If you want a simpler path (no folder indirection), you can move the `Jenkinsfile` to the repo root for that branch.

Next steps I can do for you
- Help generate a Job DSL or full job `config.xml` to create the Multibranch Pipeline programmatically (requires knowledge of installed plugins).
- Help craft the exact set of credentials and scopes for GitHub/GitLab to minimize permissions.
- If you provide Jenkins admin access details (not recommended here), I can show exact REST calls to create the full job.

---
File created by the local helper: `terraform-drift-audit/README.md`
