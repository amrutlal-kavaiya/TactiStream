# Data Model: 003 Live State & Metrics

Contract shapes (`MetricResult`, `CandidateMoment`, `Snapshot`, `InsightRevoked`) are unchanged except the proposed
per-player MetricId extension (see "Metric IDs"). Below are runtime types, rules and formulas.

## Ingest (`state/ingest.py`)

```python
IngestStatus = Literal["applied", "duplicate", "invalid", "held", "late_frame", "revision", "ignored"]

@dataclass(frozen=True, slots=True)
class IngestResult:
    envelope: FeedEnvelope            # with server_receipt_ms stamped
    status: IngestStatus
    delta: StateDelta | None          # None for duplicate/invalid/held/ignored
    gap: tuple[int, int] | None = None

@dataclass(slots=True)
class IngestStats:
    received: int = 0; applied: int = 0; duplicates: int = 0; payload_conflicts: int = 0; invalid: int = 0
    gaps: int = 0; revisions: int = 0; late_frames: int = 0; ignored: int = 0; held_max: int = 0

class Ingestor:
    def __init__(self, state: MatchState, clock: Clock, *, wall_ms: Callable[[], int] = epoch_ms,
                 reorder_window_ms: int = 500, archive: FeedArchive | None = None, max_buffer: int = 10_000) -> None: ...
    def accept(self, envelope: FeedEnvelope) -> list[IngestResult]: ...   # 0..n results (buffered releases included)
    def tick(self) -> list[IngestResult]: ...                              # release events held ≥ window; flag gaps
    def flush(self) -> list[IngestResult]: ...                             # release everything in order (end of feed, tests)
    @property
    def expected_next_seq(self) -> int | None: ...
    stats: IngestStats
```

Rules, in order, for each received envelope:

1. Stamp `server_receipt_ms = wall_ms()` if absent; buffer the raw envelope into `archive` (if set).
2. `kind ∈ {insight, agent_trace, latency}` → `ignored`.
3. `schema_registry.validate("feed_envelope", …)` fails → `invalid`.
4. (`kind`, `record_id`) already seen (applied or buffered) → `duplicate` (`payload_conflicts` +1 if the payload differs).
5. No metadata applied yet and kind ≠ `metadata` → `held` (no timer).
6. `metadata` → apply; then release anything held for metadata.
7. `frame` → apply (`late_frame` if `frame_index` < highest applied index, else `applied`).
8. `event`:
   - `expected_next_seq is None`: release now if `sequence ∈ {0, 1}`; else hold (timer starts).
   - `sequence == expected_next_seq` → apply, then release consecutive held sequences.
   - `sequence > expected_next_seq` → hold (timer starts at receipt on `clock.now_ms()`).
   - `sequence < expected_next_seq` (not a duplicate) → apply as `revision`.
9. `tick()`: if the oldest held event has waited ≥ `reorder_window_ms`, release all held events in ascending sequence;
   the first released carries `gap = (expected_next_seq, lowest_held − 1)` when `expected_next_seq` is known.

## Match state (`state/match_state.py`, extends 001)

```python
@dataclass(frozen=True, slots=True)
class Revision:
    record_id: str
    kind: Literal["event", "frame"]
    session_clock_ms: int

@dataclass
class StateDelta:                                  # 001 fields unchanged; new fields default to "no change"
    state_version: int
    new_events: list[MatchEvent]
    new_frame: TrackingFrame | None
    duplicate: bool
    revision: Revision | None = None
    late_frame: bool = False

class MatchState:                                  # 001 attributes unchanged
    def apply(self, envelope: FeedEnvelope) -> StateDelta: ...
    def snapshot(self, as_of_ms: int | None = None) -> MatchSnapshot: ...   # None → latest session clock seen
    @property
    def session_clock_ms(self) -> int: ...         # max session_clock_ms applied
    @property
    def max_frame_index(self) -> int: ...
    def record_keys(self) -> frozenset[tuple[str, str]]: ...
    def to_checkpoint(self) -> dict[str, object]: ...
    @classmethod
    def from_checkpoint(cls, data: Mapping[str, object]) -> "MatchState": ...

def full_state_hash(state: MatchState) -> str: ...   # sha256 of canonical JSON: metadata + all events + all frames (001 state_hash unchanged)
```

