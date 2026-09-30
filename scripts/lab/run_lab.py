"""Run the Redshift lab SQL against the deployed infrastructure.

Usage:
  python scripts/lab/run_lab.py --part 1            # one part (repeatable)
  python scripts/lab/run_lab.py --all               # parts 1-7
  python scripts/lab/run_lab.py --check             # validate TICKIT row counts

Reads the deployment from `terraform output -json` (run it after `terraform apply`).
Credentials come from .env.credentials or the environment.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.lab.athena import AthenaRunner  # noqa: E402
from scripts.lab.aws_session import get_client  # noqa: E402
from scripts.lab.checks import check_counts  # noqa: E402
from scripts.lab.config import load_config  # noqa: E402
from scripts.lab.redshift import RedshiftRunner  # noqa: E402
from scripts.lab.runner import LabError, format_comparison, run_part  # noqa: E402
from scripts.lab.sql import PARTS  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Redshift lab parts.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--part",
        type=int,
        choices=sorted(PARTS),
        action="append",
        help="Part number (repeatable).",
    )
    group.add_argument("--all", action="store_true", help="Run every part in order.")
    group.add_argument(
        "--check", action="store_true", help="Validate the loaded TICKIT row counts."
    )
    return parser


def selected_parts(args: argparse.Namespace) -> list[int]:
    return sorted(PARTS) if args.all else list(args.part)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()
    runners = {
        "redshift": RedshiftRunner(
            get_client("redshift-data", config.region),
            config.workgroup_name,
            config.database_name,
            config.admin_secret_arn,
        ),
        "athena": AthenaRunner(
            get_client("athena", config.region),
            config.athena_workgroup_name,
            config.glue_database_name,
        ),
    }

    if args.check:
        problems = check_counts(runners["redshift"])
        print(
            "\n".join(problems)
            if problems
            else "OK: all TICKIT tables have the expected row counts."
        )
        return 1 if problems else 0

    try:
        for part in selected_parts(args):
            print(f"\n===== Part {part} =====")
            results = run_part(part, config, runners)
            if part == 4:
                print(
                    "\n"
                    + format_comparison(
                        [r for r in results if r.sql.startswith("SELECT")]
                    )
                )
    except LabError as exc:
        print(f"\nLAB ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
