# Eventhouse Contract — KQL database `tactistream`

Source of truth for `infra/fabric/{tables,mappings,functions}.kql`. Static test `backend/tests/infra/test_kql_scripts.py`
asserts every table, column and function named here exists in the scripts with the same types.

## Ingestion path

```text
Event Hubs tactistream-feed ──(consumer group fabric)──► Eventstream tactistream-feed-es
    ──► Eventhouse table RawEnvelopes (mapping RawEnvelopesMapping, JSON)
          ├─ update policy kind == "event"       ──► Events
          ├─ update policy kind == "frame"       ──► Frames
          ├─ update policy kind == "insight"     ──► Insights
          ├─ update policy kind == "agent_trace" ──► AgentTraces
          └─ update policy kind == "latency"     ──► Latency
   kind == "metadata" stays in RawEnvelopes (function MatchMetadata(match_id))
```

## Tables

### `RawEnvelopes` (retention 14 d)

| Column | Type | JSON path |
|---|---|---|
| `SchemaVersion` | string | `$.schema_version` |
| `Kind` | string | `$.kind` |
| `MatchId` | string | `$.match_id` |
| `RecordId` | string | `$.record_id` |
| `PublishedMs` | long | `$.published_ms` |
| `Payload` | dynamic | `$.payload` |
| `EnqueuedAt` | datetime | `$.x-opt-enqueued-time` (Eventstream system property; null if absent) |

### `Events` (retention 365 d)

`MatchId:string, EventId:string, Sequence:long, Period:int, PeriodClockMs:long, SessionClockMs:long, EventType:string,
TeamId:string, PlayerId:string, RecipientId:string, StartX:real, StartY:real, EndX:real, EndY:real, DurationMs:long,
Outcome:string, RelatedEventIds:dynamic, SourceKind:string, GeneratorVersion:string, Seed:long, PublishedAt:datetime,
IngestedAt:datetime`

### `Frames` (retention 365 d)

`MatchId:string, FrameId:string, FrameIndex:long, Period:int, SessionClockMs:long, BallVisible:bool, BallX:real, BallY:real,
BallHeightM:real, Players:dynamic, VisiblePlayers:int, SourceKind:string, PublishedAt:datetime, IngestedAt:datetime`

### `Insights` (retention 365 d)

`MatchId:string, InsightId:string, InsightVersion:int, MomentId:string, StateVersion:long, AsOfSessionMs:long, Mode:string,
Language:string, SourceKind:string, ClaimStatus:string, Title:string, Body:string, Labels:dynamic, EvidenceIds:dynamic,
ClaimIds:dynamic, ShowFromMs:long, ShowUntilMs:long, ExpiresAtSessionMs:long, Annotations:dynamic, TraceId:string,
PublishedAt:datetime, IngestedAt:datetime`

### `AgentTraces` (retention 365 d)

`MatchId:string, TraceId:string, MomentId:string, Config:string, Outcome:string, FallbackReason:string, RepairUsed:bool,
ClaimsProposed:int, ClaimsApproved:int, ClaimsRevised:int, ClaimsRejected:int, ModelCalls:int, InputTokens:long,
OutputTokens:long, DurationMs:long, Steps:dynamic, PublishedAt:datetime, IngestedAt:datetime`

Claim counts are derived in the parse function from `Steps[].verdicts[].decision`.

### `Latency` (retention 365 d)

`MatchId:string, SampleId:string, Kind:string, ValueMs:long, Outcome:string, FallbackReason:string, TargetId:string,
ViewerId:string, TraceId:string, Config:string, RecordedAt:datetime, IngestedAt:datetime`

### `ReviewLabels` (retention 365 d; optional, loaded by 008)

`ReviewId:string, ItemId:string, RunId:string, Config:string, ClaimId:string, Reviewer:string, Label:string, LabeledAt:datetime`

`Label ∈ {supported, unsupported, unclear}`. Config labels are joined in after review (blinding key), never shown to reviewers.

## Views and functions

| Function | Signature | Returns |
|---|---|---|
| `ParseEvents()` … `ParseLatency()` | `()` | typed rows from `RawEnvelopes` filtered by `Kind` (used by update policies) |
| `EventsDeduped` | `()` | `Events | summarize arg_max(IngestedAt, *) by MatchId, EventId` |
| `Frames2Hz` | `()` | `Frames | where FrameIndex % 5 == 0` |
| `MatchMetadata` | `(match_id:string)` | latest metadata payload for the match |
| `MatchSummary` | `(match_id:string, as_of_ms:long)` | one row per `TeamId`: `PassesAttempted, PassesCompleted, Shots, Turnovers, EventCounts:dynamic (bag by EventType), LastEventIds:dynamic (≤10, newest first), AsOfMs` — **only events with `SessionClockMs <= as_of_ms`** |
| `PlayerHistory` | `(match_id:string, player_id:string, as_of_ms:long, max_items:int = 20)` | `EventId, Sequence, EventType, TeamId, PlayerId, SessionClockMs` where `PlayerId == player_id or RecipientId == player_id`, `SessionClockMs <= as_of_ms`, newest first |
| `LatencyP95` | `(kind:string, since:timespan)` | `Samples, P50, P95, Max, FallbackSamples, FallbackShare` over `Latency` with all outcomes included |
| `FallbackRate` | `(since:timespan)` | per `FallbackReason`: `Count`, `Share` of all `AgentTraces` in window; plus row `Total` |
| `ClaimSupportByConfig` | `()` | per `Config`: `Moments, Released, Fallback, Abstained, ClaimsProposed, ClaimsApproved, ClaimsRejected, VerifierApprovalRate, ReviewedClaims, Supported, Unsupported, Unclear, ReviewedSupportRate` (review columns from `ReviewLabels`, null if none) |

Parity rule: `MatchSummary` / `PlayerHistory` semantics are identical to `InMemoryHistoryStore`; a shared golden file
`backend/tests/fixtures/history_golden.json` defines events and expected outputs used by both the Python unit test and the optional
Kusto-emulator test.

Turnover definition (shared): `Turnovers` for team T counts `interception` and `ball_recovery` events with outcome `won` whose
`TeamId` is the other team (T lost the ball).