`state_version` increments by 1 per accepted record (metadata, event, frame, revision, late frame) — so for identical
inputs the final value is identical regardless of order.

## Snapshot (`state/snapshot.py`)

```python
@dataclass(frozen=True, slots=True)
class MatchSnapshot:
    match_id: str
    metadata: MatchMetadata
    as_of_ms: int
    state_version: int
    events: tuple[MatchEvent, ...]                 # session_clock_ms ≤ as_of_ms, ascending sequence
    frames: tuple[TrackingFrame, ...]              # session_clock_ms ≤ as_of_ms, ascending frame_index
    def event(self, event_id: str) -> MatchEvent: ...                          # KeyError if absent
    def events_between(self, start_ms: int, end_ms: int) -> tuple[MatchEvent, ...]: ...   # inclusive
    def frames_between(self, start_ms: int, end_ms: int) -> tuple[TrackingFrame, ...]: ...
    def frame_at(self, t_ms: int, tolerance_ms: int = 50) -> TrackingFrame | None: ...
    def position(self, player_id: str, t_ms: int) -> tuple[float, float] | None: ...       # None if frame missing or invisible
    def attack_direction(self, team_id: TeamId, period: int) -> Literal[1, -1]: ...
    def possessing_team_at(self, t_ms: int) -> TeamId | None: ...
```

`MatchState` caches the frozen tuples per `state_version`; `snapshot(as_of)` slices them with `bisect` (O(log n)).

## Checkpoints and archive (`state/checkpoint.py`, `storage/`)

```python
# storage/base.py
class ArtifactNotFound(KeyError): ...
class ArtifactStore(Protocol):
    async def put(self, key: str, data: bytes, *, content_type: str = "application/json") -> None: ...
    async def get(self, key: str) -> bytes: ...                 # raises ArtifactNotFound
    async def exists(self, key: str) -> bool: ...
    async def list(self, prefix: str) -> list[str]: ...         # sorted keys
    async def append(self, key: str, data: bytes) -> None: ...  # creates if missing
    async def delete(self, key: str) -> None: ...               # no error if missing

# storage/local.py
class LocalArtifactStore(ArtifactStore):
    def __init__(self, root: Path) -> None: ...                 # keys: [a-z0-9._/-]+, no "..", no leading "/"; atomic put via tmp + os.replace

# state/checkpoint.py
CHECKPOINT_FORMAT = "tactistream.checkpoint.v1"
def checkpoint_key(match_id: str, state_version: int) -> str: ...   # f"checkpoints/{match_id}/{state_version:08d}.json"
def archive_key(match_id: str, session_id: str) -> str: ...         # f"feed-archive/{match_id}/{session_id}.jsonl"

class FeedArchive:
    def __init__(self, store: ArtifactStore, match_id: str, session_id: str) -> None: ...
    def buffer(self, envelope: FeedEnvelope) -> None: ...      # sync, called by Ingestor
    async def flush(self) -> int: ...                           # appends buffered lines; returns lines_written total
    lines_written: int

class Checkpointer:
    def __init__(self, store: ArtifactStore, clock: Clock, *, every_records: int = 100, every_ms: int = 10_000, keep: int = 3) -> None: ...
    def note_applied(self, n: int = 1) -> None: ...
    def due(self) -> bool: ...
    async def write(self, session: CheckpointSource) -> str | None: ...   # flushes archive first; never raises (logs, counts failures)

@dataclass(frozen=True)
class RestoredMatch:
    state: MatchState; ingestor: Ingestor; archive: FeedArchive; session_id: str
    session_config: Mapping[str, object]; session_clock_ms: int; ws_head_seq: int
async def restore(store: ArtifactStore, match_id: str, clock: Clock) -> RestoredMatch | None: ...
async def clear(store: ArtifactStore, match_id: str) -> None: ...            # reset / backward seek
```

Checkpoint JSON (canonical, one object):

| Field | Type | Notes |
|---|---|---|
| `format` | `"tactistream.checkpoint.v1"` | |
| `match_id`, `session_id` | str | |
| `session_config` | `{"scenario", "seed", "variant"}` | to rebuild the replayer on restore |
| `state_version`, `session_clock_ms` | int | |
| `ws_head_seq` | int | restored hub starts at `ws_head_seq + 10000` |
| `metadata` | `MatchMetadata` | |
| `events`, `frames` | arrays of contract records (with `server_receipt_ms` kept in a parallel `receipts` map) | |
| `ingest` | `{"expected_next_seq": int \| null, "max_frame_index": int}` | |
| `archive_lines` | int | archive lines covered by this checkpoint |

