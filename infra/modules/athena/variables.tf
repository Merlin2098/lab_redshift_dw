variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "results_bucket_name" {
  description = "Bucket where Athena writes query results."
  type        = string
}

variable "results_prefix" {
  description = "Prefix inside the bucket for Athena results."
  type        = string
  default     = "athena-results"
}

variable "bytes_scanned_cutoff_per_query" {
  description = "Per-query scan limit in bytes (cost guard). Default 1 GiB; the TICKIT data is far smaller."
  type        = number
  default     = 1073741824
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
