#!/bin/bash
set -euo pipefail

echo "Applying fixes with high-rigor precision..."

# Detect environment directory
if [ -d "environment" ]; then
    ENV_DIR="environment"
else
    ENV_DIR="/app/environment"
fi

# 1. Fix Terraform IAM (Strict Scoping)
cat <<EOF > "$ENV_DIR/terraform/iam.tf"
provider "aws" {
  region                      = "us-east-1"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
}

resource "aws_iam_role" "firehose_role" {
  name = "firehose_delivery_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "firehose.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "firehose_policy" {
  name = "firehose_delivery_policy"
  role = aws_iam_role.firehose_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.log_bucket.arn,
          "\${aws_s3_bucket.log_bucket.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "\${aws_cloudwatch_log_group.app_logs.arn}:*"
      },
      {
          Effect = "Allow",
          Action = [
              "kinesis:DescribeStream",
              "kinesis:GetShardIterator",
              "kinesis:GetRecords",
              "kinesis:ListShards"
          ],
          Resource = "*"
      }
    ]
  })
}
EOF

# 2. Fix Firehose
cat <<EOF > "$ENV_DIR/terraform/firehose.tf"
resource "aws_kinesis_firehose_delivery_stream" "log_stream" {
  name        = "app-logs-delivery-stream"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.log_bucket.arn
    
    buffering_size     = 5
    buffering_interval = 60
  }
}

resource "aws_s3_bucket" "log_bucket" {
  bucket = "app-observability-logs-bucket"
}
EOF

# 3. Fix CloudWatch Filter
sed -i 's/filter_pattern  = .*/filter_pattern  = ""/' "$ENV_DIR/terraform/cloudwatch.tf"

# 4. Fix Prometheus Config
sed -i "s/'localhost:9090'/'localhost:8080'/" "$ENV_DIR/prometheus/prometheus.yml"
sed -i 's/replacment/replacement/g' "$ENV_DIR/prometheus/prometheus.yml"

# 5. Fix Alert Rules
sed -i 's/rate(http_requests_total{status=~"5.."}\[])/rate(http_requests_total{status=~"5.."}[5m])/' "$ENV_DIR/prometheus/alerts.yml"
sed -i 's/for: 0s/for: 1m/' "$ENV_DIR/prometheus/alerts.yml"

# 6. Fix Grafana Dashboard (Using Python for reliable JSON manipulation)
python3 - <<EOF
import json
import os

path = "$ENV_DIR/grafana/dashboard.json"
with open(path, 'r') as f:
    data = json.load(f)

# Fix title
data['title'] = "App Metrics"

# Fix PromQL in panels
for panel in data.get('panels', []):
    panel['datasource'] = "Prometheus-Main"
    for target in panel.get('targets', []):
        if 'rate(http_requests_total[5m' in target['expr']:
            target['expr'] = 'rate(http_requests_total[5m])'

# Add variable
data['templating']['list'] = [
    {
        "allValue": None,
        "current": {},
        "datasource": "Prometheus-Main",
        "definition": "label_values(http_requests_total, job)",
        "hide": 0,
        "includeAll": False,
        "label": "Job",
        "multi": False,
        "name": "job",
        "query": {
            "query": "label_values(http_requests_total, job)",
            "refId": "StandardVariableQuery"
        },
        "refresh": 1,
        "type": "query"
    }
]

with open(path, 'w') as f:
    json.dump(data, f, indent=4)
EOF

echo "Fixes applied!"
