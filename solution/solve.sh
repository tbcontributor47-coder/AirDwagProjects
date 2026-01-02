#!/bin/bash

# This script applies the fixes to the buggy configuration files

echo "Applying fixes..."

# 1. Fix Terraform IAM
# Replace "Resource = \"*\"" with specific ARN and add logs permission
sed -i 's/Resource = "\*"/Resource = [aws_s3_bucket.log_bucket.arn, "${aws_s3_bucket.log_bucket.arn}\/*"]/' environment/terraform/iam.tf
# Add the missing CloudWatch Logs permissions block if it's missing (it usually is in the buggy version)
# For simplicity, we assume the agent would add this. But solve.sh should be automated.
# Let's insert the missing block after the first statement.
sed -i '/"${aws_s3_bucket.log_bucket.arn}\/\*"]/a \
      },\
      {\
        Effect = "Allow"\
        Action = [\
          "logs:CreateLogStream",\
          "logs:PutLogEvents"\
        ]\
        Resource = "${aws_cloudwatch_log_group.app_logs.arn}:*"' environment/terraform/iam.tf

# 2. Fix Firehose Buffer
sed -i 's/buffer_size = 1/buffer_size = 5/' environment/terraform/firehose.tf

# 3. Fix CloudWatch Filter
sed -i 's/filter_pattern  = .*/filter_pattern  = ""/' environment/terraform/cloudwatch.tf

# 4. Fix Prometheus Config
sed -i "s/'localhost:9090'/'localhost:8080'/" environment/prometheus/prometheus.yml
sed -i 's/replacment/replacement/' environment/prometheus/prometheus.yml

# 5. Fix Alert Rules
sed -i 's/rate(http_requests_total{status=~"5.."}\[])/rate(http_requests_total{status=~"5.."}[5m])/' environment/prometheus/alerts.yml
sed -i 's/for: 0s/for: 1m/' environment/prometheus/alerts.yml

# 6. Fix Grafana Dashboard
sed -i 's/rate(http_requests_total\[5m/rate(http_requests_total[5m])/' environment/grafana/dashboard.json

echo "Fixes applied!"
