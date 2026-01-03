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
   - Maintain existing resource names: `firehose_delivery_role`, `app-logs-delivery-stream`, and `/aws/app/backend-services`.
2. ✅ IAM policies grant correct permissions (least privilege)
   - Firehose role must use `firehose.amazonaws.com` service principal.
   - S3 and CloudWatch permissions must be scoped to specific resource ARNs, not `*`.
   - The CloudWatch subscription filter must have both `destination_arn` and `role_arn` correctly configured.
3. ✅ Prometheus configuration is valid (`promtool check config`)
   - `backend-services` must scrape `localhost:8080`.
   - `node-exporter` relabeling must fix the `replacment` typo to `replacement`.
   - CloudWatch subscription `filter_pattern` must be set to an empty string (`""`).
4. ✅ PromQL queries return correct results
   - Alerts threshold for `HighErrorRate` must be `> 0.05` for the `5..` status codes.
   - Grafana dashboard panels must use the `Prometheus-Main` datasource.
5. ✅ Grafana dashboard JSON is valid
   - Dashboard title must be `App Metrics`.
   - RPS panel must use the correct `rate()` expression with `[5m]` interval.
   - Add a dashboard query variable named `job` using the syntax `label_values(http_requests_total, job)`.
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

All tests must pass by meeting these specific requirements:

- **Terraform & Infrastructure**:
  - `terraform validate` and `terraform plan` must succeed without errors.
  - Maintain exact resource names: `firehose_delivery_role`, `app-logs-delivery-stream`, and `/aws/app/backend-services`.
  - The CloudWatch subscription filter must be correctly linked using `destination_arn` and `role_arn`.
- **IAM (Least Privilege)**:
  - Firehose role must use the `firehose.amazonaws.com` service principal.
  - S3 and CloudWatch Logs permissions must be scoped to specific resource ARNs, avoiding `*` wildcards.
- **Prometheus & Alerts**:
  - `promtool check config` must pass.
  - `backend-services` job must scrape `localhost:8080`.
  - The `node-exporter` relabeling typo must be corrected to `replacement`.
  - The CloudWatch subscription `filter_pattern` must be explicitly set to an empty string (`""`).
  - Any Prometheus alert rule using the `rate()` function must use a `[5m]` range vector.
  - Alerts must use `> 0.05` thresholds and have a `1m` duration.
  - Alerts must include the `severity: critical` label.
- **Grafana Dashboards**:
  - Dashboard JSON must be valid with its title set to `App Metrics`.
  - Panels must use the `Prometheus-Main` datasource.
  - Every dashboard panel query must contain the exact expression `rate(http_requests_total[5m])`.
  - A template variable named `job` must be present using the `label_values(http_requests_total, job)` query syntax.

## Technical Requirements

### Terraform Configuration Syntax

**Kinesis Firehose Delivery Stream:**
- When configuring a Kinesis Firehose delivery stream for S3 destinations, you must use `destination = "extended_s3"` with an `extended_s3_configuration` block
- The `s3_configuration` block is not valid for this resource type - use `extended_s3_configuration` instead
- Buffer settings in `extended_s3_configuration` use `buffering_size` (MB) and `buffering_interval` (seconds) as attribute names

**IAM Policy JSON Encoding:**
- When using `jsonencode()` in Terraform, resource ARNs can be constructed using the `format()` function for string concatenation
- Example: `format("%s/*", aws_s3_bucket.example.arn)` for bucket objects
- Policy resources must reference actual resource attributes (e.g., `aws_s3_bucket.log_bucket.arn`)

### Grafana Dashboard JSON Structure

**Dashboard JSON Format:**
- Grafana dashboard JSON must be valid JSON with proper structure
- Panel queries in the `targets` array must contain valid PromQL expressions with proper syntax (matching brackets and parentheses)
- Template variables must be defined in the `templating.list` array with proper structure
- Query-type variables require a `query` object with a `query` field containing the PromQL expression (e.g., `label_values(http_requests_total, job)`)
- Variable definitions require fields: `name`, `type`, `datasource`, `query`, and `refresh`

## Constraints

- Do NOT change the overall architecture
- Maintain existing resource names
- Keep the same metrics and log formats
- Fix only the configuration bugs

## Hints

1. Check IAM policy `Resource` ARNs carefully - use `format()` function for string concatenation in Terraform expressions
2. Firehose needs permissions to write to S3 AND read from CloudWatch
3. Prometheus job names must match service discovery labels
4. PromQL `rate()` requires a range vector (e.g., `[5m]`) and proper closing syntax
5. Alert `for` duration should be reasonable (not `0s`)
6. Grafana JSON must be valid - ensure all JSON brackets, braces, and quotes are properly matched
7. Verify Terraform syntax matches AWS provider requirements - check resource documentation for correct block types
