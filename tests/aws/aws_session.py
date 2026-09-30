"""Client factory for the cloud tests. Thin wrapper over the shared lab helper."""

from scripts.lab.aws_session import get_client

__all__ = ["get_client"]
