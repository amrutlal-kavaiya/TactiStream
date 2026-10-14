# Data Model: 005 Why Mode Replay

Canonical shapes: `contracts/schemas/scene_annotations.schema.json` (new, see [contracts/replay-api.md](contracts/replay-api.md))
plus existing `candidate_moment`, `tracking_frame`, `event`, `metric_result`, `insight_packet` schemas.

## Contract models (`backend/src/tactistream/contracts/scene.py`)

| Type | Fields (all frozen, `extra="forbid"`) |
|---|---|
| `Window` | `start_ms: int`, `end_ms: int` (validator: `end_ms > start_ms`) |
| `HighlightAnnotation` | `annotation_id`, `kind: Literal["highlight"]`, `player_id`, `team_id`, `evidence_ids: list[EvidenceId]` |
| `PathPoint` | `t_ms`, `frame_id`, `pos_m: PointM` |
| `PathAnnotation` | `annotation_id`, `kind: Literal["path"]`, `player_id`, `team_id`, `segments: list[list[PathPoint]]` (each ≥ 2 points, ordered), `evidence_ids` |
| `ChannelKeyframe` | `phase: Literal["before","at_pass"]`, `t_ms`, `frame_id`, `passer_pos_m`, `receiver_pos_m`, `clearance_m: float`, `nearest_defender_id`, `nearest_defender_pos_m`, `closest_point_m` |
| `ChannelAnnotation` | `annotation_id`, `kind: Literal["channel"]`, `metric_id`, `anchor_event_id`, `passer_id`, `receiver_id`, `unit: Literal["m"]`, `keyframes: tuple[ChannelKeyframe, ChannelKeyframe]` (before then at_pass, `t` strictly increasing), `evidence_ids` |
| `PressureRingAnnotation` | `annotation_id`, `kind: Literal["pressure_ring"]`, `carrier_id`, `team_id`, `metric_id`, `t_ms`, `frame_id`, `center_m`, `radius_m: float ≥ 0`, `defender_ids: list[PlayerId]` (≤ 3), `score: float`, `unit: Literal["score_0_100"]`, `evidence_ids` |
| `SceneAnnotation` | discriminated union on `kind` of the four above |
| `UnresolvedAnnotation` | `annotation_id: str`, `reason: Literal["unknown_player","player_not_visible","metric_missing","metric_unavailable","outside_window","inconsistent_geometry"]` |
| `SceneAnnotations` | `schema_version`, `match_id`, `moment_id`, `state_version`, `window`, `frame_interval_ms: Literal[100]`, `annotation_source: Literal["insight","default"]`, `tracking_coverage: float`, `partial_tracking: bool`, `annotations: list[SceneAnnotation]` (sorted by ID), `unresolved: list[UnresolvedAnnotation]` |
| `ReplayResponse` | `moment: CandidateMoment`, `frames: list[TrackingFrame]`, `events: list[MatchEvent]`, `scene: SceneAnnotations` |
| `ReplayUnavailable` | `error: Literal["insufficient_tracking"]`, `detail: str`, `moment: CandidateMoment`, `events: list[MatchEvent]` |

Invariants (model validators + tests):

- Every `PathPoint.pos_m`, `ChannelKeyframe.passer_pos_m/receiver_pos_m/nearest_defender_pos_m`, and
  `PressureRingAnnotation.center_m` equals a position in the referenced frame.
- `ChannelKeyframe.clearance_m` equals the metric component (`clearance_before_m` for `before`, `clearance_at_pass_m`
  for `at_pass`).
- All `t_ms` lie in `window`; all `annotation_id`s match `AnnotationId` pattern in `common.schema.json`.

## Runtime (non-contract) backend types

```python
# moments/scene.py
@dataclass(frozen=True)
class TrackingVerdict:
    ok: bool
    detail: str | None = None            # e.g. "Tracking coverage 0.42 is below 0.6"

# api/replay.py
class ReplayService:
    session: MatchSession
    _cache: OrderedDict[tuple[str, int, str], ReplayResponse]   # LRU, 32 entries, cleared on reset
```

## Frontend types

| Module | Types |
|---|---|
| `scene/frameSource.ts` | `SampledEntity`, `SampledFrame`, `FrameSource`, `liveFrameSource()` |
| `replay/ReplayController.ts` | `ReplaySpeed = 0.5 \| 1`, `ReplayStatus`, `ReplayCursor`, `ReplayController` |
| `scene/annotationGeometry.ts` | `Vec2`, `channelBandAt`, `trailUntil`, `pressureRingAt`, `highlightAt` |
| `scene/cameraPoses.ts` | `CameraPreset`, `cameraPose()` |
| `store/matchStore.ts` | `Surface`, `ReplayLoadState`, `openReplay`, `closeReplay`, `replays` |
| generated | `SceneAnnotations`, `ReplayResponse`, `ReplayUnavailable` from the new schema |

## State transitions

```text
Surface:        live --openReplay(m)--> replay(m) --closeReplay | Escape | reset--> live

ReplayLoad(m):  idle --openReplay--> loading --200--> ready(response)
                                       loading --409--> insufficient(body)
                                       loading --404/5xx--> error
                ready/insufficient are cached per moment_id until reset or moment.state_version changes

ReplayController:
                paused --play--> playing --pause--> paused
                playing --(t reaches end, loop=false)--> ended --play--> playing (from start)
                playing --(t reaches end, loop=true)--> playing (t wraps to start + overflow)
                any --seek(t)--> same status (ended → paused if t < end); t clamped to [start, end]
```

## Pattern → expected annotations (fixtures)

| Scenario (seed 42) | Moment pattern | Expected resolved kinds |
|---|---|---|
| `space_creation` (hero) | `space_creation` | `highlight` (runner Blue 9), `path` (Amber defender), `channel` |
| `press_turnover` | `press_turnover` | `pressure_ring` (carrier), `highlight` (ball winner), `path` (nearest presser) |
| `switch_escape` | `switch_escape` | `pressure_ring` (passer), `highlight` + `path` (switch receiver) |
| missing-data fixture | any | none — 409 `insufficient_tracking` |
