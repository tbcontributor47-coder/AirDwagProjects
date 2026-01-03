# AWS Observability Stack - Configuration Fix

## Background

Your company runs a microservices platform on AWS, and the observability stack is broken. The monitoring, logging, and alerting pipeline has multiple configuration issues that prevent proper visibility into system health.

The stack consists of:
- **CloudWatch Logs** → **Kinesis Firehose** → **S3** (log aggregation)
- **Prometheus** (metrics collection)
- **Grafana** (visualization)
- **AlertManager** (alerting)

## Problem Statement

The observability infrastructure was recently updated, but several bugs were introduced:

### 1. CloudWatch to S3 Pipeline (Terraform)
The log shipping pipeline is broken. Logs from CloudWatch should flow through Kinesis Firehose to S3, but nothing is being delivered.

**Issues to fix:**
- IAM role permissions are incomplete
- Firehose delivery stream configuration has errors
- CloudWatch log subscription filter is malformed

### 2. Prometheus Configuration
Prometheus is not scraping the correct metrics from services.

**Issues to fix:**
- Scrape configurations pointing to wrong endpoints
- Service discovery labels incorrect
- Metric relabeling rules broken

### 3. Grafana Dashboards
Dashboards show incorrect or no data.

**Issues to fix:**
- Datasource connection strings wrong
- PromQL queries have logic errors
- Dashboard variable syntax incorrect

### 4. Alert Rules
Alerts are either not firing or creating false positives.

**Issues to fix:**
- PromQL alert expressions have threshold errors
- Alert duration/for clauses incorrect
- Severity labels missing or wrong

## Your Task

Fix all configuration files so that:

1. ✅ Terraform validates and plans successfully
2. ✅ IAM policies grant correct permissions (least privilege)
   - Firehose role must use `firehose.amazonaws.com` service principal.
   - S3 and CloudWatch permissions must be scoped to specific resource ARNs, not `*`.
3. ✅ Prometheus configuration is valid (`promtool check config`)
   - `backend-services` must scrape `localhost:8080`.
   - `node-exporter` relabeling must fix the `replacment` typo to `replacement`.
4. ✅ PromQL queries return correct results
   - Alerts threshold for `HighErrorRate` must be `> 0.05` for the `5..` status codes.
   - Grafana dashboard panels must use the `Prometheus-Main` datasource.
5. ✅ Grafana dashboard JSON is valid
   - Dashboard title must be `App Metrics`.
   - RPS panel must use the correct `rate()` expression with `[5m]` interval.
6. ✅ Alert rules fire at correct thresholds
   - Alerts must have a `severity: critical` label.
   - Alert duration (`for`) must be exactly `1m`.

## Files to Fix

```
environment/
├── terraform/
│   ├── iam.tf              # IAM roles and policies (BUGGY)
│   ├── firehose.tf         # Kinesis Firehose config (BUGGY)
│   └── cloudwatch.tf       # Log groups and subscriptions (BUGGY)
├── prometheus/
│   ├── prometheus.yml      # Prometheus config (BUGGY)
│   └── alerts.yml          # Alert rules (BUGGY)
└── grafana/
    └── dashboard.json      # Grafana dashboard (BUGGY)
```

## Success Criteria

All tests must pass:
- Terraform validation and planning
- IAM policy compliance checks
- Prometheus configuration validation
- PromQL query correctness
- Grafana dashboard validation
- Alert threshold verification

## Constraints

- Do NOT change the overall architecture
- Maintain existing resource names
- Keep the same metrics and log formats
- Fix only the configuration bugs

## Hints

1. Check IAM policy `Resource` ARNs carefully
2. Firehose needs permissions to write to S3 AND read from CloudWatch
3. Prometheus job names must match service discovery labels
4. PromQL `rate()` requires a range vector (e.g., `[5m]`)
5. Alert `for` duration should be reasonable (not `0s`)
