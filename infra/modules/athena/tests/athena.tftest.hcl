mock_provider "aws" {}

variables {
  name_prefix         = "redshift-lab-dev"
  results_bucket_name = "redshift-lab-dev-123456789012-lab"
  tags                = { CostCenter = "redshift-lab" }
}

run "workgroup_writes_to_the_lab_bucket_and_is_destroyable" {
  command = apply

  assert {
    condition     = aws_athena_workgroup.this.force_destroy == true
    error_message = "force_destroy must be true."
  }

  assert {
    condition     = one(aws_athena_workgroup.this.configuration).enforce_workgroup_configuration == true
    error_message = "Workgroup settings must override client-side settings."
  }

  assert {
    condition     = one(one(aws_athena_workgroup.this.configuration).result_configuration).output_location == "s3://redshift-lab-dev-123456789012-lab/athena-results/"
    error_message = "Results must go to the lab bucket under athena-results/."
  }

  assert {
    condition     = one(one(one(aws_athena_workgroup.this.configuration).result_configuration).encryption_configuration).encryption_option == "SSE_S3"
    error_message = "Results must be encrypted with SSE_S3."
  }
}
