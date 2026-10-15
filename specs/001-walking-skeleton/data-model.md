# Data Model: 001 Walking Skeleton

Canonical shapes live in `/contracts/schemas`. This file lists the Python/TS types introduced in this feature,
their invariants, and the state transitions the skeleton needs.

## Contract models (`backend/src/tactistream/contracts/`)

| Module | Types | Schema |
|---|---|---|
| `common.py` | `SourceKind`, `Provenance`, `PointM = tuple[float, float]`, `TeamId`, `ViewerMode`, `Language`, `MetricKind`, `MomentPattern`, `ClaimStatus`, ID `Annotated[str, StringConstraints(pattern=...)]` aliases | `common.schema.json` |
| `match.py` | `MatchMetadata`, `Team`, `Player`, `PitchSpec`, `PeriodSpec` | `match_metadata.schema.json` |
| `event.py` | `MatchEvent`, `EventType`, `Outcome` | `event.schema.json` |
| `tracking.py` | `TrackingFrame`, `PlayerPosition`, `BallPosition` | `tracking_frame.schema.json` |
| `metric.py` | `MetricResult`, `MetricWindow`, `MetricInputs` | `metric_result.schema.json` |
| `moment.py` | `CandidateMoment` | `candidate_moment.schema.json` |
| `claim.py` | `SlotValue`, `Claim`, `AnalystOutput`, `Verdict`, `VerifierOutput`, `ModePlan`, `ProducerOutput` | `claim.schema.json` |
| `insight.py` | `InsightPacket`, `RenderSpec`, `InsightBundle` | `insight_packet.schema.json`, `ws_message.schema.json#/$defs/InsightBundle` |
| `recap.py` | `Recap`, `RecapItem`, `OverlayCue` | `recap.schema.json` |
| `envelope.py` | `FeedEnvelope` (discriminated on `kind` → typed payload) | `feed_envelope.schema.json` |
| `ws.py` | `ServerMessage`, `Snapshot`, `NarrativeStatus`, `InsightRevoked`, `ClientMessage` (`ResumeMsg`, `PrefsMsg`, `DisplayAckMsg`) | `ws_message.schema.json` |

All models: `model_config = ConfigDict(extra="forbid", frozen=True)`. Serialization: `model_dump(mode="json", exclude_none=True)`.

## Validation rules (enforced by schema and model validators)

- Visible tracked entity ⇔ `pos_m` present. Invisible entities have no position (never fabricated).
- Pass events require `end_m` and `duration_ms`; completed passes require `recipient_id`.
- `MetricResult.status == "ok"` ⇔ `value` and `unit` present; `unavailable` ⇔ `unavailable_reason` present and no `value`.
- `InsightPacket.render.show_until_ms > show_from_ms`; `expires_at_session_ms >= show_until_ms` (model validator).
- Every `InsightPacket.evidence_ids` entry resolves in the session evidence index before release (runtime check, `agents/checks.py`).

## Runtime (non-contract) types introduced

```python
# transport/bus.py
class FeedBus(Protocol):
    async def publish(self, envelope: FeedEnvelope) -> None: ...
    def subscribe(self, consumer_group: str) -> AsyncIterator[FeedEnvelope]: ...

# transport/replayer.py
class PlaybackState(StrEnum): PLAYING = "playing"; PAUSED = "paused"; ENDED = "ended"
@dataclass
class FeedReplayer:
    records: Sequence[FeedEnvelope]          # sorted by session_clock_ms, metadata first
    bus: FeedBus
    clock: Clock                              # injectable; FakeClock in tests
    speed: float = 1.0
    async def play(self) -> None: ...
    def pause(self) -> None: ...
    async def reset(self) -> None: ...
    @property
    def session_clock_ms(self) -> int: ...

# state/match_state.py (skeleton subset; 003 extends)
@dataclass
class StateDelta:
    state_version: int
    new_events: list[MatchEvent]
    new_frame: TrackingFrame | None
    duplicate: bool

class MatchState:
    metadata: MatchMetadata | None
    events: list[MatchEvent]                  # ordered by sequence
    latest_frame: TrackingFrame | None
    state_version: int
    def apply(self, envelope: FeedEnvelope) -> StateDelta: ...

# api/session.py
class MatchSession:
    match_id: str
    replayer: FeedReplayer
    state: MatchState
    hub: WsHub                                # fan-out with per-match seq log
    evidence: EvidenceIndex                   # id -> event | frame | metric
```

## State transitions

```text
Playback:   paused --play--> playing --pause--> paused
            playing --(last record)--> ended
            any --reset--> paused (session_clock_ms = 0, state cleared, seq continues monotonically, snapshot pushed)

Card:       pass event applied --> metric computed --> packet variants rendered --> check_packet
            check ok   --> insight released (WS "insight")
            check fail --> narrative_status{stage: fallback, fallback_reason: output_check_failed}
```

## Fixture

`data/fixtures/skeleton.jsonl` — one `FeedEnvelope` JSON per line: 1 metadata, 60 frames (0–5.9 s), 4 events with
contiguous sequences: `evt-0040 kickoff` (blue-10, t=0 ms), `evt-0041 carry` (blue-08, [52.0,33.0] → [58.1,32.4], t=1500 ms),
`evt-0042 pass complete` (blue-08 → blue-11, [58.1,32.4] → [71.2,28.0], duration 900 ms, t=3000 ms),
`evt-0043 carry` (blue-11, [71.2,28.0] → [75.0,27.0], t=3900 ms). Session clock starts at 0; `period_clock_ms` offsets are illustrative.
Expected `forward_progress` = 71.2 − 58.1 = **13.1 m** (Blue attacks +x).
