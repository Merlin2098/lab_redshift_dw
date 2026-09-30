"""Read-only search for resources that survive `terraform destroy`.

Everything is matched by name prefix or by the Project tag, never by Terraform state, so it still
works if terraform.tfstate was lost.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _paginate(client, operation: str, key: str, **kwargs) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in client.get_paginator(operation).paginate(**kwargs):
        items.extend(page.get(key, []))
    return items


def find_residuals(
    clients: Mapping[str, Any], *, prefix: str, project: str, glue_database: str
) -> list[str]:
    residuals: list[str] = []

    serverless = clients["redshift-serverless"]
    residuals += [
        f"redshift-serverless workgroup: {wg['workgroupName']}"
        for wg in _paginate(serverless, "list_workgroups", "workgroups")
        if wg["workgroupName"].startswith(prefix)
    ]
    residuals += [
        f"redshift-serverless namespace: {ns['namespaceName']}"
        for ns in _paginate(serverless, "list_namespaces", "namespaces")
        if ns["namespaceName"].startswith(prefix)
    ]
    residuals += [
        f"redshift-serverless snapshot (billed): {snap['snapshotName']}"
        for snap in _paginate(serverless, "list_snapshots", "snapshots")
        if snap.get("namespaceName", "").startswith(prefix)
    ]

    residuals += [
        f"s3 bucket: {bucket['Name']}"
        for bucket in clients["s3"].list_buckets()["Buckets"]
        if bucket["Name"].startswith(prefix) and bucket["Name"].endswith("-lab")
    ]
    residuals += [
        f"iam role: {role['RoleName']}"
        for role in _paginate(clients["iam"], "list_roles", "Roles")
        if role["RoleName"].startswith(prefix)
    ]
    residuals += [
        f"cloudwatch log group: {group['logGroupName']}"
        for group in _paginate(
            clients["logs"],
            "describe_log_groups",
            "logGroups",
            logGroupNamePrefix=f"/aws/redshift/{prefix}",
        )
    ]
    residuals += [
        f"vpc (tag Project={project}): {vpc['VpcId']}"
        for vpc in _paginate(
            clients["ec2"],
            "describe_vpcs",
            "Vpcs",
            Filters=[{"Name": "tag:Project", "Values": [project]}],
        )
    ]
    residuals += [
        f"glue database: {db['Name']}"
        for db in _paginate(clients["glue"], "get_databases", "DatabaseList")
        if db["Name"] == glue_database
    ]
    residuals += [
        f"athena workgroup: {wg['Name']}"
        for wg in _paginate(clients["athena"], "list_work_groups", "WorkGroups")
        if wg["Name"].startswith(prefix)
    ]
    # Secrets already scheduled for deletion are excluded by list_secrets
    # (IncludePlannedDeletion defaults to false).
    residuals += [
        f"secrets manager secret: {secret['Name']}"
        for secret in _paginate(
            clients["secretsmanager"],
            "list_secrets",
            "SecretList",
            Filters=[{"Key": "name", "Values": [f"redshift!{prefix}"]}],
        )
    ]
    return residuals
