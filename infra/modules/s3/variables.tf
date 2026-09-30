variable "bucket_name" {
  description = "Globally unique bucket name."
  type        = string
}

variable "force_destroy" {
  description = "Let destroy delete the bucket even if it holds objects (UNLOAD output, Athena results)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
