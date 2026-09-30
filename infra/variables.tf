variable "project_name" {
  description = "Project name used in resource naming (lowercase letters, digits, hyphens)."
  type        = string
  default     = "redshift-lab"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,20}$", var.project_name))
    error_message = "project_name must be 3-20 characters: lowercase letters, digits and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owner tag applied to all resources."
  type        = string
  default     = "lab-student"
}

variable "cost_center" {
  description = "CostCenter tag applied to all resources."
  type        = string
  default     = "redshift-lab"
}

variable "aws_region" {
  description = "AWS region. Must be us-east-1: the public TICKIT dataset lives there and 4 RPUs is available there."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "This lab only supports us-east-1."
  }
}

variable "tags" {
  description = "Additional tags applied to all resources."
  type        = map(string)
  default     = {}
}

variable "glue_database_name" {
  description = "Glue database for Spectrum and Athena."
  type        = string
  default     = "spectrumdb"
}

variable "availability_zone_count" {
  description = "AZs/subnets for the workgroup: 2 without enhanced VPC routing (3 is forced with it). Use 3 if the first apply rejects 2."
  type        = number
  default     = 2
}

variable "availability_zone_names" {
  description = "Optional explicit AZ names if the default AZs are not supported by Redshift Serverless in your account."
  type        = list(string)
  default     = null
}

variable "enable_enhanced_vpc_routing" {
  description = "Turn on enhanced VPC routing (creates S3 and Glue endpoints; the Glue one has an hourly cost)."
  type        = bool
  default     = false
}

variable "base_capacity" {
  description = "Redshift Serverless base capacity in RPUs (4, or a multiple of 8)."
  type        = number
  default     = 4
}

variable "max_capacity" {
  description = "Redshift Serverless scaling ceiling in RPUs."
  type        = number
  default     = 8
}

variable "usage_limit_rpu_hours_daily" {
  description = "Daily RPU-hour cap; queries are turned off when reached."
  type        = number
  default     = 16
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 7
}

variable "enable_budget_guardrail" {
  description = "Create a monthly AWS Budget. Off by default for student deployments."
  type        = bool
  default     = false
}

variable "budget_limit_usd" {
  description = "Monthly budget limit in USD."
  type        = number
  default     = 25
}

variable "budget_alert_email" {
  description = "Email for budget alerts. Required when enable_budget_guardrail is true."
  type        = string
  default     = ""
}
