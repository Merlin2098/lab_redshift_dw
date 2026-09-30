variable "name_prefix" {
  description = "Prefix for resource names, e.g. redshift-lab-dev."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets for the workgroup."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security groups for the workgroup."
  type        = list(string)
}

variable "default_iam_role_arn" {
  description = "Role used by IAM_ROLE DEFAULT (COPY, UNLOAD, CREATE EXTERNAL SCHEMA)."
  type        = string
}

variable "additional_iam_role_arns" {
  description = "Extra roles associated with the namespace but not default (the empty role for Part 7)."
  type        = list(string)
  default     = []
}

variable "enable_enhanced_vpc_routing" {
  description = "Route COPY/UNLOAD/Spectrum traffic through the VPC. Needs 3 AZs and the endpoints from the network module."
  type        = bool
  default     = false
}

variable "base_capacity" {
  description = "Base capacity in RPUs. 4 (minimum) or a multiple of 8."
  type        = number
  default     = 4

  validation {
    condition     = var.base_capacity == 4 || (var.base_capacity >= 8 && var.base_capacity % 8 == 0)
    error_message = "base_capacity must be 4 or a multiple of 8."
  }
}

variable "max_capacity" {
  description = "Ceiling for automatic scaling, in RPUs. Must be >= base_capacity."
  type        = number
  default     = 8
}

variable "usage_limit_rpu_hours_daily" {
  description = "Daily RPU-hour cap; queries are turned off when it is reached."
  type        = number
  default     = 16
}

variable "log_retention_days" {
  description = "CloudWatch retention for the exported connection log."
  type        = number
  default     = 7
}

variable "db_name" {
  description = "First database created in the namespace."
  type        = string
  default     = "dev"
}

variable "admin_username" {
  description = "Admin user; its password is generated and stored by Secrets Manager."
  type        = string
  default     = "awsuser"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
