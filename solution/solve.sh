#!/bin/bash

# This script applies the fixes to the buggy configuration files
# using cat to ensure exact content and avoid sed regex issues.

echo "Applying fixes..."

# Ensure we are in the correct directory or use absolute paths
# Jenkins maps the task to /app

# 1. Fix Terraform IAM
cat <<'EOF' > /app/environment/terraform/iam.tf
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
          "${aws_s3_bucket.log_bucket.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.app_logs.arn}:*"
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
cat <<'EOF' > /app/environment/terraform/firehose.tf
resource "aws_kinesis_firehose_delivery_stream" "log_stream" {
  name        = "app-logs-delivery-stream"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.log_bucket.arn
    
    # Note: extended_s3_configuration uses 'buffering_size' and 'buffering_interval'
    buffering_size     = 5
    buffering_interval = 60
  }
}

resource "aws_s3_bucket" "log_bucket" {
  bucket = "app-observability-logs-bucket"
}
EOF

# 3. Fix CloudWatch Filter
sed -i 's/filter_pattern  = .*/filter_pattern  = ""/' /app/environment/terraform/cloudwatch.tf

# 4. Fix Prometheus Config
sed -i "s/'localhost:9090'/'localhost:8080'/" /app/environment/prometheus/prometheus.yml
sed -i 's/replacment/replacement/' /app/environment/prometheus/prometheus.yml

# 5. Fix Alert Rules
sed -i 's/rate(http_requests_total{status=~"5.."}\[])/rate(http_requests_total{status=~"5.."}[5m])/' /app/environment/prometheus/alerts.yml
sed -i 's/for: 0s/for: 1m/' /app/environment/prometheus/alerts.yml

# 6. Fix Grafana Dashboard
sed -i 's/rate(http_requests_total\[5m/rate(http_requests_total[5m])/' /app/environment/grafana/dashboard.json

echo "Fixes applied!"
