import pytest

from scripts.lab.aws_session import get_client
from scripts.lab.config import load_config


@pytest.fixture(scope="session")
def lab_config():
    """Deployment settings from terraform output. Skips when there are no credentials or no deployment."""
    try:
        get_client("sts", "us-east-1").get_caller_identity()
    except Exception as exc:  # noqa: BLE001 - any failure means "no usable credentials"
        pytest.skip(f"no usable AWS credentials: {exc}")
    try:
        return load_config()
    except (RuntimeError, ValueError) as exc:
        pytest.skip(f"lab is not deployed: {exc}")
