mock_provider "aws" {}

variables {
  name_prefix  = "redshift-lab-dev"
  project_name = "redshift-lab"
  tags         = { CostCenter = "redshift-lab" }
}

run "disabled_by_default" {
  command = apply

  assert {
    condition     = length(aws_budgets_budget.monthly) == 0 && output.budget_name == ""
    error_message = "The budget must not exist unless enabled."
  }
}

run "enabled_filters_by_project_tag" {
  command = apply

  variables {
    enabled     = true
    alert_email = "student@example.com"
  }

  assert {
    condition     = tolist(one(aws_budgets_budget.monthly[0].cost_filter).values)[0] == "user:Project$redshift-lab"
    error_message = "Cost filter must match the literal tag value user:Project$<project_name>."
  }
}

run "enabled_without_email_is_rejected" {
  command = plan

  variables {
    enabled = true
  }

  expect_failures = [aws_budgets_budget.monthly]
}
