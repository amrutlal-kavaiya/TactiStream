"""Environment-driven configuration; variable names match `.env.example`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from tactistream.agents.context import AgentBudgets

_REPO_ROOT = Path(__file__).parents[3]
PRESENTER_KEY_MIN_LENGTH = 16


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
    max_sessions: int = Field(default=8, gt=0, validation_alias="TACTISTREAM_MAX_SESSIONS")
    data_dir: Path = Field(default=_REPO_ROOT / "data", validation_alias="TACTISTREAM_DATA_DIR")
    static_dir: Path | None = Field(
        default=_REPO_ROOT / "frontend" / "dist", validation_alias="TACTISTREAM_STATIC_DIR"
    )

    eventhubs_fully_qualified_namespace: str | None = None
    eventhubs_name: str = "tactistream-feed"
    eventhubs_consumer_group: str = "live-state"

    foundry_project_endpoint: str | None = None
    foundry_model_deployment: str | None = None
    azure_location: str | None = None

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
    presenter_key: SecretStr | None = Field(default=None, validation_alias="TACTISTREAM_PRESENTER_KEY")

    demo_fixtures: bool = Field(default=False, validation_alias="TACTISTREAM_DEMO_FIXTURES")
    trace_dir: Path | None = Field(default=None, validation_alias="TACTISTREAM_TRACE_DIR")
    agent_scripts: Path = Field(
        default=_REPO_ROOT / "data/fixtures/agent_scripts/demo-blue-amber-001.json",
        validation_alias="TACTISTREAM_AGENT_SCRIPTS",
    )
    analyst_timeout_ms: int = Field(default=3500, ge=800, validation_alias="TACTISTREAM_ANALYST_TIMEOUT_MS")
    verifier_timeout_ms: int = Field(default=2500, ge=600, validation_alias="TACTISTREAM_VERIFIER_TIMEOUT_MS")
    producer_timeout_ms: int = Field(default=1500, ge=600, validation_alias="TACTISTREAM_PRODUCER_TIMEOUT_MS")
    release_reserve_ms: int = Field(default=400, ge=0, validation_alias="TACTISTREAM_RELEASE_RESERVE_MS")
    repair_min_remaining_ms: int = Field(
        default=3000, ge=0, validation_alias="TACTISTREAM_REPAIR_MIN_REMAINING_MS"
    )
    min_tracking_coverage: float = Field(
        default=0.8, ge=0, le=1, validation_alias="TACTISTREAM_MIN_TRACKING_COVERAGE"
    )
    narrative_min_rank: float = Field(
        default=0.4, ge=0, le=1, validation_alias="TACTISTREAM_NARRATIVE_MIN_RANK"
    )
    narrative_max_concurrency: int = Field(
        default=2, gt=0, validation_alias="TACTISTREAM_NARRATIVE_MAX_CONCURRENCY"
    )
    foundry_model_deployment_fast: str | None = None

    @field_validator("trace_dir", "agent_scripts", mode="after")
    @classmethod
    def _repo_relative(cls, value: Path | None) -> Path | None:
        if value is None or value.is_absolute():
            return value
        return _REPO_ROOT / value

    @field_validator("presenter_key", mode="before")
    @classmethod
    def _presenter_key_strength(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if len(value) < PRESENTER_KEY_MIN_LENGTH:
                raise ValueError(
                    f"TACTISTREAM_PRESENTER_KEY must be at least {PRESENTER_KEY_MIN_LENGTH} characters "
                    "(leave it empty to disable presenter mode)"
                )
        return value

    @model_validator(mode="after")
    def _required_endpoints(self) -> Settings:
        if self.artifact_store == "blob" and not self.azure_storage_account_url:
            raise ValueError("AZURE_STORAGE_ACCOUNT_URL is required when TACTISTREAM_ARTIFACT_STORE=blob")
        if self.history == "eventhouse" and not self.fabric_kusto_query_uri:
            raise ValueError("FABRIC_KUSTO_QUERY_URI is required when TACTISTREAM_HISTORY=eventhouse")
        if self.agents == "scripted" and not self.agent_scripts.is_file():
            raise ValueError(
                f"TACTISTREAM_AGENT_SCRIPTS must name an existing file when TACTISTREAM_AGENTS=scripted "
                f"({self.agent_scripts})"
            )
        return self

    def agent_budgets(self) -> AgentBudgets:
        from tactistream.agents.context import MIN_STEP_MS, AgentBudgets

        return AgentBudgets(
            caps_ms={
                "analyst": self.analyst_timeout_ms,
                "verifier": self.verifier_timeout_ms,
                "producer": self.producer_timeout_ms,
                "single_agent": self.analyst_timeout_ms,
            },
            min_ms=dict(MIN_STEP_MS),
            reserve_ms=self.release_reserve_ms,
            repair_min_remaining_ms=self.repair_min_remaining_ms,
            deadline_ms=self.narrative_deadline_ms,
        )
