"""Environment-driven configuration; variable names match `.env.example`."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    bus: Literal["memory", "eventhubs"] = Field(default="memory", validation_alias="TACTISTREAM_BUS")
    agents: Literal["off", "scripted", "foundry"] = Field(
        default="off", validation_alias="TACTISTREAM_AGENTS"
    )
    narrative_deadline_ms: int = Field(
        default=8000, gt=0, validation_alias="TACTISTREAM_NARRATIVE_DEADLINE_MS"
    )
    data_dir: Path = Field(default=_REPO_ROOT / "data", validation_alias="TACTISTREAM_DATA_DIR")
    static_dir: Path | None = Field(
        default=_REPO_ROOT / "frontend" / "dist", validation_alias="TACTISTREAM_STATIC_DIR"
    )

    eventhubs_fully_qualified_namespace: str | None = None
    eventhubs_name: str = "tactistream-feed"
    eventhubs_consumer_group: str = "live-state"

    foundry_project_endpoint: str | None = None
    foundry_model_deployment: str | None = None

    applicationinsights_connection_string: str | None = None
    azure_client_id: str | None = None
    azure_storage_account_url: str | None = None
    fabric_kusto_query_uri: str | None = None
    fabric_kusto_database: str | None = None

    artifact_store: Literal["local", "blob"] = Field(
        default="local", validation_alias="TACTISTREAM_ARTIFACT_STORE"
    )
    analytics_publish: bool = Field(default=False, validation_alias="TACTISTREAM_ANALYTICS_PUBLISH")
    history: Literal["off", "memory", "eventhouse"] = Field(
        default="memory", validation_alias="TACTISTREAM_HISTORY"
    )
    history_timeout_ms: int = Field(default=1500, gt=0, validation_alias="TACTISTREAM_HISTORY_TIMEOUT_MS")
    environment: str = Field(default="dev", min_length=1, validation_alias="TACTISTREAM_ENVIRONMENT")

    @model_validator(mode="after")
    def _required_endpoints(self) -> Settings:
        if self.artifact_store == "blob" and not self.azure_storage_account_url:
            raise ValueError("AZURE_STORAGE_ACCOUNT_URL is required when TACTISTREAM_ARTIFACT_STORE=blob")
        if self.history == "eventhouse" and not self.fabric_kusto_query_uri:
            raise ValueError("FABRIC_KUSTO_QUERY_URI is required when TACTISTREAM_HISTORY=eventhouse")
        return self
