import json

import pytest

from scripts.lab.aws_session import get_client

pytestmark = pytest.mark.cloud


def test_workgroup_is_private_and_small(lab_config):
    workgroup = get_client("redshift-serverless", lab_config.region).get_workgroup(
        workgroupName=lab_config.workgroup_name
    )["workgroup"]
    assert workgroup["publiclyAccessible"] is False
    assert workgroup["baseCapacity"] == 4


def test_usage_limit_is_daily_and_deactivates(lab_config):
    client = get_client("redshift-serverless", lab_config.region)
    arn = client.get_workgroup(workgroupName=lab_config.workgroup_name)["workgroup"][
        "workgroupArn"
    ]
    limits = client.list_usage_limits(resourceArn=arn)["usageLimits"]
    assert any(
        limit["period"] == "daily" and limit["breachAction"] == "deactivate"
        for limit in limits
    )


def test_lab_bucket_blocks_public_access(lab_config):
    config = get_client("s3", lab_config.region).get_public_access_block(
        Bucket=lab_config.bucket_name
    )["PublicAccessBlockConfiguration"]
    assert all(config.values())


def test_redshift_role_trusts_both_service_principals(lab_config):
    name = lab_config.redshift_role_arn.rsplit("/", 1)[1]
    document = get_client("iam", lab_config.region).get_role(RoleName=name)["Role"][
        "AssumeRolePolicyDocument"
    ]
    principals = {
        p
        for statement in document["Statement"]
        for p in _as_list(statement["Principal"]["Service"])
    }
    assert principals == {"redshift.amazonaws.com", "redshift-serverless.amazonaws.com"}


def test_connection_log_group_has_retention(lab_config):
    namespace = lab_config.workgroup_name.removesuffix("-wg") + "-ns"
    groups = get_client("logs", lab_config.region).describe_log_groups(
        logGroupNamePrefix=f"/aws/redshift/{namespace}/"
    )["logGroups"]
    assert groups, "expected the Terraform-managed log group"
    assert all(group.get("retentionInDays") == 7 for group in groups), json.dumps(
        [g["logGroupName"] for g in groups]
    )


def _as_list(value):
    return value if isinstance(value, list) else [value]
