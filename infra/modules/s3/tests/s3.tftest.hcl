mock_provider "aws" {}

variables {
  bucket_name = "redshift-lab-dev-123456789012-lab"
  tags        = { CostCenter = "redshift-lab" }
}

run "bucket_is_private_encrypted_and_destroyable" {
  command = apply

  assert {
    condition     = aws_s3_bucket.this.force_destroy == true
    error_message = "force_destroy must be true so destroy empties UNLOAD and Athena output."
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.this.block_public_acls,
      aws_s3_bucket_public_access_block.this.block_public_policy,
      aws_s3_bucket_public_access_block.this.ignore_public_acls,
      aws_s3_bucket_public_access_block.this.restrict_public_buckets,
    ])
    error_message = "All public access must be blocked."
  }

  assert {
    condition     = one(aws_s3_bucket_server_side_encryption_configuration.this.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "AES256"
    error_message = "SSE-AES256 expected."
  }

  assert {
    condition     = strcontains(aws_s3_bucket_policy.tls_only.policy, "aws:SecureTransport")
    error_message = "A TLS-only bucket policy is expected."
  }

  assert {
    condition     = output.resource_arn == output.bucket_arn
    error_message = "resource_arn must equal the bucket ARN."
  }
}
