output "workgroup_name" {
  description = "Name of the Athena workgroup."
  value       = aws_athena_workgroup.this.name
}

output "resource_arn" {
  description = "ARN of the Athena workgroup."
  value       = aws_athena_workgroup.this.arn
}
