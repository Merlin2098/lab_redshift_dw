import json

import pytest

from scripts.lab.config import LabConfig, parse_outputs

OUTPUTS = {
    "aws_region": "us-east-1",
    "workgroup_name": "redshift-lab-dev-wg",
    "database_name": "dev",
    "admin_secret_arn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:redshift!x",
    "bucket_name": "redshift-lab-dev-123456789012-lab",
    "redshift_role_arn": "arn:aws:iam::123456789012:role/redshift-lab-dev-redshift-role",
    "no_permissions_role_arn": "arn:aws:iam::123456789012:role/redshift-lab-dev-rol-sin-permisos",
    "athena_workgroup_name": "redshift-lab-dev-wg",
    "glue_database_name": "spectrumdb",
}


def _raw(outputs):
    return json.dumps(
        {
            k: {"value": v, "type": "string", "sensitive": False}
            for k, v in outputs.items()
        }
    )


def test_parse_outputs_builds_the_config():
    config = parse_outputs(_raw(OUTPUTS))
    assert isinstance(config, LabConfig)
    assert config.workgroup_name == "redshift-lab-dev-wg"
    assert config.region == "us-east-1"


def test_sql_values_expose_only_the_documented_placeholders():
    values = parse_outputs(_raw(OUTPUTS)).sql_values()
    assert values == {
        "bucket": OUTPUTS["bucket_name"],
        "glue_database": "spectrumdb",
        "no_permissions_role_arn": OUTPUTS["no_permissions_role_arn"],
        "redshift_role_arn": OUTPUTS["redshift_role_arn"],
    }


def test_missing_outputs_explain_that_the_infra_may_not_be_applied():
    with pytest.raises(ValueError, match="applied"):
        parse_outputs("{}")
