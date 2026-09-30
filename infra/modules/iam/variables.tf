variable "name_prefix" {
  description = "Prefix for role names."
  type        = string
}

variable "account_id" {
  description = "AWS account ID (used to build Glue ARNs)."
  type        = string
}

variable "aws_region" {
  description = "AWS region (used to build Glue ARNs)."
  type        = string
}

variable "lab_bucket_arn" {
  description = "ARN of the lab bucket (UNLOAD target)."
  type        = string
}

variable "glue_database_name" {
  description = "Glue database used by Spectrum and Athena."
  type        = string
}

variable "glue_database_arn" {
  description = "ARN of the Glue database."
  type        = string
}

variable "dataset_bucket_name" {
  description = "Public bucket that holds the TICKIT dataset."
  type        = string
  default     = "redshift-downloads"
}

variable "dataset_prefix" {
  description = "Prefix of the TICKIT dataset inside the dataset bucket."
  type        = string
  default     = "tickit"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
