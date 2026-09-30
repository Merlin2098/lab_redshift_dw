output "namespace_name" {
  description = "Name of the Redshift Serverless namespace."
  value       = aws_redshiftserverless_namespace.this.namespace_name
}

output "workgroup_name" {
  description = "Name of the Redshift Serverless workgroup."
  value       = aws_redshiftserverless_workgroup.this.workgroup_name
}

output "database_name" {
  description = "Name of the first database."
  value       = aws_redshiftserverless_namespace.this.db_name
}

output "admin_secret_arn" {
  description = "ARN of the Secrets Manager secret with the admin credentials (used by the Data API)."
  value       = aws_redshiftserverless_namespace.this.admin_password_secret_arn
}

output "workgroup_endpoint" {
  description = "Endpoint address of the workgroup. Empty until the endpoint exists."
  value       = try(aws_redshiftserverless_workgroup.this.endpoint[0].address, "")
}

output "resource_arn" {
  description = "ARN of the workgroup."
  value       = aws_redshiftserverless_workgroup.this.arn
}

output "log_group_name" {
  description = "CloudWatch log group for the exported connection log."
  value       = aws_cloudwatch_log_group.connectionlog.name
}

output "log_group_arn" {
  description = "ARN of the connection log group."
  value       = aws_cloudwatch_log_group.connectionlog.arn
}
