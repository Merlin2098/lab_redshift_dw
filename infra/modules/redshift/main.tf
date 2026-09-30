locals {
  namespace_name = "${var.name_prefix}-ns"
  workgroup_name = "${var.name_prefix}-wg"
}

# Created BEFORE the namespace: if the group does not exist Redshift creates it itself with
# "Never Expire" retention and outside Terraform, which would survive the destroy.
resource "aws_cloudwatch_log_group" "connectionlog" {
  name              = "/aws/redshift/${local.namespace_name}/connectionlog"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_redshiftserverless_namespace" "this" {
  namespace_name        = local.namespace_name
  db_name               = var.db_name
  admin_username        = var.admin_username
  manage_admin_password = true
  default_iam_role_arn  = var.default_iam_role_arn
  iam_roles             = concat([var.default_iam_role_arn], var.additional_iam_role_arns)
  log_exports           = ["connectionlog"]
  tags                  = var.tags

  depends_on = [aws_cloudwatch_log_group.connectionlog]
}

resource "aws_redshiftserverless_workgroup" "this" {
  namespace_name       = aws_redshiftserverless_namespace.this.namespace_name
  workgroup_name       = local.workgroup_name
  base_capacity        = var.base_capacity
  max_capacity         = var.max_capacity
  enhanced_vpc_routing = var.enable_enhanced_vpc_routing
  publicly_accessible  = false
  subnet_ids           = var.subnet_ids
  security_group_ids   = var.security_group_ids
  tags                 = var.tags

  lifecycle {
    precondition {
      condition     = var.max_capacity >= var.base_capacity
      error_message = "max_capacity must be greater than or equal to base_capacity."
    }
  }
}

resource "aws_redshiftserverless_usage_limit" "daily" {
  resource_arn  = aws_redshiftserverless_workgroup.this.arn
  usage_type    = "serverless-compute"
  amount        = var.usage_limit_rpu_hours_daily
  period        = "daily"
  breach_action = "deactivate"
}
