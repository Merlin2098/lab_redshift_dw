# Owned by Terraform (not by CREATE EXTERNAL DATABASE) so that destroy removes it
# together with the external tables Redshift creates inside it.
resource "aws_glue_catalog_database" "this" {
  name        = var.database_name
  description = "Redshift lab: external tables for Spectrum and Athena."
  tags        = var.tags
}