Trigger: `note_applied` per accepted record; `due()` when ≥ `every_records` since the last write or ≥ `every_ms` on the
monotonic clock (and ≥ 1 record since). Writes run as a background task on an immutable `to_checkpoint()` copy.

## Metric engine (`metrics/registry.py`)

```python
@dataclass(frozen=True)
class MetricParams:
    pass_window_ms: int = 300_000; rhythm_window_ms: int = 300_000; rhythm_min_ms: int = 60_000
    pressure_scale_m: float = 2.5; pressure_k: int = 3; min_visible_opponents: int = 10
    lookback_ms: int = 4_000
    run_search_ms: int = 6_000; run_max_span_ms: int = 4_000; run_min_disp_m: float = 8.0
    run_min_speed_mps: float = 4.0; run_angle_min_deg: float = 20.0; run_angle_max_deg: float = 70.0
    run_max_invisible_share: float = 0.2; follow_min_disp_m: float = 1.0; frame_tolerance_ms: int = 50

@dataclass(frozen=True)
class MetricDefinition:
    kind: MetricKind; definition_version: str; unit: str; params: Mapping[str, float]; limitation_key: str; formula: str

class AnchorNotFound(KeyError): ...

class MetricEngine:
    def __init__(self, params: MetricParams = MetricParams(), cache_size: int = 4096) -> None: ...
    def compute(self, kind: MetricKind, snapshot: MatchSnapshot, anchor_event_id: str, *,
                subject_id: str | None = None, moments: Sequence[CandidateMoment] = ()) -> MetricResult: ...
    def compute_by_id(self, metric_id: str, snapshot: MatchSnapshot, *, moments: Sequence[CandidateMoment] = ()) -> MetricResult: ...
    @staticmethod
    def metric_id(kind: MetricKind, anchor_sequence: int, subject_id: str | None = None) -> str: ...
    def definitions(self) -> list[MetricDefinition]: ...
```

Each metric module exposes one pure function `compute_<kind>(snapshot, anchor, params, …) -> MetricResult`. Cache key:
`(kind, anchor_event_id, subject_id, snapshot.as_of_ms, snapshot.state_version, tuple(m.moment_id for m in moments))`.

### Metric IDs

`metric-{kind}-{anchor_sequence:04d}` for all kinds; `contribution` uses `metric-contribution-{anchor_sequence:04d}-{player_id}`
(e.g. `metric-contribution-0045-blue-09`). This requires the proposed `common.schema.json` `MetricId` pattern
`^metric-[a-z_]+-[0-9]{4,}(-(blue|amber)-[0-9]{2})?$`.

### Definitions (all `definition_version = "{kind}.v1"`, `limitation_key = "limitation.{kind}"`)

`t` = anchor `session_clock_ms`; "visible opponents" = visible players of the team not in possession at `t`; positions from
`frame_at(t, 50)`. All distances are measured in stadium coordinates; directions use `geometry.normalize` with the anchor team's
attack direction for the anchor's period.

