resource "aws_budgets_budget" "monthly" {
  count             = var.enabled ? 1 : 0
  name              = "${var.name_prefix}-monthly-budget"
  budget_type       = "COST"
  limit_amount      = tostring(var.limit_usd)
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = var.time_period_start
  tags              = var.tags

  cost_filter {
    name   = "TagKeyValue"
    values = [format("user:Project$%s", var.project_name)]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }

  lifecycle {
    precondition {
      condition     = var.alert_email != ""
      error_message = "alert_email is required when the budget is enabled."
    }
  }
}
