mock_provider "aws" {}

variables {
  name_prefix        = "redshift-lab-dev"
  account_id         = "123456789012"
  aws_region         = "us-east-1"
  lab_bucket_arn     = "arn:aws:s3:::redshift-lab-dev-123456789012-lab"
  glue_database_name = "spectrumdb"
  glue_database_arn  = "arn:aws:glue:us-east-1:123456789012:database/spectrumdb"
  tags               = { CostCenter = "redshift-lab" }
}

run "trust_includes_both_redshift_principals" {
  command = apply

  assert {
    condition = alltrue([
      for role in [aws_iam_role.redshift, aws_iam_role.no_permissions] :
      toset(flatten([for s in jsondecode(role.assume_role_policy).Statement : s.Principal.Service])) == toset(["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"])
    ])
    error_message = "Both roles must be assumable by redshift.amazonaws.com and redshift-serverless.amazonaws.com."
  }
}

run "policies_are_scoped_without_wildcard_resources" {
  command = apply

  assert {
    condition = alltrue([
      for p in [aws_iam_role_policy.dataset_read.policy, aws_iam_role_policy.lab_bucket.policy, aws_iam_role_policy.glue_catalog.policy] :
      !contains(flatten([for s in jsondecode(p).Statement : s.Resource]), "*")
    ])
    error_message = "No policy statement may use Resource \"*\"."
  }

  assert {
    condition     = contains(flatten([for s in jsondecode(aws_iam_role_policy.dataset_read.policy).Statement : s.Resource]), "arn:aws:s3:::redshift-downloads/tickit/*")
    error_message = "Dataset read must be limited to the tickit prefix."
  }

  assert {
    condition     = contains(flatten([for s in jsondecode(aws_iam_role_policy.lab_bucket.policy).Statement : s.Resource]), "arn:aws:s3:::redshift-lab-dev-123456789012-lab/*")
    error_message = "Lab bucket access must be limited to the lab bucket."
  }

  assert {
    condition     = contains(flatten([for s in jsondecode(aws_iam_role_policy.glue_catalog.policy).Statement : s.Resource]), "arn:aws:glue:us-east-1:123456789012:database/spectrumdb")
    error_message = "Glue access must include the lab database."
  }
}

run "no_permissions_role_is_named_for_part_7" {
  command = apply

  assert {
    condition     = endswith(aws_iam_role.no_permissions.name, "-rol-sin-permisos")
    error_message = "The empty role must be named ...-rol-sin-permisos."
  }
}
