from scripts.lab.checks import EXPECTED_COUNTS, check_counts
from scripts.lab.redshift import Result


class CountRunner:
    def __init__(self, counts):
        self.counts = counts

    def run(self, sql):
        table = sql.split("FROM ")[1].strip()
        return Result("redshift", sql, "FINISHED", 1, rows=[[str(self.counts[table])]])


def test_no_discrepancies_when_counts_match():
    assert check_counts(CountRunner(dict(EXPECTED_COUNTS))) == []


def test_reports_each_mismatch():
    counts = dict(EXPECTED_COUNTS)
    counts["sales"] = 1
    problems = check_counts(CountRunner(counts))
    assert len(problems) == 1 and "sales" in problems[0]


def test_expected_counts_cover_the_seven_tickit_tables():
    assert set(EXPECTED_COUNTS) == {
        "users",
        "venue",
        "category",
        "date",
        "event",
        "listing",
        "sales",
    }
