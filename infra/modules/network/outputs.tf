output "vpc_id" {
  description = "ID of the lab VPC."
  value       = aws_vpc.this.id
}

output "subnet_ids" {
  description = "IDs of the private subnets for the Redshift Serverless workgroup."
  value       = aws_subnet.private[*].id
}

output "security_group_id" {
  description = "ID of the workgroup security group."
  value       = aws_security_group.workgroup.id
}

output "resource_arn" {
  description = "ARN of the lab VPC."
  value       = aws_vpc.this.arn
}
