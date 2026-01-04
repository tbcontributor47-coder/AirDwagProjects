# Task: Kubernetes CrashLoopBackOff Debugging

## Scenario
A new microservice `order-processor` has been deployed to the Kubernetes cluster, but it's failing to stay healthy. The pods are entering a `CrashLoopBackOff` state. Your job is to find the configuration errors and fix them.

## Requirements
1.  **Liveness Probe:** The liveness probe is pointing to an incorrect port or path. Fix it so it correctly monitors the application's health.
2.  **Environment Variables:** The application requires a `DB_CONNECTION_STRING` environment variable to start, which is currently missing from the deployment spec.
3.  **Stability:** After applying the fixes, the deployment should have all replicas in a `Running` and `Ready` state.

## Instructions
- Examine the files in `environment/`.
- Fix `deployment.yaml` and any other configuration issues you find.
- Verify your container build in the `Dockerfile`.
- Run `tests/test.sh` to validate the fix.

## Hints
- Check the `port` in the `livenessProbe` section.
- Ensure the application's entrypoint script is actually executable.
