from scripts.lab.athena import AthenaRunner


class FakeAthena:
    def __init__(self, states, rows=None, stats=None, reason=None):
        self._states = list(states)
        self._rows = rows or []
        self._stats = stats or {}
        self._reason = reason
        self.started = None

    def start_query_execution(self, **kwargs):
        self.started = kwargs
        return {"QueryExecutionId": "q-1"}

    def get_query_execution(self, QueryExecutionId):
        state = self._states.pop(0)
        status = {"State": state}
        if self._reason:
            status["StateChangeReason"] = self._reason
        return {"QueryExecution": {"Status": status, "Statistics": self._stats}}

    def get_query_results(self, QueryExecutionId, **kwargs):
        return {"ResultSet": {"Rows": self._rows}}


def _runner(client):
    return AthenaRunner(
        client, "wg", "spectrumdb", poll_seconds=0, sleep=lambda s: None
    )


def test_run_normalizes_succeeded_and_collects_statistics():
    rows = [
        {"Data": [{"VarCharValue": "dateid"}, {"VarCharValue": "ventas"}]},
        {"Data": [{"VarCharValue": "1827"}, {"VarCharValue": "33"}]},
    ]
    client = FakeAthena(
        ["RUNNING", "SUCCEEDED"],
        rows=rows,
        stats={"EngineExecutionTimeInMillis": 812, "DataScannedInBytes": 5_000_000},
    )
    result = _runner(client).run("SELECT 1")

    assert client.started["WorkGroup"] == "wg"
    assert client.started["QueryExecutionContext"] == {"Database": "spectrumdb"}
    assert result.ok and result.engine == "athena"
    assert result.duration_ms == 812 and result.bytes_scanned == 5_000_000
    assert result.columns == ["dateid", "ventas"] and result.rows == [["1827", "33"]]


def test_run_reports_failure_reason():
    client = FakeAthena(["FAILED"], reason="SYNTAX_ERROR")
    result = _runner(client).run("SELEC")

    assert (
        not result.ok and result.status == "FAILED" and result.error == "SYNTAX_ERROR"
    )
