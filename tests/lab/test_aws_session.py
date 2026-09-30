import os

from scripts.lab import aws_session


def _isolate(monkeypatch, *names):
    """Start from an unset variable and make monkeypatch remove whatever load_dotenv sets afterwards."""
    for name in names:
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)


def test_credentials_file_is_loaded_into_the_environment(tmp_path, monkeypatch):
    _isolate(
        monkeypatch, "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"
    )
    env_file = tmp_path / ".env.credentials"
    env_file.write_text(
        "AWS_ACCESS_KEY_ID=AKIAFAKEFAKEFAKE\nAWS_SECRET_ACCESS_KEY=fakefake\n",
        encoding="utf-8",
    )

    assert aws_session.load_credentials_file(env_file) is True
    assert os.environ["AWS_ACCESS_KEY_ID"] == "AKIAFAKEFAKEFAKE"


def test_session_token_is_loaded(tmp_path, monkeypatch):
    _isolate(monkeypatch, "AWS_SESSION_TOKEN")
    env_file = tmp_path / ".env.credentials"
    env_file.write_text("AWS_SESSION_TOKEN=faketoken\n", encoding="utf-8")

    aws_session.load_credentials_file(env_file)

    assert os.environ["AWS_SESSION_TOKEN"] == "faketoken"


def test_real_environment_wins_over_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "from-env")
    env_file = tmp_path / ".env.credentials"
    env_file.write_text("AWS_ACCESS_KEY_ID=from-file\n", encoding="utf-8")

    aws_session.load_credentials_file(env_file)

    assert os.environ["AWS_ACCESS_KEY_ID"] == "from-env"


def test_get_client_uses_tls_verification_and_the_requested_region(monkeypatch):
    captured = {}

    def fake_client(service, **kwargs):
        captured.update(service=service, **kwargs)
        return object()

    monkeypatch.setattr(aws_session.boto3, "client", fake_client)
    monkeypatch.setattr(aws_session, "load_credentials_file", lambda path=None: False)

    aws_session.get_client("athena", "us-east-1")

    assert captured == {"service": "athena", "region_name": "us-east-1"}
    assert "verify" not in captured