| Kind | Anchor | Value (unit, rounding) | Components | Window / inputs | Unavailable |
|---|---|---|---|---|---|
| `pass_completion` | any event (team = anchor team) | completed ÷ attempted (`ratio`, 3 dp) | `completed`, `attempted` | `[t−300000, t]`; `event_ids` = counted passes; `excluded_count` = passes with `outcome=null` | `missing_events` if attempted = 0 |
| `forward_progress` | pass | 001 definition (`m`, 1 dp) | — | 001 | `not_applicable` if not a pass |
| `rhythm` | any event (team = anchor team) | completed passes per min (`per_min`, 2 dp) | `completed_passes_per_min`, `turnovers_per_min`, `completed_passes`, `turnovers`, `window_min` | `[t−W, t]`, `W = min(300000, t − first event time)`; `event_ids` = passes + turnovers | `not_applicable` if `W < 60000` |
| `pressure` | pass, carry or shot (carrier = actor) | `(100/3)·Σ_{i≤3} exp(−d_i/2.5)` (`score_0_100`, 1 dp) | `d1_m`, `d2_m`, `d3_m` | `[t, t]`; `frame_ids` = [frame at t]; `subject_ids` = [carrier, def1, def2, def3] | `insufficient_tracking` if carrier invisible, frame missing, or visible opponents < 10; `not_applicable` for other event types |
| `channel` | pass with `recipient_id` | `clearance_at_pass_m − clearance_before_m` of the rounded components (`m`, 1 dp) | `clearance_before_m`, `clearance_at_pass_m` (0.1 m) | `[t−4000, t]`; `frame_ids` = [before, at_pass]; `subject_ids` = [passer, receiver] | `insufficient_tracking` if passer/receiver invisible, a frame missing, or < 10 visible opponents at either time; `not_applicable` if no recipient |
| `receiver_separation` | pass with `recipient_id` | `separation_at_pass_m − separation_before_m` (`m`, 1 dp) | `separation_before_m`, `separation_at_pass_m`, `separation_at_reception_m` (if reception frame in snapshot) | `[t−4000, t]` (+ reception frame id when present); `subject_ids` = [receiver, nearest defender at pass] | as `channel` (receiver only) |
| `off_ball_run` | pass | best qualifying displacement (`m`, 1 dp) | `duration_ms`, `mean_speed_mps` (2 dp), `angle_deg` (1 dp) | run `[s, e]`; `frame_ids` = [frame s, frame e]; `subject_ids` = [runner]; `event_ids` = [anchor] | `insufficient_tracking` if any candidate invisible in > 20% of `[t−6000, t]` frames; `not_applicable` if none qualifies |
| `defender_follow` | pass (uses `off_ball_run` for the same anchor) | cosine(defender Δ, runner Δ) over `[s, e]` (`cosine`, 2 dp); 0.0 if defender Δ < 1.0 m | `defender_displacement_m`, `runner_displacement_m` | `[s, e]`; `frame_ids` = [s, e]; `subject_ids` = [defender, runner] | inherits `off_ball_run` reason; `insufficient_tracking` if defender invisible at s/e or < 10 visible opponents at s |
| `contribution` | any event + `subject_id` + `moments` | `direct_events + off_ball_involvements` (`count`) | `direct_events`, `off_ball_involvements`, `moments_considered` | union of moment windows; `event_ids` = direct events; `frame_ids` = frames of counted `off_ball_run` results | `missing_events` if `moments` is empty |

Off-ball-run search: candidates = anchor team's outfield players except passer and receiver; for each, every start frame
`s` in `[t−6000, t]` and end `e ≤ min(s+4000, t)` with the player visible in all frames of `[s, e]`; qualifying =
displacement ≥ 8.0, displacement/duration ≥ 4.0 m/s, folded angle (0–180°, normalized) in [20, 70]. Choose the largest
displacement (compared after rounding to 0.1 m); ties → shorter duration, then earlier `s`, then lower `player_id`.

Limitation texts (EN; HI drafted, reviewed in 006):

| Key | Text |
|---|---|
| `limitation.pass_completion` | Passes with a missing outcome are excluded and counted separately. |
| `limitation.forward_progress` | Distance gained toward goal; it does not measure chance quality. |
| `limitation.rhythm` | Activity rates shown separately; not a validated momentum measure. |
| `limitation.pressure` | Distance heuristic from the three nearest opponents; not an official performance metric. |
| `limitation.channel` | Shows how the passing lane changed; supports interpretation, does not prove intent. |
| `limitation.receiver_separation` | Distance to the nearest opponent; supports interpretation, does not prove intent. |
| `limitation.defender_follow` | Movement similarity between two players; correlation, not proof the defender was drawn by the run. |
| `limitation.off_ball_run` | Detected from tracked displacement and speed thresholds; does not judge the run's purpose. |
| `limitation.contribution` | Direct actions plus evidence-supported off-ball involvement in selected moments; not an official assist or player rating. |

## Moment detection (`moments/detector.py`)

