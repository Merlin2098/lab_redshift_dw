mock_provider "aws" {
  mock_resource "aws_redshiftserverless_workgroup" {
    defaults = {
      arn = "arn:aws:redshift-serverless:us-east-1:123456789012:workgroup/mock"
    }
  }
}

variables {
  name_prefix              = "redshift-lab-dev"
  subnet_ids               = ["subnet-aaa", "subnet-bbb"]
  security_group_ids       = ["sg-aaa"]
  default_iam_role_arn     = "arn:aws:iam::123456789012:role/redshift-lab-dev-redshift-role"
  additional_iam_role_arns = ["arn:aws:iam::123456789012:role/redshift-lab-dev-rol-sin-permisos"]
  tags                     = { CostCenter = "redshift-lab" }
}

run "workgroup_is_private_small_and_capped" {
  command = apply

  assert {
    condition     = aws_redshiftserverless_workgroup.this.base_capacity == 4 && aws_redshiftserverless_workgroup.this.max_capacity == 8
    error_message = "Defaults must be base 4 and max 8 RPUs."
  }

  assert {
    condition     = aws_redshiftserverless_workgroup.this.publicly_accessible == false
    error_message = "The workgroup must not be publicly accessible."
  }

  assert {
    condition     = aws_redshiftserverless_workgroup.this.enhanced_vpc_routing == false
    error_message = "Enhanced VPC routing is off by default."
  }

  assert {
    condition     = aws_redshiftserverless_usage_limit.daily.period == "daily" && aws_redshiftserverless_usage_limit.daily.breach_action == "deactivate" && aws_redshiftserverless_usage_limit.daily.amount == 16
    error_message = "A daily 16 RPU-hour limit with deactivate is expected."
  }
}

run "namespace_uses_managed_password_and_default_role" {
  command = apply

  assert {
    condition     = aws_redshiftserverless_namespace.this.manage_admin_password == true
    error_message = "The admin password must be managed by Secrets Manager."
  }

  assert {
    condition     = aws_redshiftserverless_namespace.this.default_iam_role_arn == var.default_iam_role_arn && contains(aws_redshiftserverless_namespace.this.iam_roles, var.default_iam_role_arn)
    error_message = "The default role must be set and also be in iam_roles."
  }

  assert {
    condition     = contains(aws_redshiftserverless_namespace.this.iam_roles, var.additional_iam_role_arns[0])
    error_message = "The no-permissions role must be associated with the namespace (Part 7)."
  }
}

run "log_group_is_explicit_and_named_like_the_service_expects" {
  command = apply

  assert {
    condition     = aws_cloudwatch_log_group.connectionlog.name == "/aws/redshift/redshift-lab-dev-ns/connectionlog"
    error_message = "The log group must be /aws/redshift/<namespace>/connectionlog."
  }

  assert {
    condition     = aws_cloudwatch_log_group.connectionlog.retention_in_days == 7
    error_message = "Retention must be set (7 days by default)."
  }
}

run "rejects_invalid_base_capacity" {
  command = plan

  variables {
    base_capacity = 6
  }

  expect_failures = [var.base_capacity]
}

run "rejects_max_capacity_below_base" {
  command = plan

  variables {
    base_capacity = 16
    max_capacity  = 8
  }

  expect_failures = [aws_redshiftserverless_workgroup.this]
}
