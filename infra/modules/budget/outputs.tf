output "budget_name" {
  description = "Budget name. Empty string when the guardrail is disabled."
  value       = try(aws_budgets_budget.monthly[0].name, "")
}

output "resource_arn" {
  description = "Budget ARN. Empty string when the guardrail is disabled."
  value       = try(aws_budgets_budget.monthly[0].arn, "")
}
