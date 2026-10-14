"""Environment-driven configuration; variable names match `.env.example`."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
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
    agents: Literal["off", "scripted", "foundry"] = Field(default="off", validation_alias="TACTISTREAM_AGENTS")
    narrative_deadline_ms: int = Field(default=8000, gt=0, validation_alias="TACTISTREAM_NARRATIVE_DEADLINE_MS")

    eventhubs_fully_qualified_namespace: str | None = None
    eventhubs_name: str = "tactistream-feed"
    eventhubs_consumer_group: str = "live-state"

    foundry_project_endpoint: str | None = None
    foundry_model_deployment: str | None = None

    applicationinsights_connection_string: str | None = None
    azure_storage_account_url: str | None = None
    fabric_kusto_query_uri: str | None = None
    fabric_kusto_database: str | None = None
