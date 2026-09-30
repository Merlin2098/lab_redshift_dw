"""Shared AWS session helper: loads .env.credentials and builds boto3 clients.

boto3's default credential chain is used after the file is loaded, so temporary
credentials (AWS_SESSION_TOKEN) work. TLS verification stays on (see
scripts/testing/check_ssl_regression.py: the Python 3.14 workaround is no longer needed).
"""

from __future__ import annotations

import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGION = "us-east-1"


def load_credentials_file(path: Path | None = None) -> bool:
    """Load .env.credentials into the environment. Variables already set are not overridden."""
    return load_dotenv(path or REPO_ROOT / ".env.credentials")


def get_client(service: str, region: str | None = None):
    load_credentials_file()
    return boto3.client(
        service,
        region_name=region or os.environ.get("AWS_DEFAULT_REGION", DEFAULT_REGION),
    )
