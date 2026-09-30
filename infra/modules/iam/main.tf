locals {
  # Redshift Serverless requires both service principals in the trust relationship.
  trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = ["redshift.amazonaws.com", "redshift-serverless.amazonaws.com"] }
      Action    = "sts:AssumeRole"
    }]
  })

  dataset_bucket_arn = "arn:aws:s3:::${var.dataset_bucket_name}"
  glue_catalog_arn   = "arn:aws:glue:${var.aws_region}:${var.account_id}:catalog"
  glue_tables_arn    = "arn:aws:glue:${var.aws_region}:${var.account_id}:table/${var.glue_database_name}/*"
}

resource "aws_iam_role" "redshift" {
  name               = "${var.name_prefix}-redshift-role"
  assume_role_policy = local.trust_policy
  tags               = var.tags
}

# Read the public TICKIT dataset (COPY and Spectrum).
resource "aws_iam_role_policy" "dataset_read" {
  name = "${var.name_prefix}-dataset-read"
  role = aws_iam_role.redshift.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${local.dataset_bucket_arn}/${var.dataset_prefix}/*"]
      },
      {
        Effect    = "Allow"
        Action    = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource  = [local.dataset_bucket_arn]
        Condition = { StringLike = { "s3:prefix" = ["${var.dataset_prefix}/*"] } }
      },
    ]
  })
}

# Read and write the lab bucket (UNLOAD output).
resource "aws_iam_role_policy" "lab_bucket" {
  name = "${var.name_prefix}-lab-bucket"
  role = aws_iam_role.redshift.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
        Resource = ["${var.lab_bucket_arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [var.lab_bucket_arn]
      },
    ]
  })
}

# Spectrum: read the catalog and create/update external tables inside the lab database only.
resource "aws_iam_role_policy" "glue_catalog" {
  name = "${var.name_prefix}-glue-catalog"
  role = aws_iam_role.redshift.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "glue:GetDatabase", "glue:GetDatabases",
        "glue:GetTable", "glue:GetTables", "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable", "glue:BatchDeleteTable",
        "glue:GetPartition", "glue:GetPartitions", "glue:BatchGetPartition",
        "glue:CreatePartition", "glue:BatchCreatePartition", "glue:UpdatePartition", "glue:DeletePartition", "glue:BatchDeletePartition",
      ]
      Resource = [local.glue_catalog_arn, var.glue_database_arn, local.glue_tables_arn]
    }]
  })
}

# Part 7 (troubleshooting): associated with the namespace but with no permissions at all,
# so COPY fails with S3 Access Denied and not with "role not associated".
resource "aws_iam_role" "no_permissions" {
  name               = "${var.name_prefix}-rol-sin-permisos"
  assume_role_policy = local.trust_policy
  tags               = var.tags
}
