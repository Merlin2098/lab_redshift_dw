"""The console guide must show exactly the SQL that sql/ runs: no hand-copied drift."""

from pathlib import Path

import pytest

from scripts.lab.sql import PARTS, SQL_DIR, render, split_statements

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "02_laboratorio_consola_aws.md"

# How the guide names the values a student reads from `terraform output`.
GUIDE_VALUES = {
    "bucket": "<bucket_name>",
    "glue_database": "spectrumdb",
    "no_permissions_role_arn": "<no_permissions_role_arn>",
    "redshift_role_arn": "<redshift_role_arn>",
}


def _sql_files():
    return sorted({name for files in PARTS.values() for name in files})


@pytest.mark.parametrize("name", _sql_files())
def test_every_statement_of_every_sql_file_appears_in_the_guide(name):
    guide = GUIDE.read_text(encoding="utf-8")
    text = render((SQL_DIR / name).read_text(encoding="utf-8"), GUIDE_VALUES)
    for statement in split_statements(text):
        assert statement.sql in guide, (
            f"{name}: statement missing from the guide:\n{statement.sql[:120]}"
        )


def test_the_guide_never_asks_for_the_database_user_and_password_method():
    """That method makes Query Editor v2 create a secret that Terraform cannot destroy."""
    guide = GUIDE.read_text(encoding="utf-8")
    assert "AWS Secrets Manager" in guide
    assert (
        "sqlworkbench" in guide
    )  # the warning explains why the other method is avoided


def test_the_guide_has_no_leftover_template_placeholders():
    guide = GUIDE.read_text(encoding="utf-8")
    assert "{{" not in guide and "${" not in guide
