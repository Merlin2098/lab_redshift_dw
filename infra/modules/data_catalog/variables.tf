variable "database_name" {
  description = "Glue database that backs the Redshift Spectrum external schema and the Athena queries."
  type        = string
  default     = "spectrumdb"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
