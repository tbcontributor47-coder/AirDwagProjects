resource "aws_cloudwatch_log_group" "app_logs" {
  name = "/aws/app/backend-services"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_subscription_filter" "firehose_filter" {
  name            = "firehose-subscription"
  log_group_name  = aws_cloudwatch_log_group.app_logs.name
  filter_pattern  = "[timestamp, uuid, level, message]"
  destination_arn = aws_kinesis_firehose_delivery_stream.log_stream.arn
  role_arn        = aws_iam_role.firehose_role.arn
}
