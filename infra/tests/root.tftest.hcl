mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b", "us-east-1c"] }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::mock-bucket" }
  }
  mock_resource "aws_glue_catalog_database" {
    defaults = { arn = "arn:aws:glue:us-east-1:123456789012:database/mock" }
  }
  mock_resource "aws_redshiftserverless_workgroup" {
    defaults = { arn = "arn:aws:redshift-serverless:us-east-1:123456789012:workgroup/mock" }
  }
}

run "wires_the_lab_with_default_names" {
  command = apply

  assert {
    condition     = output.bucket_name == "redshift-lab-dev-123456789012-lab"
    error_message = "Bucket name must be <project>-<env>-<account>-lab."
  }

  assert {
    condition     = output.workgroup_name == "redshift-lab-dev-wg" && output.namespace_name == "redshift-lab-dev-ns"
    error_message = "Workgroup and namespace names must derive from the prefix."
  }

  assert {
    condition     = output.glue_database_name == "spectrumdb"
    error_message = "The Glue database must be spectrumdb."
  }

  assert {
    condition     = output.budget_name == ""
    error_message = "The budget must be off by default."
  }

  assert {
    condition     = length(module.network.subnet_ids) == 2
    error_message = "Two subnets expected by default."
  }
}

run "enhanced_vpc_routing_forces_three_azs" {
  command = apply

  variables {
    enable_enhanced_vpc_routing = true
  }

  assert {
    condition     = length(module.network.subnet_ids) == 3
    error_message = "Enhanced VPC routing needs at least three AZs."
  }
}

run "rejects_invalid_project_name" {
  command = plan

  variables {
    project_name = "Bad_Name"
  }

  expect_failures = [var.project_name]
}

run "rejects_other_regions" {
  command = plan

  variables {
    aws_region = "eu-west-1"
  }

  expect_failures = [var.aws_region]
}
