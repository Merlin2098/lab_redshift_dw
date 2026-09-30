"""Redshift Data API runner (one statement per call: CREATE EXTERNAL TABLE cannot run in a transaction)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

_TERMINAL = ("FINISHED", "FAILED", "ABORTED")


@dataclass
class Result:
    engine: str
    sql: str
    status: str
    duration_ms: int | None
    bytes_scanned: int | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "FINISHED"


def _cell(value: dict[str, Any]) -> str:
    if value.get("isNull"):
        return "NULL"
    return str(next(iter(value.values())))


class RedshiftRunner:
    def __init__(
        self,
        client,
        workgroup: str,
        database: str,
        secret_arn: str,
        poll_seconds: float = 1.0,
        sleep=time.sleep,
    ):
        self._client = client
        self._workgroup = workgroup
        self._database = database
        self._secret_arn = secret_arn
        self._poll_seconds = poll_seconds
        self._sleep = sleep

    def run(self, sql: str) -> Result:
        statement_id = self._client.execute_statement(
            WorkgroupName=self._workgroup,
            Database=self._database,
            SecretArn=self._secret_arn,
            Sql=sql,
        )["Id"]
        while True:
            described = self._client.describe_statement(Id=statement_id)
            if described["Status"] in _TERMINAL:
                break
            self._sleep(self._poll_seconds)

        nanoseconds = described.get("Duration")
        duration_ms = (
            nanoseconds // 1_000_000
            if isinstance(nanoseconds, int) and nanoseconds >= 0
            else None
        )
        result = Result(
            "redshift",
            sql,
            described["Status"],
            duration_ms,
            error=described.get("Error"),
        )
        if result.ok and described.get("HasResultSet"):
            result.columns, result.rows = self._fetch(statement_id)
        return result

    def _fetch(self, statement_id: str) -> tuple[list[str], list[list[str]]]:
        columns: list[str] = []
        rows: list[list[str]] = []
        token: str | None = None
        while True:
            kwargs = {"NextToken": token} if token else {}
            page = self._client.get_statement_result(Id=statement_id, **kwargs)
            columns = columns or [
                column["name"] for column in page.get("ColumnMetadata", [])
            ]
            rows.extend(
                [_cell(value) for value in record] for record in page.get("Records", [])
            )
            token = page.get("NextToken")
            if not token:
                return columns, rows
