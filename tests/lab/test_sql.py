import re

import pytest

from scripts.lab.sql import (
    PARTS,
    SQL_DIR,
    Statement,
    render,
    split_statements,
    statements_for_part,
)

VALUES = {
    "bucket": "my-bucket",
    "glue_database": "spectrumdb",
    "no_permissions_role_arn": "arn:aws:iam::123456789012:role/empty",
    "redshift_role_arn": "arn:aws:iam::123456789012:role/redshift",
}


def test_split_basic_and_ignores_comments():
    text = "-- a comment\nSELECT 1; -- trailing\nSELECT 2;\n"
    assert [s.sql for s in split_statements(text)] == ["SELECT 1", "SELECT 2"]


def test_split_keeps_semicolons_and_dashes_inside_quotes():
    text = "SELECT 'a;b--c';\nSELECT 2;"
    assert [s.sql for s in split_statements(text)] == ["SELECT 'a;b--c'", "SELECT 2"]


def test_split_handles_escaped_quotes():
    text = "SELECT 'it''s; fine';SELECT 2;"
    assert [s.sql for s in split_statements(text)] == [
        "SELECT 'it''s; fine'",
        "SELECT 2",
    ]


def test_split_last_statement_without_semicolon():
    assert [s.sql for s in split_statements("SELECT 1")] == ["SELECT 1"]


def test_engine_directive_persists_and_expect_error_applies_once():
    text = "-- @engine: athena\nSELECT 1;\nSELECT 2;\n-- @engine: redshift\n-- @expect-error\nSELECT 3;\nSELECT 4;"
    assert split_statements(text) == [
        Statement("SELECT 1", "athena", False),
        Statement("SELECT 2", "athena", False),
        Statement("SELECT 3", "redshift", True),
        Statement("SELECT 4", "redshift", False),
    ]


def test_render_substitutes_and_fails_on_missing_placeholder():
    assert (
        render("COPY x TO 's3://${bucket}/y'", {"bucket": "b"})
        == "COPY x TO 's3://b/y'"
    )
    with pytest.raises(KeyError):
        render("${missing}", {})


def test_every_part_file_exists_and_renders_with_the_standard_values():
    for part, files in PARTS.items():
        assert files, f"part {part} has no files"
        for name in files:
            assert (SQL_DIR / name).is_file(), name
        assert statements_for_part(part, VALUES), f"part {part} produced no statements"


def test_no_hardcoded_account_arns_in_sql():
    for path in SQL_DIR.glob("*.sql"):
        assert not re.search(
            r"arn:aws:iam::\d{12}", path.read_text(encoding="utf-8")
        ), path.name


def test_ddl_drops_every_table_before_creating():
    text = (SQL_DIR / "01_ddl.sql").read_text(encoding="utf-8")
    for table in ("sales", "listing", "event", "date", "category", "venue", "users"):
        assert f"DROP TABLE IF EXISTS {table};" in text
        assert text.index(f"DROP TABLE IF EXISTS {table};") < text.index(
            f"CREATE TABLE {table}("
        )


def test_part_7_marks_the_denied_copy_as_expected_error():
    statements = statements_for_part(7, VALUES)
    assert statements[0].expect_error is True
    assert "empty" in statements[0].sql
    assert not any(s.expect_error for s in statements[1:])


def test_part_4_compares_both_engines():
    engines = [
        s.engine for s in statements_for_part(4, VALUES) if s.sql.startswith("SELECT")
    ]
    assert engines == ["athena", "redshift"]
