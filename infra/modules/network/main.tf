data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = var.availability_zone_names != null ? var.availability_zone_names : slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_subnet" "private" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-private-${local.azs[count.index]}" })
}

# No inbound rules: access is through Query Editor v2 and the Data API, never a direct connection.
resource "aws_security_group" "workgroup" {
  name        = "${var.name_prefix}-redshift"
  description = "Redshift Serverless workgroup. No inbound rules."
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-redshift" })
}

# The subnets have no internet route, so open egress only matters for the endpoints below.
resource "aws_vpc_security_group_egress_rule" "workgroup_all" {
  security_group_id = aws_security_group.workgroup.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "Egress for the workgroup network interfaces."
  tags              = var.tags
}

resource "aws_vpc_endpoint" "s3" {
  count             = var.enable_enhanced_vpc_routing ? 1 : 0
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_vpc.this.main_route_table_id]
  tags              = merge(var.tags, { Name = "${var.name_prefix}-s3" })
}

resource "aws_security_group" "endpoints" {
  count       = var.enable_enhanced_vpc_routing ? 1 : 0
  name        = "${var.name_prefix}-endpoints"
  description = "Interface endpoints: HTTPS from inside the VPC only."
  vpc_id      = aws_vpc.this.id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-endpoints" })
}

resource "aws_vpc_security_group_ingress_rule" "endpoints_https" {
  count             = var.enable_enhanced_vpc_routing ? 1 : 0
  security_group_id = aws_security_group.endpoints[0].id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = var.vpc_cidr
  description       = "HTTPS from the lab VPC."
  tags              = var.tags
}

resource "aws_vpc_endpoint" "glue" {
  count               = var.enable_enhanced_vpc_routing ? 1 : 0
  vpc_id              = aws_vpc.this.id
  service_name        = "com.amazonaws.${var.aws_region}.glue"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints[0].id]
  private_dns_enabled = true
  tags                = merge(var.tags, { Name = "${var.name_prefix}-glue" })
}
