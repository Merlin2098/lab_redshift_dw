"""Runs one lab part and formats what the student sees."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from scripts.lab.config import LabConfig
from scripts.lab.redshift import Result
from scripts.lab.sql import statements_for_part

ATHENA_MIN_BYTES = 10 * 1024**2
ATHENA_USD_PER_TB = 5.0


class LabError(Exception):
    """A lab statement failed unexpectedly, or an expected failure did not happen."""


class Runner(Protocol):
    def run(self, sql: str) -> Result: ...


def format_table(columns: list[str], rows: list[list[str]], limit: int = 10) -> str:
    shown = rows[:limit]
    widths = [
        max(len(str(c)) for c in [col, *[row[i] for row in shown]])
        for i, col in enumerate(columns)
    ]
    lines = [
        "  ".join(
            str(col).ljust(width) for col, width in zip(columns, widths, strict=True)
        )
    ]
    lines += [
        "  ".join(
            str(cell).ljust(width) for cell, width in zip(row, widths, strict=True)
        )
        for row in shown
    ]
    if len(rows) > limit:
        lines.append(f"({len(rows) - limit} more rows)")
    return "\n".join(lines)


def athena_cost_usd(bytes_scanned: int) -> float:
    """Approximate Athena cost: $5 per TB scanned, with a 10 MB minimum per query."""
    return max(bytes_scanned, ATHENA_MIN_BYTES) / 1e12 * ATHENA_USD_PER_TB


def format_comparison(results: list[Result]) -> str:
    lines = [
        f"{'engine':<10} {'time (ms)':>10} {'scanned (bytes)':>16} {'est. cost (USD)':>16}"
    ]
    for result in results:
        scanned = "-" if result.bytes_scanned is None else f"{result.bytes_scanned:,}"
        cost = (
            "workgroup RPUs"
            if result.engine == "redshift"
            else f"~{athena_cost_usd(result.bytes_scanned or 0):.6f}"
        )
        duration = result.duration_ms if result.duration_ms is not None else "-"
        lines.append(f"{result.engine:<10} {duration:>10} {scanned:>16} {cost:>16}")
    return "\n".join(lines)


def run_part(
    part: int,
    config: LabConfig,
    runners: Mapping[str, Runner],
    out: Callable[[str], None] = print,
) -> list[Result]:
    results: list[Result] = []
    for statement in statements_for_part(part, config.sql_values()):
        out(f"\n-- [{statement.engine}]\n{statement.sql};")
        result = runners[statement.engine].run(statement.sql)
        if statement.expect_error:
            if result.ok:
                raise LabError(
                    f"statement was expected to fail but succeeded: {statement.sql[:80]}"
                )
            out(f"Expected error: {result.error}")
        elif not result.ok:
            raise LabError(
                f"[{statement.engine}] {result.status}: {result.error}\n{statement.sql}"
            )
        elif result.rows:
            out(format_table(result.columns, result.rows))
        results.append(result)
    return results
