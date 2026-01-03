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

1. **CloudWatch to S3 Pipeline**: The log shipping pipeline is broken. Logs from CloudWatch should flow through Kinesis Firehose to S3, but nothing is being delivered.

2. **Prometheus Configuration**: Prometheus is not scraping the correct metrics from services.

3. **Grafana Dashboards**: Dashboards show incorrect or no data due to configuration errors.

4. **Alert Rules**: Alerts are either not firing or creating false positives.

## Your Task

Fix all configuration files so that:

1. **Terraform configuration validates and plans successfully**
2. **IAM policies grant correct permissions following least privilege principles**
3. **Prometheus configuration is valid and scrapes from the correct endpoints**
4. **PromQL queries are syntactically correct and return expected results**
5. **Grafana dashboard JSON is valid and displays data correctly**
6. **Alert rules fire at appropriate thresholds with correct severity labels**

## Constraints

**DO NOT modify these exact values (they are validated by tests):**
- IAM role name: `firehose_delivery_role`
- IAM role service principal: `firehose.amazonaws.com`
- Firehose stream name: `app-logs-delivery-stream`
- CloudWatch log group name: `/aws/app/backend-services`
- CloudWatch subscription filter pattern: empty string (`""`)
- Prometheus backend-services job target: `localhost:8080`
- Grafana dashboard title: `App Metrics`
- Grafana datasource name: `Prometheus-Main`
- Prometheus alert threshold: `> 0.05`
- Prometheus alert duration: `1m`
- Prometheus alert severity label: `critical`
- Grafana must include a query variable using `label_values`

Do NOT change the overall architecture, maintain existing resource names, keep the same metrics and log formats, and fix only the configuration bugs.

## Files to Fix

```
environment/
├── terraform/
│   ├── iam.tf              # IAM roles and policies
│   ├── firehose.tf         # Kinesis Firehose config
│   └── cloudwatch.tf       # Log groups and subscriptions
├── prometheus/
│   ├── prometheus.yml      # Prometheus config
│   └── alerts.yml          # Alert rules
└── grafana/
    └── dashboard.json      # Grafana dashboard
```

## Success Criteria

All tests must pass:
- Terraform validation and planning
- IAM policy compliance checks (no wildcard resources for S3/CloudWatch)
- Prometheus configuration validation
- PromQL query correctness
- Grafana dashboard validation
- Alert threshold verification
