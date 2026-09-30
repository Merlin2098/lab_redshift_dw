output "artifact_bucket_name" {
  description = "S3 bucket used for packaged runtime artifacts."
  value       = aws_s3_bucket.artifacts.bucket
}

output "artifact_bucket_arn" {
  description = "ARN of the artifact bucket, for IAM policy scoping by other stacks."
  value       = aws_s3_bucket.artifacts.arn
}

output "artifact_bundle_s3_uri" {
  description = "S3 URI of the packaged runtime artifact."
  value       = "s3://${aws_s3_bucket.artifacts.bucket}/${aws_s3_object.artifact_bundle.key}"
}

output "data_job_execution_role_arn" {
  description = "IAM role ARN for Glue or other batch data jobs."
  value       = aws_iam_role.data_job_execution.arn
}

output "log_group_name" {
  description = "CloudWatch log group name for data jobs."
  value       = aws_cloudwatch_log_group.data_jobs.name
}

output "log_group_arn" {
  description = "CloudWatch log group ARN for data jobs."
  value       = aws_cloudwatch_log_group.data_jobs.arn
}

output "budget_name" {
  description = "AWS Budget name for monthly cost governance. Empty string when enable_budget_guardrail is false."
  value       = var.enable_budget_guardrail ? aws_budgets_budget.monthly[0].name : ""
}

output "budget_alert_sns_arn" {
  description = "SNS topic ARN for budget alerts. Empty string when the guardrail is disabled or no alert email is configured."
  value       = var.enable_budget_guardrail && var.budget_alert_email != "" ? aws_sns_topic.budget_alerts[0].arn : ""
}
