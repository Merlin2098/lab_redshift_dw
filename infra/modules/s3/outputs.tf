output "bucket_name" {
  description = "Name of the lab bucket."
  value       = aws_s3_bucket.this.bucket
}

output "bucket_arn" {
  description = "ARN of the lab bucket."
  value       = aws_s3_bucket.this.arn
}

output "resource_arn" {
  description = "ARN of the lab bucket."
  value       = aws_s3_bucket.this.arn
}
