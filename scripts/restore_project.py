# Restores the project to a consistent state after cloning or switching branches.
# Runs `uv sync` (including the dev dependency-group) to sync .venv with pyproject.toml/uv.lock.
# Usage: python scripts/restore_project.py [--project-root <path>] [--dry-run] [--pretty]
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def install_requirements(project_root: Path, *, dry_run: bool) -> dict[str, object]:
    if not (project_root / "pyproject.toml").exists():
        return {"status": "skipped", "reason": "no pyproject.toml found"}

    command = ["uv", "sync"]

    if dry_run:
        return {"status": "skipped", "reason": "dry-run", "command": command}

    subprocess.run(command, cwd=project_root, check=True)
    return {"status": "ok"}


def restore_project(project_root: Path, *, dry_run: bool = False) -> dict[str, object]:
    project_root = project_root.resolve()
    dependencies = install_requirements(project_root, dry_run=dry_run)

    return {
        "status": "ok",
        "dependencies": dependencies,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore a host by installing requirements."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        payload = restore_project(Path(args.project_root), dry_run=args.dry_run)
    except ValueError as exc:
        payload = {"status": "error", "error": str(exc)}
        print(json.dumps(payload, indent=2 if args.pretty else None))
        return 1

    print(json.dumps(payload, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
