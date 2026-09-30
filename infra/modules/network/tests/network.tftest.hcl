mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = {
      names = ["us-east-1a", "us-east-1b", "us-east-1c"]
    }
  }
}

variables {
  name_prefix = "redshift-lab-dev"
  aws_region  = "us-east-1"
  tags = {
    Project    = "redshift-lab"
    CostCenter = "redshift-lab"
  }
}

run "defaults_two_private_subnets_and_no_endpoints" {
  command = apply

  assert {
    condition     = length(aws_subnet.private) == 2
    error_message = "Default must create exactly 2 private subnets."
  }

  assert {
    condition     = alltrue([for s in aws_subnet.private : s.map_public_ip_on_launch == false])
    error_message = "Subnets must be private."
  }

  assert {
    condition     = length(aws_vpc_endpoint.s3) == 0 && length(aws_vpc_endpoint.glue) == 0
    error_message = "No VPC endpoints without enhanced VPC routing."
  }

  assert {
    condition     = aws_vpc.this.tags["CostCenter"] == "redshift-lab"
    error_message = "Common tags must be applied to the VPC."
  }
}

run "enhanced_vpc_routing_adds_endpoints" {
  command = apply

  variables {
    enable_enhanced_vpc_routing = true
    availability_zone_count     = 3
  }

  assert {
    condition     = length(aws_subnet.private) == 3
    error_message = "Three subnets expected for three AZs."
  }

  assert {
    condition     = length(aws_vpc_endpoint.s3) == 1 && length(aws_vpc_endpoint.glue) == 1
    error_message = "S3 gateway and Glue interface endpoints expected with enhanced VPC routing."
  }
}

run "rejects_single_az" {
  command = plan

  variables {
    availability_zone_count = 1
  }

  expect_failures = [var.availability_zone_count]
}
