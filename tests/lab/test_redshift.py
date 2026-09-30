from scripts.lab.redshift import RedshiftRunner


class FakeDataApi:
    def __init__(
        self,
        statuses,
        has_result=False,
        records=None,
        columns=None,
        duration=2_500_000_000,
        error=None,
    ):
        self._statuses = list(statuses)
        self._has_result = has_result
        self._records = records or []
        self._columns = columns or []
        self._duration = duration
        self._error = error
        self.executed = None

    def execute_statement(self, **kwargs):
        self.executed = kwargs
        return {"Id": "stmt-1"}

    def describe_statement(self, Id):
        status = self._statuses.pop(0)
        described = {
            "Status": status,
            "HasResultSet": self._has_result,
            "Duration": self._duration,
        }
        if self._error and status in ("FAILED", "ABORTED"):
            described["Error"] = self._error
        return described

    def get_statement_result(self, Id, **kwargs):
        return {
            "ColumnMetadata": [{"name": c} for c in self._columns],
            "Records": self._records,
        }


def _runner(client):
    return RedshiftRunner(
        client, "wg", "dev", "arn:secret", poll_seconds=0, sleep=lambda s: None
    )


def test_run_passes_workgroup_database_and_secret_and_polls_until_finished():
    client = FakeDataApi(["STARTED", "FINISHED"])
    result = _runner(client).run("SELECT 1")

    assert client.executed == {
        "WorkgroupName": "wg",
        "Database": "dev",
        "SecretArn": "arn:secret",
        "Sql": "SELECT 1",
    }
    assert result.ok and result.engine == "redshift"
    assert result.duration_ms == 2500


def test_run_returns_rows_and_columns_for_selects():
    records = [
        [{"longValue": 7}, {"stringValue": "x"}],
        [{"isNull": True}, {"stringValue": "y"}],
    ]
    client = FakeDataApi(
        ["FINISHED"], has_result=True, records=records, columns=["a", "b"]
    )
    result = _runner(client).run("SELECT a, b FROM t")

    assert result.columns == ["a", "b"]
    assert result.rows == [["7", "x"], ["NULL", "y"]]


def test_run_reports_failures_without_raising():
    client = FakeDataApi(["FAILED"], error="S3ServiceException: Access Denied")
    result = _runner(client).run("COPY ...")

    assert not result.ok
    assert result.error == "S3ServiceException: Access Denied"
