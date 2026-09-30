import pytest

from scripts.lab.config import LabConfig
from scripts.lab.redshift import Result
from scripts.lab.runner import (
    LabError,
    athena_cost_usd,
    format_comparison,
    format_table,
    run_part,
)

CONFIG = LabConfig(
    region="us-east-1",
    workgroup_name="wg",
    database_name="dev",
    admin_secret_arn="arn:secret",
    bucket_name="b",
    redshift_role_arn="arn:aws:iam::123456789012:role/r",
    no_permissions_role_arn="arn:aws:iam::123456789012:role/empty",
    athena_workgroup_name="awg",
    glue_database_name="spectrumdb",
)


class FakeRunner:
    def __init__(self, engine, ok=True, error=None, bytes_scanned=None):
        self.engine, self.ok, self.error, self.bytes_scanned = (
            engine,
            ok,
            error,
            bytes_scanned,
        )
        self.ran = []

    def run(self, sql):
        self.ran.append(sql)
        status = "FINISHED" if self.ok else "FAILED"
        return Result(
            self.engine,
            sql,
            status,
            100,
            self.bytes_scanned,
            ["c"],
            [["1"]],
            None if self.ok else self.error,
        )


def test_format_table_aligns_columns_and_limits_rows():
    text = format_table(["a", "bb"], [["1", "x"], ["22", "y"], ["3", "z"]], limit=2)
    assert text.splitlines()[0].split() == ["a", "bb"]
    assert "(1 more rows)" in text


def test_athena_cost_uses_the_10mb_minimum():
    assert athena_cost_usd(1_000_000_000_000) == pytest.approx(5.0)
    assert athena_cost_usd(0) == pytest.approx(10 * 1024**2 / 1e12 * 5)


def test_format_comparison_lists_both_engines():
    results = [
        Result("athena", "q", "FINISHED", 812, 5_000_000),
        Result("redshift", "q", "FINISHED", 95),
    ]
    text = format_comparison(results)
    assert "athena" in text and "redshift" in text and "812" in text and "95" in text


def test_run_part_executes_statements_in_order_and_returns_results():
    runners = {"redshift": FakeRunner("redshift"), "athena": FakeRunner("athena")}
    lines = []
    results = run_part(2, CONFIG, runners, out=lines.append)

    assert len(results) == 1 and runners["redshift"].ran[0].startswith("SELECT")
    assert any("SELECT" in line for line in lines)


def test_run_part_raises_on_unexpected_failure():
    runners = {
        "redshift": FakeRunner("redshift", ok=False, error="boom"),
        "athena": FakeRunner("athena"),
    }
    with pytest.raises(LabError, match="boom"):
        run_part(2, CONFIG, runners, out=lambda line: None)


def test_expected_error_is_reported_and_execution_continues():
    redshift = FakeRunner("redshift")
    original_run = redshift.run
    outcomes = iter([False] + [True] * 10)

    def run(sql):
        redshift.ok = next(outcomes)
        redshift.error = "S3ServiceException: Access Denied"
        return original_run(sql)

    redshift.run = run
    lines = []
    results = run_part(
        7,
        CONFIG,
        {"redshift": redshift, "athena": FakeRunner("athena")},
        out=lines.append,
    )

    assert len(results) == 5
    assert any("Access Denied" in line for line in lines)


def test_expected_error_that_succeeds_raises():
    runners = {
        "redshift": FakeRunner("redshift", ok=True),
        "athena": FakeRunner("athena"),
    }
    with pytest.raises(LabError, match="expected to fail"):
        run_part(7, CONFIG, runners, out=lambda line: None)
