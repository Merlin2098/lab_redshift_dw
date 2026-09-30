"""Lab configuration read from `terraform output -json` (no hardcoded environment values)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[2] / "infra"


@dataclass(frozen=True)
class LabConfig:
    region: str
    workgroup_name: str
    database_name: str
    admin_secret_arn: str
    bucket_name: str
    redshift_role_arn: str
    no_permissions_role_arn: str
    athena_workgroup_name: str
    glue_database_name: str

    def sql_values(self) -> dict[str, str]:
        """Values for the ${placeholders} used in sql/*.sql."""
        return {
            "bucket": self.bucket_name,
            "glue_database": self.glue_database_name,
            "no_permissions_role_arn": self.no_permissions_role_arn,
            "redshift_role_arn": self.redshift_role_arn,
        }


def parse_outputs(raw: str) -> LabConfig:
    data = json.loads(raw)
    try:
        return LabConfig(
            region=data["aws_region"]["value"],
            workgroup_name=data["workgroup_name"]["value"],
            database_name=data["database_name"]["value"],
            admin_secret_arn=data["admin_secret_arn"]["value"],
            bucket_name=data["bucket_name"]["value"],
            redshift_role_arn=data["redshift_role_arn"]["value"],
            no_permissions_role_arn=data["no_permissions_role_arn"]["value"],
            athena_workgroup_name=data["athena_workgroup_name"]["value"],
            glue_database_name=data["glue_database_name"]["value"],
        )
    except KeyError as exc:
        raise ValueError(
            f"terraform output is missing {exc}; has the infra been applied?"
        ) from exc


def load_config(infra_dir: Path = INFRA_DIR) -> LabConfig:
    result = subprocess.run(
        ["terraform", f"-chdir={infra_dir}", "output", "-json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"terraform output failed: {result.stderr.strip()}")
    return parse_outputs(result.stdout)
