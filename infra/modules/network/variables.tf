variable "name_prefix" {
  description = "Prefix for resource names, e.g. redshift-lab-dev."
  type        = string
}

variable "aws_region" {
  description = "Region of the VPC endpoints (only used when enhanced VPC routing is on)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR of the lab VPC. Each subnet is a /24, well above the /27 Redshift Serverless needs."
  type        = string
  default     = "10.42.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of AZs/subnets. Redshift Serverless needs 2 without enhanced VPC routing and 3 with it."
  type        = number
  default     = 2

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "availability_zone_count must be 2 or 3."
  }
}

variable "availability_zone_names" {
  description = "Optional explicit AZ names. Use it if the default AZs are not supported by Redshift Serverless in your account. Overrides availability_zone_count."
  type        = list(string)
  default     = null
}

variable "enable_enhanced_vpc_routing" {
  description = "Create the S3 gateway and Glue interface endpoints needed when the workgroup uses enhanced VPC routing."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
