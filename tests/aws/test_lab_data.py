import pytest

from scripts.lab.aws_session import get_client
from scripts.lab.checks import check_counts
from scripts.lab.redshift import RedshiftRunner

pytestmark = pytest.mark.cloud


def test_tickit_tables_have_the_expected_counts(lab_config):
    runner = RedshiftRunner(
        get_client("redshift-data", lab_config.region),
        lab_config.workgroup_name,
        lab_config.database_name,
        lab_config.admin_secret_arn,
    )
    assert check_counts(runner) == []
