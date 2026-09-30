output "redshift_role_arn" {
  description = "ARN of the Redshift role (namespace default role)."
  value       = aws_iam_role.redshift.arn
}

output "redshift_role_name" {
  description = "Name of the Redshift role."
  value       = aws_iam_role.redshift.name
}

output "no_permissions_role_arn" {
  description = "ARN of the empty role used to provoke the COPY error in Part 7."
  value       = aws_iam_role.no_permissions.arn
}

output "resource_arn" {
  description = "ARN of the Redshift role."
  value       = aws_iam_role.redshift.arn
}