```python
@dataclass(frozen=True)
class DetectionParams:
    press_threshold: float = 35.0; press_lookback_ms: int = 3_000
    switch_min_dy_m: float = 30.0; switch_min_separation_m: float = 5.0
    channel_min_gain_m: float = 2.0
    window_min_ms: int = 8_000; window_max_ms: int = 12_000; window_tail_ms: int = 500
    settle_margin_ms: int = 200; space_pass_settle_ms: int = 12_000
    min_visible_per_team: int = 10

def detect_moments(snapshot: MatchSnapshot, metrics: MetricEngine, params: DetectionParams = DetectionParams()) -> list[CandidateMoment]: ...
def sequence_start_ms(snapshot: MatchSnapshot, trigger: MatchEvent) -> int: ...
def moment_window(snapshot: MatchSnapshot, trigger: MatchEvent, params: DetectionParams) -> tuple[int, int]: ...
def tracking_coverage(snapshot: MatchSnapshot, window: tuple[int, int], involved: Sequence[str], params: DetectionParams) -> float: ...
```

Definitions:

- **Turnover**: `interception`, `tackle` with `won`, or `ball_recovery` by the team that did not last possess.
- **Sequence start**: time of the latest event before the trigger that is a `kickoff`, the first event after an
  `out_of_play`, or a turnover (trigger excluded).
- **Window**: `start = clamp(sequence_start, t − 12000, t − 8000)` (floored at 0); `end = t + duration_ms + 500`.
- **Settled**: a trigger is evaluated only when the snapshot has a frame with `session_clock_ms ≥ t + duration_ms + 200`.
- **Coverage**: share of expected frames in `[start, end]` (100 ms grid) in which every involved player is visible and
  each team has ≥ 10 visible players; missing frames count as uncovered. Rounded to 3 dp.
- **Qualifying space pass** P (team T): completed pass with positive `forward_progress`, `off_ball_run(P)` ok,
  `channel(P)` ok with value ≥ 2.0.

Triggers, evaluated in ascending trigger sequence:

