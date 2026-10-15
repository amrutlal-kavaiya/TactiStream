# Data Model: 007 Azure Platform

## New contract model

### `LatencySample` (`backend/src/tactistream/contracts/latency.py`; schema `contracts/schemas/latency_sample.schema.json`, proposed)

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `"1.0"` | |
| `sample_id` | `str` | `lat-{kind}-{target_id}-{viewer_id}` or uuid4 hex for probes; dedupe key |
| `match_id` | `MatchId` | |
| `kind` | `"fast_overlay" \| "narrative"` | |
| `value_ms` | `int ≥ 0` | `ack_received_ms − server_receipt_ms` (fast) or `ack_received_ms − trigger_receipt_ms` (narrative); upper bound (001 R10) |
| `outcome` | `"released" \| "fallback" \| "abstained"` | fallback/abstained samples are always kept (constitution VI) |
| `fallback_reason` | `NarrativeStatus.fallback_reason \| None` | required when `outcome != released` for narrative |
| `target_id` | `str` | `event_id` or `insight_id:version` |
| `viewer_id` | `str` | per-WebSocket connection id (`v-` + 8 hex); lets 008 count viewers |
| `trace_id` | `TraceId \| None` | narrative only |
| `config` | `str` | `live` in the app; eval config id when produced by 008 runners |
| `recorded_ms` | `int` | server wall clock (epoch ms) |

Published as `FeedEnvelope(kind="latency", record_id=sample_id, payload=LatencySample)`.

### Envelope kinds published by `AnalyticsPublisher`

| kind | record_id | payload | Source |
|---|---|---|---|
| `insight` | `{insight_id}:{insight_version}:{mode}:{language}` | `InsightPacket` (one per variant) | released bundle (after output checks) |
| `agent_trace` | `trace_id` | `AgentTrace` (004) | workflow completion (released, fallback, abstained) |
| `latency` | `sample_id` | `LatencySample` | `LatencyRecorder.record` |

