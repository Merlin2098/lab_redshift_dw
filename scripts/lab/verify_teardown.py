"""Verify that `terraform destroy` left nothing behind (read-only).

Usage:
  python scripts/lab/verify_teardown.py [--prefix P] [--project P] [--glue-database D] [--region R]

The prefix, project tag and Glue database default to the values in infra/terraform.tfvars
(project_name, glue_database_name) and fall back to the lab defaults (redshift-lab, spectrumdb).
The values being checked are printed first, so a renamed project cannot pass unnoticed.

Exit code 0 = clean, 1 = residual resources were found (they are listed).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.lab.aws_session import REPO_ROOT, get_client  # noqa: E402
from scripts.lab.teardown import find_residuals  # noqa: E402

SERVICES = (
    "redshift-serverless",
    "s3",
    "iam",
    "logs",
    "ec2",
    "glue",
    "athena",
    "secretsmanager",
)
DEFAULT_TFVARS = REPO_ROOT / "infra" / "terraform.tfvars"
DEFAULT_PROJECT = "redshift-lab"
DEFAULT_GLUE_DATABASE = "spectrumdb"
_TFVAR = re.compile(
    r'^\s*(project_name|glue_database_name)\s*=\s*"([^"]*)"', re.MULTILINE
)


def read_tfvars(path: Path) -> dict[str, str]:
    """Return project_name / glue_database_name from a tfvars file; empty if it is absent."""
    if not path.is_file():
        return {}
    return dict(_TFVAR.findall(path.read_text(encoding="utf-8")))


def main(
    argv: list[str] | None = None, clients=None, tfvars_path: Path = DEFAULT_TFVARS
) -> int:
    tfvars = read_tfvars(tfvars_path)
    project_default = tfvars.get("project_name", DEFAULT_PROJECT)

    parser = argparse.ArgumentParser(
        description="Look for resources left after terraform destroy."
    )
    parser.add_argument(
        "--prefix",
        default=project_default,
        help="Name prefix (project_name) of the lab resources.",
    )
    parser.add_argument(
        "--project", default=project_default, help="Value of the Project tag."
    )
    parser.add_argument(
        "--glue-database",
        default=tfvars.get("glue_database_name", DEFAULT_GLUE_DATABASE),
    )
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args(argv)

    print(
        f"Checking prefix={args.prefix} project={args.project} "
        f"glue_database={args.glue_database} region={args.region}"
    )
    clients = clients or {
        service: get_client(service, args.region) for service in SERVICES
    }
    residuals = find_residuals(
        clients,
        prefix=args.prefix,
        project=args.project,
        glue_database=args.glue_database,
    )

    if not residuals:
        print("OK: no residual lab resources found.")
        return 0
    print("Residual resources found (delete them or run `terraform destroy` again):")
    print("\n".join(f"  - {item}" for item in residuals))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
