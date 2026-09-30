"""Expected TICKIT row counts, used by `run_lab.py --check`."""

from __future__ import annotations

# Source: AWS TICKIT sample database documentation. Not re-verified against a live load:
# confirm on the first deployment and fix here if AWS changed the dataset.
EXPECTED_COUNTS: dict[str, int] = {
    "users": 49990,
    "venue": 202,
    "category": 11,
    "date": 365,
    "event": 8798,
    "listing": 192497,
    "sales": 172456,
}


def check_counts(runner) -> list[str]:
    """Return one message per table whose row count differs from the expected one."""
    problems: list[str] = []
    for table, expected in EXPECTED_COUNTS.items():
        result = runner.run(f"SELECT COUNT(*) FROM {table}")
        if not result.ok:
            problems.append(f"{table}: query failed: {result.error}")
            continue
        actual = int(result.rows[0][0])
        if actual != expected:
            problems.append(f"{table}: expected {expected}, found {actual}")
    return problems