| Pattern | Trigger | Condition | `moment_id` | Involved players (order) | `metric_ids` (order) |
|---|---|---|---|---|---|
| `space_creation` (via shot) | `shot` by T | window contains a qualifying space pass P by T (latest one if several) | `mom-{shot seq}` | passer(P), receiver(P), runner, defender (from `defender_follow` if ok), shooter | off_ball_run(P), defender_follow(P), channel(P), receiver_separation(P), forward_progress(P), pressure(P) |
| `space_creation` (no shot) | qualifying space pass P | no shot by T within 12 s after P and settled at `t_P + 12000` or at the next possession change, whichever first | `mom-{P seq}` | passer, receiver, runner, defender | as above |
| `press_turnover` | turnover by team W | the losing team's last on-ball event V (pass/carry/shot) is ≤ 3000 ms before the trigger and `pressure(V) ≥ 35.0` | `mom-{turnover seq}` | victim(V), pressure `subject_ids[1:]`, turnover actor | pressure(V) |
| `switch_escape` | completed pass P | |Δy| ≥ 30 m and `receiver_separation(P).separation_at_reception_m ≥ 5.0` | `mom-{P seq}` | passer, receiver, `receiver_separation` subject 2 | receiver_separation(P), forward_progress(P), pressure(P) |
| `shot` | `shot` by T | not space_creation, and the window contains no trigger of another moment whose focus team is T (focus = runner's team / turnover winner / switching team) | `mom-{shot seq}` | shooter, passer + receiver of T's last completed pass in the window | pressure(shot) + off_ball_run, defender_follow, channel of T's last completed forward pass in the window (if any) |

`generic` is reserved and never produced in 003. `rank_score` is set by `ranking.score(moment, metrics, pinned=None)`.
One moment per `moment_id`: a pass that qualifies as `switch_escape` is not also used for the no-shot `space_creation`
path. A space pass used by a shot-triggered `space_creation` moment does not create a second moment.

## Ranking (`moments/ranking.py`)

```python
BASE = {"space_creation": 0.60, "press_turnover": 0.55, "switch_escape": 0.50, "shot": 0.40, "generic": 0.20}
PINNED_BONUS = 0.30
def strength(moment: CandidateMoment, metrics: Mapping[str, MetricResult], trigger: MatchEvent) -> float: ...
def score(moment: CandidateMoment, metrics: Mapping[str, MetricResult], trigger: MatchEvent, pinned_player_id: str | None = None) -> float: ...
def rank(moments: Sequence[CandidateMoment], pinned_player_id: str | None = None) -> list[CandidateMoment]: ...
```

`strength`: space_creation `min(1, channel/5.0)`; press_turnover `min(1, pressure/70)`; switch_escape
`min(1, separation_at_reception_m/12)`; shot `0.5` on_target / `0.3` off_target / `0.2` blocked / `0.6` goal; generic 0.
`score = round(BASE + 0.25·strength + 0.15·coverage + (PINNED_BONUS if pinned in involved_player_ids else 0), 4)`.
`rank` re-scores with the pin (bonus applied on top of the stored unpinned `rank_score`) and sorts by
`(−score, window.end_ms, moment_id)`; it returns copies with `rank_score` replaced. Example: hero with channel 3.6 m,
coverage 1.0 → `0.60 + 0.18 + 0.15 = 0.93`; pinned `blue-09` → 1.23.

## Pipeline, ledger and hashing (`moments/pipeline.py`, `api/insight_ledger.py`)

```python
@dataclass(frozen=True)
class MomentChange:
    kind: Literal["new", "revised", "removed"]
    moment: CandidateMoment | None            # None when removed
    previous: CandidateMoment | None          # None when new
    metrics: tuple[MetricResult, ...]         # results for moment.metric_ids

class MomentPipeline:
    def __init__(self, engine: MetricEngine, params: DetectionParams = DetectionParams()) -> None: ...
    def on_snapshot(self, snapshot: MatchSnapshot, *, revision: bool = False) -> list[MomentChange]: ...
    def reconcile(self, snapshot: MatchSnapshot) -> list[MomentChange]: ...     # full re-detect + diff
    def moments(self) -> list[CandidateMoment]: ...                              # ranked, current
    def metrics(self) -> dict[str, MetricResult]: ...                            # by metric_id, for current moments
    def add_hook(self, on_moment: Callable[[CandidateMoment], None] | None = None,
                 on_moment_revised: Callable[[CandidateMoment, CandidateMoment | None], None] | None = None) -> None: ...

def metric_state_hash(state: MatchState, moments: Sequence[CandidateMoment], metrics: Mapping[str, MetricResult]) -> str: ...
# sha256(canonical JSON {"state": full_state_hash(state), "moments": [dump without state_version, sorted by moment_id],
#                        "metrics": [dump without state_version, sorted by metric_id]})

class InsightLedger:
    def register(self, bundle: InsightBundle, *, moment_id: str, evidence_ids: Sequence[str]) -> None: ...
    def affected(self, moment_ids: Collection[str], evidence_ids: Collection[str]) -> list[tuple[str, int]]: ...   # latest unrevoked versions
    def revoke(self, insight_id: str, insight_version: int, reason: Literal["late_event_revision", "expired", "superseded"]) -> InsightRevoked: ...
    def released(self, as_of_ms: int | None = None) -> list[InsightBundle]: ...                                  # unrevoked, as_of_session_ms ≤ as_of
```

`on_snapshot` re-detects only when an event was applied since the last run, a pending trigger's settle time was crossed, or
`revision=True`. A change is "revised" when the moment dump without `state_version` differs.

## Session wiring (`api/session.py`, extends 001/002)

```text
bus.subscribe("live-state") → Ingestor.accept → results
tick task (every 100 ms on Clock) → Ingestor.tick → results; pipeline.on_snapshot(state.snapshot()); Checkpointer.due → write (background)

result applied event   → WS event (unless bulk) → 001 fact path for completed forward passes (ledger.register)
result applied frame   → WS frame (unless bulk)
result late_frame      → no WS; pipeline.on_snapshot(..., revision=True)
result revision        → WS event; pipeline.on_snapshot(..., revision=True)
result with gap        → WS error {"error":"sequence_gap","detail":"missing 11-11"}
MomentChange new       → EvidenceIndex.add(metrics) → WS metric × n → WS moment → on_moment hooks
MomentChange revised   → ledger.affected → WS insight_revoked × k → WS metric × n → WS moment → on_moment_revised hooks
MomentChange removed   → ledger.affected → WS insight_revoked × k → WS snapshot
reset / backward seek  → new MatchState, Ingestor, MomentPipeline, InsightLedger; checkpoint.clear(store, match_id)
```

`EvidenceIndex` resolves `evt-`/`frm-` IDs through `state.snapshot(as_of)` and `metric-` IDs through its metric map
(latest result per ID).
