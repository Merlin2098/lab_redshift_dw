mock_provider "aws" {}

variables {
  tags = { CostCenter = "redshift-lab" }
}

run "creates_the_spectrum_database" {
  command = apply

  assert {
    condition     = aws_glue_catalog_database.this.name == "spectrumdb"
    error_message = "Default database name must be spectrumdb."
  }

  assert {
    condition     = aws_glue_catalog_database.this.tags["CostCenter"] == "redshift-lab"
    error_message = "Common tags must be applied."
  }
}
