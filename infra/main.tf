data "aws_caller_identity" "current" {}

locals {
  name_prefix = lower(replace("${var.project_name}-${var.environment}", "_", "-"))
  bucket_name = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-lab"
  az_count    = var.enable_enhanced_vpc_routing ? max(3, var.availability_zone_count) : var.availability_zone_count

  common_tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "Terraform"
    CostCenter  = var.cost_center
  })
}

module "network" {
  source                      = "./modules/network"
  name_prefix                 = local.name_prefix
  aws_region                  = var.aws_region
  availability_zone_count     = local.az_count
  availability_zone_names     = var.availability_zone_names
  enable_enhanced_vpc_routing = var.enable_enhanced_vpc_routing
  tags                        = local.common_tags
}

module "s3" {
  source      = "./modules/s3"
  bucket_name = local.bucket_name
  tags        = local.common_tags
}

module "data_catalog" {
  source        = "./modules/data_catalog"
  database_name = var.glue_database_name
  tags          = local.common_tags
}

module "iam" {
  source             = "./modules/iam"
  name_prefix        = local.name_prefix
  account_id         = data.aws_caller_identity.current.account_id
  aws_region         = var.aws_region
  lab_bucket_arn     = module.s3.bucket_arn
  glue_database_name = module.data_catalog.database_name
  glue_database_arn  = module.data_catalog.database_arn
  tags               = local.common_tags
}

module "redshift" {
  source                      = "./modules/redshift"
  name_prefix                 = local.name_prefix
  subnet_ids                  = module.network.subnet_ids
  security_group_ids          = [module.network.security_group_id]
  default_iam_role_arn        = module.iam.redshift_role_arn
  additional_iam_role_arns    = [module.iam.no_permissions_role_arn]
  enable_enhanced_vpc_routing = var.enable_enhanced_vpc_routing
  base_capacity               = var.base_capacity
  max_capacity                = var.max_capacity
  usage_limit_rpu_hours_daily = var.usage_limit_rpu_hours_daily
  log_retention_days          = var.log_retention_days
  tags                        = local.common_tags
}

module "athena" {
  source              = "./modules/athena"
  name_prefix         = local.name_prefix
  results_bucket_name = module.s3.bucket_name
  tags                = local.common_tags
}

module "budget" {
  source       = "./modules/budget"
  enabled      = var.enable_budget_guardrail
  name_prefix  = local.name_prefix
  project_name = var.project_name
  limit_usd    = var.budget_limit_usd
  alert_email  = var.budget_alert_email
  tags         = local.common_tags
}
