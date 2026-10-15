from pathlib import Path

import pytest
from pydantic import ValidationError

from tactistream.settings import Settings

ENV_EXAMPLE = Path(__file__).parents[3] / ".env.example"

PLATFORM_ENV = {
    "TACTISTREAM_ARTIFACT_STORE": "blob",
    "TACTISTREAM_ANALYTICS_PUBLISH": "on",
    "TACTISTREAM_HISTORY": "eventhouse",
    "TACTISTREAM_HISTORY_TIMEOUT_MS": "900",
    "TACTISTREAM_STATIC_DIR": "/app/frontend/dist",
    "TACTISTREAM_ENVIRONMENT": "production",
    "AZURE_CLIENT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_STORAGE_ACCOUNT_URL": "https://acct.blob.core.windows.net",
    "FABRIC_KUSTO_QUERY_URI": "https://eh.kusto.fabric.microsoft.com",
    "FABRIC_KUSTO_DATABASE": "tactistream",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    names = {line.split("=", 1)[0] for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines() if line}
    for name in names | set(PLATFORM_ENV):
        monkeypatch.delenv(name, raising=False)


def test_platform_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.artifact_store == "local"
    assert s.analytics_publish is False
    assert s.history == "memory"
    assert s.history_timeout_ms == 1500
    assert s.environment == "dev"
    assert s.azure_client_id is None


def test_platform_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in PLATFORM_ENV.items():
        monkeypatch.setenv(name, value)
    s = Settings(_env_file=None)
    assert s.artifact_store == "blob"
    assert s.analytics_publish is True
    assert s.history == "eventhouse"
    assert s.history_timeout_ms == 900
    assert s.static_dir == Path("/app/frontend/dist")
    assert s.environment == "production"
    assert s.azure_client_id == "00000000-0000-0000-0000-000000000001"
    assert s.azure_storage_account_url == "https://acct.blob.core.windows.net"
    assert s.fabric_kusto_query_uri == "https://eh.kusto.fabric.microsoft.com"
    assert s.fabric_kusto_database == "tactistream"


@pytest.mark.parametrize(("value", "expected"), [("off", False), ("on", True), ("false", False)])
def test_analytics_publish_accepts_on_off(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("TACTISTREAM_ANALYTICS_PUBLISH", value)
    assert Settings(_env_file=None).analytics_publish is expected


def test_history_off_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACTISTREAM_HISTORY", "off")
    assert Settings(_env_file=None).history == "off"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TACTISTREAM_ARTIFACT_STORE", "s3"),
        ("TACTISTREAM_HISTORY", "cosmos"),
        ("TACTISTREAM_HISTORY_TIMEOUT_MS", "0"),
    ],
)
def test_invalid_platform_values_rejected(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_blob_store_requires_storage_account_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACTISTREAM_ARTIFACT_STORE", "blob")
    with pytest.raises(ValidationError, match="AZURE_STORAGE_ACCOUNT_URL"):
        Settings(_env_file=None)


def test_eventhouse_history_requires_query_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TACTISTREAM_HISTORY", "eventhouse")
    with pytest.raises(ValidationError, match="FABRIC_KUSTO_QUERY_URI"):
        Settings(_env_file=None)