`AgentTrace` fields 007 relies on (must exist in 004's model): `trace_id`, `match_id`, `moment_id`, `config`, `outcome`,
`fallback_reason`, `steps[]` (agent, decision, claim_ids, verdicts, started_ms, duration_ms), `usage` (`model_calls`,
`input_tokens`, `output_tokens`), `repair_used`, `duration_ms`.

## Runtime types

```python
# history/base.py
@dataclass(frozen=True)
class EventRef:
    event_id: str                 # evt-NNNN, current match only
    sequence: int
    event_type: EventType
    team_id: TeamId
    player_id: PlayerId
    session_clock_ms: int

@dataclass(frozen=True)
class HistorySummary:
    match_id: str
    as_of_ms: int
    event_counts: Mapping[tuple[TeamId, EventType], int]
    passes_attempted: Mapping[TeamId, int]
    passes_completed: Mapping[TeamId, int]
    shots: Mapping[TeamId, int]
    turnovers: Mapping[TeamId, int]          # interception + ball_recovery won by the other team
    last_event_ids: tuple[str, ...]          # up to 10 most recent as of as_of_ms
    source: Literal["memory", "eventhouse"]

class HistoryUnavailable(Exception):
    reason: Literal["timeout", "error", "disabled"]

class HistoryStore(Protocol):
    async def match_summary(self, match_id: str, as_of_ms: int) -> HistorySummary: ...
    async def player_history(self, match_id: str, player_id: str, as_of_ms: int) -> list[EventRef]: ...

# history/tool.py
class GetHistoryArgs(BaseModel):            # the ONLY fields a model may supply
    query: Literal["match_summary", "player_history"]
    player_id: PlayerId | None = None

class HistoryToolResult(BaseModel):
    status: Literal["ok", "unavailable"]
    reason: Literal["timeout", "error", "disabled"] | None = None
    as_of_ms: int
    summary: HistorySummaryModel | None = None
    events: list[EventRefModel] = []
    dropped_unresolvable: int = 0
    duration_ms: int

# transport/analytics_publisher.py
class AnalyticsPublisher:
    def __init__(self, bus: FeedBus, *, enabled: bool, clock: Clock, max_queue: int = 1000) -> None: ...
    def offer_insight(self, bundle: InsightBundle) -> None: ...
    def offer_agent_trace(self, trace: AgentTrace) -> None: ...
    def offer_latency(self, sample: LatencySample) -> None: ...
    async def run(self) -> None: ...          # drain task started by create_app lifespan
    async def aclose(self) -> None: ...
    dropped: Counter[str]                     # by kind

# telemetry/instruments.py
class Instruments:
    def record_latency(self, sample: LatencySample) -> None: ...
    def record_fallback(self, reason: FallbackReason, *, match_id: str, config: str = "live") -> None: ...
    def record_model_call(self, agent: AgentRole, model: str, input_tokens: int, output_tokens: int, duration_ms: int) -> None: ...
    def record_history_query(self, duration_ms: int, status: Literal["ok", "timeout", "error"]) -> None: ...
    def record_analytics_drop(self, kind: str) -> None: ...
    def record_checkpoint_failure(self) -> None: ...
def get_instruments() -> Instruments: ...

# telemetry/correlation.py
@contextmanager
def workflow_span(match_id: str, moment_id: str, *, config: str = "live") -> Iterator[str]: ...   # yields trace_id
def current_trace_id() -> str | None: ...
```

## ArtifactStore key routing (`storage/blob.py`)

| Key prefix | Container | Writers |
|---|---|---|
| `checkpoints/{match_id}/{state_version:08d}.json` | `checkpoints` | 003 `state/checkpoint.py` |
| `datasets/{split}/{scenario}-{seed}-{variant}.jsonl` | `datasets` | 002 dataset export, 008 frozen inputs mirror |
| `feed-archive/{match_id}/{session_id}.jsonl` | `artifacts` | 003 feed archive |
| `recaps/{match_id}/{recap_id}.json` · `exports/…` | `artifacts` | 006 recap, 009 optional MP4 |
| `eval/{run_id}/…` | `artifacts` | 008 evaluation runs (optional mirror) |

Blob name = key without the routed first segment for `checkpoints/` and `datasets/`, full key otherwise. Content type from
extension (`.json`, `.jsonl` → `application/json`; `.mp4` → `video/mp4`).

## Runtime configuration (Container App environment, names added to `.env.example`)

| Variable | Deployed value | Local default |
|---|---|---|
| `TACTISTREAM_BUS` | `eventhubs` | `memory` |
| `TACTISTREAM_AGENTS` | `foundry` | `off` |
| `EVENTHUBS_FULLY_QUALIFIED_NAMESPACE` | `<ns>.servicebus.windows.net` | — |
| `EVENTHUBS_NAME` / `EVENTHUBS_CONSUMER_GROUP` | `tactistream-feed` / `live-state` | same |
| `FOUNDRY_PROJECT_ENDPOINT` / `FOUNDRY_MODEL_DEPLOYMENT` | from params | — |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | container app secret ref | unset |
| `AZURE_CLIENT_ID` | managed identity client id | unset |
| `AZURE_STORAGE_ACCOUNT_URL` | `https://<acct>.blob.core.windows.net` | — |
| `TACTISTREAM_ARTIFACT_STORE` | `blob` | `local` |
| `TACTISTREAM_ANALYTICS_PUBLISH` | `on` | `off` |
| `TACTISTREAM_HISTORY` | `eventhouse` (after US3) else `memory` | `memory` |
| `TACTISTREAM_HISTORY_TIMEOUT_MS` | `1500` | `1500` |
| `FABRIC_KUSTO_QUERY_URI` / `FABRIC_KUSTO_DATABASE` | from SETUP.md / `tactistream` | — |
| `TACTISTREAM_STATIC_DIR` / `TACTISTREAM_CONTRACTS_DIR` | `/app/frontend/dist` / `/app/contracts/schemas` | repo paths |
| `TACTISTREAM_ENVIRONMENT` | `production` | `dev` |

`Settings` gains: `artifact_store: Literal["local","blob"]`, `analytics_publish: bool`, `history: Literal["off","memory","eventhouse"]`,
`history_timeout_ms: int = 1500`, `azure_storage_account_url`, `fabric_kusto_query_uri`, `fabric_kusto_database`, `static_dir`,
`environment`.

## State transitions

```text
Analytics envelope:  offered --queue has room--> queued --publish ok--> sent
                     offered --queue full------> dropped (counted)
                     queued  --publish error---> dropped (counted, logged once per minute)

History tool call:   requested --store ok ≤1.5 s--> ok (IDs filtered by evidence index as-of)
                     requested --timeout---------> unavailable(timeout)
                     requested --exception-------> unavailable(error)
                     requested --history=off-----> unavailable(disabled)

Deploy revision:     image pushed --update--> provisioning --probes pass--> active (old revision deactivated)
                                                  └--probes fail--> failed (old revision stays active; workflow fails)
```
