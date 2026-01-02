resource "aws_kinesis_firehose_delivery_stream" "log_stream" {
  name        = "app-logs-delivery-stream"
  destination = "s3"

  s3_configuration {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.log_bucket.arn
    
    # BUG: Buffer size is too small for production (should be at least 1MB/60s), causing API throttling
    buffer_size = 1
    buffer_interval = 60
  }
}

resource "aws_s3_bucket" "log_bucket" {
  bucket = "app-observability-logs-bucket"
}
