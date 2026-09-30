output "aws_region" {
  description = "Region of the lab."
  value       = var.aws_region
}

output "bucket_name" {
  description = "Lab bucket (UNLOAD target and Athena results)."
  value       = module.s3.bucket_name
}

output "namespace_name" {
  description = "Redshift Serverless namespace."
  value       = module.redshift.namespace_name
}

output "workgroup_name" {
  description = "Redshift Serverless workgroup."
  value       = module.redshift.workgroup_name
}

output "database_name" {
  description = "First Redshift database."
  value       = module.redshift.database_name
}

output "admin_secret_arn" {
  description = "Secrets Manager secret with the admin credentials (Data API authentication)."
  value       = module.redshift.admin_secret_arn
}

output "redshift_role_arn" {
  description = "Default IAM role of the namespace."
  value       = module.iam.redshift_role_arn
}

output "no_permissions_role_arn" {
  description = "Empty IAM role for the Part 7 troubleshooting case."
  value       = module.iam.no_permissions_role_arn
}

output "athena_workgroup_name" {
  description = "Athena workgroup."
  value       = module.athena.workgroup_name
}

output "glue_database_name" {
  description = "Glue database for Spectrum and Athena."
  value       = module.data_catalog.database_name
}

output "log_group_name" {
  description = "CloudWatch log group of the Redshift namespace."
  value       = module.redshift.log_group_name
}

output "log_group_arn" {
  description = "ARN of the Redshift namespace log group."
  value       = module.redshift.log_group_arn
}

output "budget_name" {
  description = "Budget name. Empty string when the guardrail is disabled."
  value       = module.budget.budget_name
}

output "resource_arns" {
  description = "ARN of the main resource of each module."
  value = {
    network      = module.network.resource_arn
    s3           = module.s3.resource_arn
    data_catalog = module.data_catalog.resource_arn
    iam          = module.iam.resource_arn
    redshift     = module.redshift.resource_arn
    athena       = module.athena.resource_arn
    budget       = module.budget.resource_arn
  }
}
