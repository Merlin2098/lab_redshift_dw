"""Athena runner with the same Result shape as the Redshift runner."""

from __future__ import annotations

import time

from scripts.lab.redshift import Result

_TERMINAL = ("SUCCEEDED", "FAILED", "CANCELLED")


class AthenaRunner:
    def __init__(
        self,
        client,
        workgroup: str,
        database: str,
        poll_seconds: float = 1.0,
        sleep=time.sleep,
    ):
        self._client = client
        self._workgroup = workgroup
        self._database = database
        self._poll_seconds = poll_seconds
        self._sleep = sleep

    def run(self, sql: str) -> Result:
        query_id = self._client.start_query_execution(
            QueryString=sql,
            WorkGroup=self._workgroup,
            QueryExecutionContext={"Database": self._database},
        )["QueryExecutionId"]
        while True:
            execution = self._client.get_query_execution(QueryExecutionId=query_id)[
                "QueryExecution"
            ]
            state = execution["Status"]["State"]
            if state in _TERMINAL:
                break
            self._sleep(self._poll_seconds)

        statistics = execution.get("Statistics", {})
        result = Result(
            "athena",
            sql,
            "FINISHED" if state == "SUCCEEDED" else state,
            statistics.get("EngineExecutionTimeInMillis"),
            statistics.get("DataScannedInBytes"),
            error=execution["Status"].get("StateChangeReason"),
        )
        if result.ok:
            result.columns, result.rows = self._fetch(query_id)
        return result

    def _fetch(self, query_id: str) -> tuple[list[str], list[list[str]]]:
        rows: list[list[str]] = []
        token: str | None = None
        first_page = True
        columns: list[str] = []
        while True:
            kwargs = {"NextToken": token} if token else {}
            page = self._client.get_query_results(QueryExecutionId=query_id, **kwargs)
            page_rows = [
                [cell.get("VarCharValue", "NULL") for cell in row["Data"]]
                for row in page["ResultSet"]["Rows"]
            ]
            if first_page and page_rows:
                columns, page_rows = page_rows[0], page_rows[1:]
            first_page = False
            rows.extend(page_rows)
            token = page.get("NextToken")
            if not token:
                return columns, rows
