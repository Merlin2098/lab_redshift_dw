"""SQL file loading, placeholder rendering and statement splitting for the Redshift lab."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from string import Template

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"

# Part number (as in docs/02_laboratorio_consola_aws.md) -> SQL files, in execution order.
# Parts 4 and 6 both need the external table, so both start with 07_spectrum_setup.sql (idempotent).
PARTS: dict[int, tuple[str, ...]] = {
    1: ("01_ddl.sql", "02_copy.sql"),
    2: ("03_star_schema.sql",),
    3: ("04_analytics.sql",),
    4: ("07_spectrum_setup.sql", "05_athena_vs_redshift.sql"),
    5: ("06_unload.sql",),
    6: ("07_spectrum_setup.sql", "07_spectrum_queries.sql"),
    7: ("08_troubleshooting.sql",),
}

_ENGINE = re.compile(r"^--\s*@engine:\s*(\w+)\s*$")
_EXPECT_ERROR = re.compile(r"^--\s*@expect-error\s*$")


@dataclass(frozen=True)
class Statement:
    sql: str
    engine: str = "redshift"
    expect_error: bool = False


def render(text: str, values: Mapping[str, str]) -> str:
    """Substitute ${name} placeholders. Raises KeyError if a placeholder has no value."""
    return Template(text).substitute(values)


def split_statements(text: str) -> list[Statement]:
    """Split SQL text into statements, honoring quotes, `--` comments and the lab directives.

    Directives are recognised only on their own line, outside a statement:
    `-- @engine: athena` sets the engine for the statements that follow;
    `-- @expect-error` marks only the next statement.
    """
    statements: list[Statement] = []
    engine = "redshift"
    expect_error = False
    buffer: list[str] = []
    in_quote = False

    def flush() -> None:
        nonlocal expect_error
        sql = "".join(buffer).strip()
        buffer.clear()
        if sql:
            statements.append(Statement(sql, engine, expect_error))
            expect_error = False

    for line in text.splitlines():
        if not in_quote and not "".join(buffer).strip():
            engine_match = _ENGINE.match(line.strip())
            if engine_match:
                engine = engine_match.group(1)
                continue
            if _EXPECT_ERROR.match(line.strip()):
                expect_error = True
                continue
        index = 0
        while index < len(line):
            char = line[index]
            if in_quote:
                buffer.append(char)
                if char == "'":
                    in_quote = False
            elif char == "'":
                in_quote = True
                buffer.append(char)
            elif line.startswith("--", index):
                break
            elif char == ";":
                flush()
            else:
                buffer.append(char)
            index += 1
        buffer.append("\n")
    flush()
    return statements


def statements_for_part(part: int, values: Mapping[str, str]) -> list[Statement]:
    """Render and split every file of a part, in order."""
    statements: list[Statement] = []
    for name in PARTS[part]:
        text = render((SQL_DIR / name).read_text(encoding="utf-8"), values)
        statements.extend(split_statements(text))
    return statements
