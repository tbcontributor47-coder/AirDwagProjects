#!/bin/bash

# This script applies the fixes to the buggy configuration files

echo "Applying fixes..."

# 1. Fix Terraform IAM
sed -i 's/Resource = "*"/Resource = [aws_s3_bucket.log_bucket.arn, "${aws_s3_bucket.log_bucket.arn}\/*"]/' environment/terraform/iam.tf

# 2. Fix Firehose (Modern AWS Provider)
sed -i 's/destination = "s3"/destination = "extended_s3"/' environment/terraform/firehose.tf
sed -i 's/s3_configuration/extended_s3_configuration/' environment/terraform/firehose.tf
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
