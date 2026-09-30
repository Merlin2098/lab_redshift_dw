"""Verify that `terraform destroy` left nothing behind (read-only).

Usage:
  python scripts/lab/verify_teardown.py [--prefix redshift-lab] [--project redshift-lab]
                                        [--glue-database spectrumdb] [--region us-east-1]

Exit code 0 = clean, 1 = residual resources were found (they are listed).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.lab.aws_session import get_client  # noqa: E402
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


def main(argv: list[str] | None = None, clients=None) -> int:
    parser = argparse.ArgumentParser(
        description="Look for resources left after terraform destroy."
    )
    parser.add_argument(
        "--prefix",
        default="redshift-lab",
        help="Name prefix (project_name) of the lab resources.",
    )
    parser.add_argument(
        "--project", default="redshift-lab", help="Value of the Project tag."
    )
    parser.add_argument("--glue-database", default="spectrumdb")
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args(argv)

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
