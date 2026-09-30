import boto3

from scripts.lab.teardown import PAGINATED_OPERATIONS, find_residuals
from scripts.lab.verify_teardown import main


class FakePaginator:
    def __init__(self, pages, calls, operation):
        self._pages, self._calls, self._operation = pages, calls, operation

    def paginate(self, **kwargs):
        self._calls.append((self._operation, kwargs))
        return iter(self._pages)


class FakeClient:
    def __init__(self, pages=None, buckets=None):
        self._pages = pages or {}
        self._buckets = buckets or []
        self.calls = []

    def get_paginator(self, operation):
        return FakePaginator(self._pages.get(operation, [{}]), self.calls, operation)

    def list_buckets(self):
        return {"Buckets": [{"Name": name} for name in self._buckets]}

    def list_work_groups(self, **kwargs):
        """Athena has no paginator for this operation: pages are chained with NextToken."""
        pages = self._pages.get("list_work_groups", [{}])
        index = int(kwargs.get("NextToken", 0))
        page = dict(pages[index])
        if index + 1 < len(pages):
            page["NextToken"] = str(index + 1)
        return page


def clean_clients():
    return {
        name: FakeClient()
        for name in (
            "redshift-serverless",
            "s3",
            "iam",
            "logs",
            "ec2",
            "glue",
            "athena",
            "secretsmanager",
        )
    }


def _find(clients):
    return find_residuals(
        clients,
        prefix="redshift-lab",
        project="redshift-lab",
        glue_database="spectrumdb",
    )


def test_find_residuals_is_empty_when_everything_is_gone():
    assert _find(clean_clients()) == []


def test_find_residuals_reports_each_leftover_with_its_service():
    clients = clean_clients()
    clients["redshift-serverless"] = FakeClient(
        pages={
            "list_workgroups": [
                {
                    "workgroups": [
                        {"workgroupName": "redshift-lab-dev-wg"},
                        {"workgroupName": "other"},
                    ]
                }
            ],
            "list_namespaces": [
                {"namespaces": [{"namespaceName": "redshift-lab-dev-ns"}]}
            ],
            "list_snapshots": [
                {
                    "snapshots": [
                        {
                            "snapshotName": "manual-1",
                            "namespaceName": "redshift-lab-dev-ns",
                        }
                    ]
                }
            ],
        }
    )
    clients["s3"] = FakeClient(
        buckets=["redshift-lab-dev-123456789012-lab", "unrelated-bucket"]
    )
    clients["iam"] = FakeClient(
        pages={
            "list_roles": [{"Roles": [{"RoleName": "redshift-lab-dev-redshift-role"}]}]
        }
    )
    clients["logs"] = FakeClient(
        pages={
            "describe_log_groups": [
                {
                    "logGroups": [
                        {
                            "logGroupName": "/aws/redshift/redshift-lab-dev-ns/connectionlog"
                        }
                    ]
                }
            ]
        }
    )
    clients["glue"] = FakeClient(
        pages={
            "get_databases": [
                {"DatabaseList": [{"Name": "spectrumdb"}, {"Name": "default"}]}
            ]
        }
    )
    clients["athena"] = FakeClient(
        pages={
            "list_work_groups": [
                {"WorkGroups": [{"Name": "primary"}, {"Name": "redshift-lab-dev-wg"}]}
            ]
        }
    )
    clients["secretsmanager"] = FakeClient(
        pages={
            "list_secrets": [
                {"SecretList": [{"Name": "redshift!redshift-lab-dev-ns-awsuser"}]}
            ]
        }
    )
    clients["ec2"] = FakeClient(
        pages={"describe_vpcs": [{"Vpcs": [{"VpcId": "vpc-123"}]}]}
    )

    residuals = _find(clients)
    text = "\n".join(residuals)

    assert len(residuals) == 10
    for expected in (
        "workgroup",
        "namespace",
        "snapshot",
        "bucket",
        "role",
        "log group",
        "glue database",
        "athena",
        "secret",
        "vpc",
    ):
        assert expected in text.lower(), expected
    assert (
        "other" not in text and "unrelated-bucket" not in text and "primary" not in text
    )


def test_vpc_lookup_uses_project_tag_filter():
    clients = clean_clients()
    _find(clients)
    operation, kwargs = clients["ec2"].calls[0]
    assert operation == "describe_vpcs"
    assert kwargs["Filters"] == [{"Name": "tag:Project", "Values": ["redshift-lab"]}]


def test_tfvars_values_become_the_defaults(tmp_path, capsys):
    tfvars = tmp_path / "terraform.tfvars"
    tfvars.write_text(
        '# project_name = "commented"\nproject_name = "mylab"\nglue_database_name = "mydb"\n',
        encoding="utf-8",
    )

    assert main([], clients=clean_clients(), tfvars_path=tfvars) == 0

    out = capsys.readouterr().out
    assert "prefix=mylab" in out and "glue_database=mydb" in out


def test_a_renamed_project_is_still_checked(tmp_path):
    tfvars = tmp_path / "terraform.tfvars"
    tfvars.write_text('project_name = "mylab"\n', encoding="utf-8")
    dirty = clean_clients()
    dirty["s3"] = FakeClient(buckets=["mylab-dev-123456789012-lab"])

    assert main([], clients=dirty, tfvars_path=tfvars) == 1


def test_explicit_flags_override_tfvars(tmp_path, capsys):
    tfvars = tmp_path / "terraform.tfvars"
    tfvars.write_text('project_name = "mylab"\n', encoding="utf-8")

    main(["--prefix", "other"], clients=clean_clients(), tfvars_path=tfvars)

    assert "prefix=other" in capsys.readouterr().out


def test_missing_tfvars_falls_back_to_the_lab_defaults(tmp_path, capsys):
    main([], clients=clean_clients(), tfvars_path=tmp_path / "absent.tfvars")

    assert "prefix=redshift-lab" in capsys.readouterr().out


def test_main_exit_code_reflects_residuals(capsys):
    assert main(["--region", "us-east-1"], clients=clean_clients()) == 0
    assert "OK" in capsys.readouterr().out

    dirty = clean_clients()
    dirty["s3"] = FakeClient(buckets=["redshift-lab-dev-123456789012-lab"])
    assert main(["--region", "us-east-1"], clients=dirty) == 1
    assert "bucket" in capsys.readouterr().out.lower()


def test_every_operation_used_with_a_paginator_really_has_one():
    """Regression: boto3 has no paginator for athena list_work_groups; fakes hid it until a real run."""
    for service, operations in PAGINATED_OPERATIONS.items():
        client = boto3.client(
            service,
            region_name="us-east-1",
            aws_access_key_id="placeholder",
            aws_secret_access_key="placeholder",
        )
        for operation in operations:
            assert client.can_paginate(operation), (
                f"{service}.{operation} cannot be paginated"
            )


def test_athena_workgroups_are_followed_across_pages():
    clients = clean_clients()
    clients["athena"] = FakeClient(
        pages={
            "list_work_groups": [
                {"WorkGroups": [{"Name": "primary"}]},
                {"WorkGroups": [{"Name": "redshift-lab-dev-wg"}]},
            ]
        }
    )

    residuals = _find(clients)

    assert residuals == ["athena workgroup: redshift-lab-dev-wg"]
