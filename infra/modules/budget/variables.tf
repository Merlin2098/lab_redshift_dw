variable "enabled" {
  description = "Create the monthly AWS Budget. Off by default for student deployments."
  type        = bool
  default     = false
}

variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "project_name" {
  description = "Value of the Project tag the budget filters on."
  type        = string
}

variable "limit_usd" {
  description = "Monthly limit in USD. Alerts at 80% (actual) and 100% (forecasted)."
  type        = number
  default     = 25
}

variable "alert_email" {
  description = "Email for budget alerts. Required when enabled."
  type        = string
  default     = ""
}

variable "time_period_start" {
  description = "Budget start, format YYYY-MM-DD_HH:MM."
  type        = string
  default     = "2024-01-01_00:00"
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
}
