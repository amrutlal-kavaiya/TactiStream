# Data Model: 002 Synthetic Simulator

Feed records are the canonical contracts (`match_metadata`, `event`, `tracking_frame`, `feed_envelope` schemas) — this
feature adds **no schema changes**. Everything below is simulator-internal (`backend/src/tactistream/simulator/`) except
the manifest file format, which is a documented artifact for 008 but deliberately *not* a bus contract.

## Configuration (`simulator/config.py`)

```python
ScenarioName = Literal["space_creation", "press_turnover", "switch_escape", "run_no_channel",
                       "press_no_turnover", "switch_closed", "tracking_gap", "demo_match"]
Variant = Literal["A", "B", "C", "D", "E", "F"]
Split = Literal["dev", "eval"]
DEV_SEEDS = range(1, 10_000); EVAL_SEED_MIN = 10_000; SEED_MAX = 2**31 - 1
DEV_VARIANTS = ("A", "B", "C"); EVAL_VARIANTS = ("D", "E", "F")
GENERATOR_VERSION = "0.1.0"
HERO_MATCH_IDS = {("space_creation", 42, "A", "dev"): "demo-blue-amber-001",
                  ("demo_match", 42, "A", "dev"): "demo-blue-amber-002"}

class ConfigError(ValueError):
    code: Literal["invalid_seed", "invalid_variant", "invalid_scenario",
                  "eval_seed_requires_eval_split", "eval_variant_requires_eval_split", "dev_seed_in_eval_split"]

@dataclass(frozen=True, slots=True)
class SimulationConfig:
    seed: int
    scenario: ScenarioName
    variant: Variant = "A"
    split: Split = "dev"
    generator_version: str = GENERATOR_VERSION
    def __post_init__(self) -> None: ...          # raises ConfigError per rules below
    @property
    def match_id(self) -> str: ...                # HERO_MATCH_IDS or "sim-" + sha256(canonical_json(self))[:10]
    def canonical_json(self) -> str: ...
```

| Rule | Error code | CLI message |
|---|---|---|
| `split=dev` and seed ≥ 10000 | `eval_seed_requires_eval_split` | `seed 10000 is reserved for split=eval` |
| `split=dev` and variant ∈ D–F | `eval_variant_requires_eval_split` | `variant D is reserved for split=eval` |
| `split=eval` and seed < 10000 | `dev_seed_in_eval_split` | `split=eval requires seed >= 10000` |
| `split=eval` and variant ∈ A–C | `invalid_variant` | `split=eval requires variant D, E or F` |
| seed < 1 or > 2^31−1 | `invalid_seed` | `seed must be in 1..2147483647` |

## Variants (`simulator/config.py` `VARIANTS: Mapping[Variant, VariantSpec]`)

"Focus team" = the team whose action defines the pattern (runner's team, pressing team, switching team).

| Variant | Split | Focus team | Period → focus attack dir | y-mirror | Key-actor set | Build-up passes | Time scale | Decoy run |
|---|---|---|---|---|---|---|---|---|
| A | dev | Blue | 1 → +x | no | primary | 2 | 1.00 | no |
| B | dev | Blue | 1 → +x | yes | primary | 3 | 1.00 | no |
| C | dev | Blue | 1 → +x | no | alternate | 1 | 1.10 | no |
| D | eval | Blue | 2 → −x | yes | second alternate | 4 | 0.90 | no |
| E | eval | Amber | 1 → −x | no | primary | 0 | 0.85 | no |
| F | eval | Amber | 2 → +x | yes | alternate | 2 | 1.15 | yes (straight run, angle < 15°) |

Scene transform applied to every scripted keyframe: rotate 180° (`x→105−x, y→68−y`) when the focus team attacks −x, then
y-mirror (`y→68−y`) if set. Time scale multiplies every beat interval. Period-2 variants emit metadata
`periods = [{1: blue +1, amber −1}, {2: blue −1, amber +1}]` and `period = 2` on every record.

Key-actor sets (shirt numbers of the focus team / opponent; team prefix follows the focus team):

| Family | primary | alternate | second alternate |
|---|---|---|---|
| space_creation, run_no_channel, tracking_gap | passer 8, receiver 11, runner 9, follower opp 4 | passer 10, receiver 9, runner 7, follower opp 3 | passer 6, receiver 7, runner 10, follower opp 5 |
| press_turnover, press_no_turnover | pressers 9, 11, 10; victim opp 5; interceptor 10 | pressers 7, 9, 8; victim opp 4; interceptor 8 | pressers 11, 10, 6; victim opp 2; interceptor 6 |
| switch_escape, switch_closed | switcher 8, receiver 7, closer opp 3 | switcher 10, receiver 2, closer opp 2 | switcher 6, receiver 11, closer opp 5 |

## Output (`simulator/engine.py`)

```python
@dataclass(frozen=True, slots=True)
class SimulationOutput:
    config: SimulationConfig
    metadata: MatchMetadata
    events: tuple[MatchEvent, ...]        # sequence 1..N, contiguous
    frames: tuple[TrackingFrame, ...]     # frame_index 0..M, contiguous, 100 ms
    manifest: GenerationManifest          # never converted to FeedEnvelope

def simulate(config: SimulationConfig) -> SimulationOutput: ...
```

Record conventions: `session_clock_ms` starts at 0; `period_clock_ms = 840000 + session_clock_ms`; event times on the
100 ms grid; `frame_id = f"frm-{frame_index:06d}"`, `event_id = f"evt-{sequence:04d}"`; positions rounded to 0.01 m;
`source = {"kind": "synthetic", "generator_version": "0.1.0", "seed": seed}` on metadata, events and frames.

## Possession state machine (`simulator/possession.py`)

```python
class Phase(StrEnum): DEAD = "dead"; CONTROLLED = "controlled"; IN_FLIGHT = "in_flight"; LOOSE = "loose"; ENDED = "ended"
@dataclass(frozen=True, slots=True)
class PossessionState:
    phase: Phase
    team_id: TeamId | None          # possessing / last-touch team
    player_id: PlayerId | None
    restart_team: TeamId | None     # set in DEAD after out_of_play
class IllegalTransition(ValueError): ...
LEGAL_TRANSITIONS: Mapping[tuple[Phase, EventType], TransitionRule]
def transition(state: PossessionState, event: MatchEvent) -> PossessionState: ...
def check_sequence(events: Sequence[MatchEvent]) -> list[ValidationIssue]: ...
```

Legal-transition table (`T` = possessing team, `O` = opponent, `p` = player in control). Anything not listed is illegal.

| Phase before | Event type | Actor rule | Outcome(s) | Phase after |
|---|---|---|---|---|
| DEAD (start of period) | `kickoff` | kickoff team, at centre spot ±0.5 m, `recipient_id` teammate | `null` | CONTROLLED(T, recipient) |
| DEAD (after `out_of_play`) | `pass` (restart) | `restart_team` | `complete` / `incomplete` | CONTROLLED(T, recipient) / LOOSE(T) |
| DEAD | `period_end` | any (last actor) | `null` | ENDED |
| CONTROLLED(T, p) | `carry` | p | `null` | CONTROLLED(T, p) |
| CONTROLLED(T, p) | `pass` | p | `complete` / `incomplete` | CONTROLLED(T, recipient) / LOOSE(T) |
| CONTROLLED(T, p) | `shot` | p | `on_target` / `off_target` / `blocked` | LOOSE(T) |
| CONTROLLED(T, p) | `clearance` | p | `null` | LOOSE(T) |
| CONTROLLED(T, p) | `pressure` | O, within 3.0 m of p | `null` | unchanged |
| CONTROLLED(T, p) | `tackle` | O, within 1.5 m of p | `won` / `lost` | CONTROLLED(O, actor) / unchanged |
| CONTROLLED(T, p) | `out_of_play` | p | `null` | DEAD(restart_team = O) |
| CONTROLLED(T, p) | `period_end` | p | `null` | ENDED |
| LOOSE(T) | `interception` | O | `won` | CONTROLLED(O, actor) |
| LOOSE(T) | `ball_recovery` | T or O | `null` | CONTROLLED(actor team, actor) |
| LOOSE(T) | `out_of_play` | last-touch player | `null` | DEAD(restart_team = opponent of actor team) |

`IN_FLIGHT` is internal to kinematics (ball between pass start and arrival); events are never emitted inside it. A
**turnover** (used by 003) is `interception`, `tackle` with `won`, or `ball_recovery` by the team that did not last possess.

## Kinematics (`simulator/kinematics.py`)

```python
MAX_PLAYER_SPEED_MPS = 9.5; MAX_PLAYER_ACCEL_MPS2 = 6.0
PASS_SPEED_RANGE_MPS = (8.0, 25.0); SHOT_SPEED_MAX_MPS = 35.0
BALL_CARRY_MAX_DIST_M = 0.5; BALL_CARRY_OFFSET_M = 0.3
REPOSITION_SPEED_MPS = 7.0; REPOSITION_ACCEL_MPS2 = 4.0; REPOSITION_MIN_MS = 3000; FRAME_MS = 100

@dataclass(frozen=True) class Keyframe: t_ms: int; pos: tuple[float, float]
class KinematicsError(ValueError): player_id: str; t_ms: int; speed: float; accel: float; code: Literal["speed_exceeded", "accel_exceeded"]
def spline_track(keys: Sequence[Keyframe], t_grid: np.ndarray) -> np.ndarray: ...          # C1 cubic Hermite (Catmull–Rom tangents)
def follow_track(targets: np.ndarray, start: tuple[float, float], start_vel: tuple[float, float],
                 max_speed: float, max_accel: float) -> np.ndarray: ...                      # velocity/accel-clamped follower
def check_bounds(player_id: str, track: np.ndarray, frame_ms: int = FRAME_MS) -> None: ...   # strict, pre-rounding; raises KinematicsError
def ball_track(possession_timeline: Sequence[BallPhase], player_tracks: Mapping[str, np.ndarray]) -> np.ndarray: ...
def plan_reposition(start: Mapping[str, tuple[float, float]], end: Mapping[str, tuple[float, float]]) -> tuple[int, dict[str, np.ndarray]]: ...
```

- Scripted actors (passer, receiver, runner, follower, pressers, closer) follow `spline_track` through scenario keyframes;
  `check_bounds` must pass or generation fails (no silent clamping).
- Everyone else follows `follow_track` toward formation slots shifted with the ball (block shift 0.35 × ball Δx, 0.25 × ball Δy),
  plus Ornstein–Uhlenbeck jitter (σ = 0.3 m, θ = 0.5 s⁻¹) from the segment RNG — bounded by construction.
- Ball: controlled → carrier position + 0.3 m along carrier velocity (attack direction when stationary); pass → linear
  interpolation `start_m → end_m` over `duration_ms`; lofted passes (|Δy| ≥ 30 m) add `height_m = 4·h·u(1−u)`, `h = 6 m`;
  dead ball → invisible until 1000 ms before restart, then at the restart spot.

## Roster and formations (`simulator/roster.py`)

```python
def build_metadata(config: SimulationConfig, periods: Sequence[PeriodSpec]) -> MatchMetadata: ...   # teams/players identical to contracts/examples/match_metadata.json
FORMATION_433: Mapping[Literal["in_possession", "out_of_possession", "kickoff"], Mapping[int, tuple[float, float]]]  # shirt → normalized (attack +x) slot
def slots(team: TeamId, phase: str, attack_dir: Literal[1, -1]) -> dict[PlayerId, tuple[float, float]]: ...
```

Roles: 1 GK; 2 RB, 3 LB, 4 CB, 5 CB (DF); 6 DM, 8 CM, 10 CM (MF); 7 RW, 9 CF, 11 LW (FW). Normalized in-possession slots
(x toward the attacked goal): GK (6, 34); back line x = 32; midfield x = 50; front line x = 64; out-of-possession block 10 m deeper.

## Hero beats — `space_creation`, variant A, time scale 1.00 (nominal, before seed jitter)

Dev jitter: every scripted keyframe ±0.5 m per axis, every beat ±200 ms (quantized to 100 ms, order and ≥ 300 ms gaps preserved).

| t (ms) | Event / movement | Actor(s) | Positions (m) |
|---|---|---|---|
| 0 | `kickoff`, recipient blue-08, duration 600 | blue-10 | [52.5, 34.0] → [49.0, 32.0] |
| 600–2600 | `carry` | blue-08 | [49.0, 32.0] → [55.0, 32.5] |
| 2600 | `pass` complete (build-up 1), duration 800 | blue-08 → blue-06 | [55.0, 32.5] → [50.0, 24.0] |
| 4400 | `pass` complete (build-up 2), duration 800 | blue-06 → blue-08 | [50.5, 24.5] → [57.0, 31.5] |
| 4800 | lane "before" reference (t_pass − 4000) | amber-04 | [67.5, 30.0] (≈ 2.4 m from blue-08→blue-11 segment) |
| 5800–8600 | diagonal off-ball run | blue-09 | [66.0, 31.5] → [75.0, 41.5] (13.45 m, 48°, 4.8 m/s mean) |
| 6000–8800 | follows the runner | amber-04 | [67.6, 30.6] → [73.5, 37.5] (cos ≈ 0.99 with run) |
| 8800 | `pass` complete (forward), duration 900 | blue-08 → blue-11 | [58.0, 32.0] → [70.0, 27.0] |
| 9700–12300 | `carry` | blue-11 | [70.0, 27.0] → [86.0, 30.0] |
| 12300 | `shot`, duration 800, outcome from RNG {on_target .4, off_target .4, blocked .2} | blue-11 | [86.0, 30.0] → [105.0, 35.5] |
| 13100 | `out_of_play` | last touch (blue-11 / amber-01 / blocking amber DF) | — |
| 14100 | `period_end` | last actor | — |

All other Amber defenders stay ≥ 5.5 m from the blue-08→blue-11 segment at 8800 ms, so nominal lane clearance goes
≈ 2.4 m → ≈ 6.0 m (gain ≈ 3.6 m). Build-up pass count follows the variant (A = 2); extra passes are inserted between
blue-06/blue-08/blue-04 before the run and shift later beats.

## Other families (beat outline; exact keyframes live in the scenario modules)

- **press_turnover**: focus team presses the opponent's build-up in the opponent's defensive third. Two `pressure` events
  (pressers 9 then 11), then the victim's pass is `incomplete` and the interceptor makes an `interception` (`won`) ≈ 700 ms
  later, carries, passes, shoots → `out_of_play` → `period_end`.
- **press_no_turnover**: same press intensity; the victim completes a pass to an unpressed full-back (nearest focus player
  ≥ 6 m), opponent circulates ≥ 5 s and plays a long ball `out_of_play`. No turnover.
- **switch_escape**: focus team circulates on one flank (y ≥ 50 before mirror) with 3 opponents within 6 m of the ball; the
  switcher plays a lofted `pass` with |Δy| ≥ 34 m, duration ≈ 2000 ms, to the far-side receiver (nearest defender ≥ 7 m at
  reception), who carries and shoots → `out_of_play`.
- **switch_closed**: same switch (|Δy| ≥ 30 m) but the closer reaches ≤ 3.0 m of the receiver at reception; the receiver
  makes a short `carry`, the closer wins a `tackle` within 2 s of reception and plays a `clearance` → `out_of_play`. Only one closing defender (second-nearest ≥ 8 m), so the pressure
  proxy stays < 30.
- **run_no_channel**: hero geometry, but the follower holds (displacement ≤ 2 m) and the opponent DM steps into the lane;
  forward pass still completes, carry, shot.
- **tracking_gap**: identical to `space_creation` for the same seed/variant; then players {runner, follower, opp 3, opp 5 —
  i.e. blue-09, amber-04, amber-03, amber-05 in A} get `visible=false` (no `pos_m`) from `run_start − 1000` to
  `forward_pass + 500` ms. Ball stays visible.
- **circulation** (program filler only): safe passes 6–15 m, no |Δy| ≥ 30 m pass, nearest opponent to the carrier ≥ 4 m,
  no turnover, no shot, and no off-ball run that would qualify under 003's `off_ball_run` thresholds (≥ 8 m within ≤ 4 s,
  ≥ 4 m/s, 20–70° to the attack axis); starts with the restart pass and ends with an `out_of_play` that hands the restart
  to the team the next segment needs (or with `period_end` if last).

## Scenario intent checks (`backend/tests/simulator/intent.py`, test-only)

Checks use test-local geometry (attack-normalized) so 002 does not depend on 003. Margins sit above 003's detection thresholds.

| Family | Must hold |
|---|---|
| space_creation | runner displacement ≥ 10 m within ≤ 3.2 s, mean speed ≥ 4.3 m/s, angle 30–60°; nearest opponent to runner at run start is the follower and its displacement cosine with the run ≥ 0.8; lane clearance (min opponent distance to passer→receiver segment) gain from t−4000 to t_pass ≥ 2.5 m; a `shot` by the focus team follows within 6 s |
| run_no_channel | same run constraints; lane clearance gain ≤ 1.0 m; forward pass completes; shot follows |
| press_turnover | pressure proxy `(100/3)·Σ exp(−d_i/2.5)` over the 3 nearest focus players to the victim ≥ 40 at the victim's last on-ball event, which is ≤ 3000 ms before a focus-team turnover |
| press_no_turnover | pressure ≥ 40 at some victim on-ball event and no focus-team turnover within 5000 ms after it |
| switch_escape | completed pass with |Δy| ≥ 34 m; receiver's nearest-opponent distance at reception ≥ 7 m |
| switch_closed | completed pass with |Δy| ≥ 30 m; receiver's nearest-opponent distance at reception ≤ 3.5 m; opponent `tackle` `won` ≤ 2000 ms after reception; pressure on receiver at reception < 30 |
| tracking_gap | gap players invisible for every frame in the gap window; zero fabricated positions; non-gap records equal `space_creation` for the same seed/variant |

## Demo match program (`simulator/program.py`)

```python
@dataclass(frozen=True) class Segment: scenario: ScenarioName | Literal["circulation"]; params: Mapping[str, float | str] = {}
@dataclass(frozen=True) class MatchProgram:
    name: str; segments: tuple[Segment, ...]
    def run(self, config: SimulationConfig) -> SimulationOutput: ...
DEMO_MATCH = MatchProgram("demo_match", (...))   # order below
```

| # | Segment | Nominal length | Start |
|---|---|---|---|
| 1 | space_creation (A geometry) | ≈ 14 s | kickoff |
| 2 | circulation (restart team), 30 s | 30 s | restart |
| 3 | press_turnover | ≈ 16 s | restart (Amber in possession) |
| 4 | circulation, 30 s | 30 s | restart |
| 5 | run_no_channel | ≈ 14 s | restart (Blue) |
| 6 | circulation, 35 s | 35 s | restart |
| 7 | switch_escape | ≈ 16 s | restart (Blue) |
| 8 | press_no_turnover | ≈ 14 s | restart (Amber) |
| 9 | circulation, 30 s | 30 s | restart |
| 10 | switch_closed | ≈ 14 s | restart (Blue) |
| 11 | circulation, 25 s, ends with `period_end` | 25 s | restart |

Between segments: dead ball (ball invisible), `plan_reposition` interval `max(3000, ceil_100(max_dist / 7.0 m/s) + 1000)` ms,
restart pass. Segment i uses RNG `SeedSequence([seed, i])`; segment 1 therefore equals standalone `space_creation`
(same seed, variant A, sub-stream 0). Expected total ≈ 278 s; required range 240–300 s.

## Manifest (`simulator/manifest.py`) — written to `manifest.json` only

```python
@dataclass(frozen=True) class SegmentLabel:
    index: int; scenario: str; variant: Variant; start_ms: int; end_ms: int
    positive: bool; expected_pattern: MomentPattern | None; negative_of: MomentPattern | None
    key_players: Mapping[str, PlayerId]          # e.g. {"runner": "blue-09", "follower": "amber-04", "passer": ..., "receiver": ...}
    key_event_ids: Mapping[str, EventId]         # hero A: {"forward_pass": "evt-0005", "shot": "evt-0007"}
    intended_explanation: str                    # English, for reviewers only
@dataclass(frozen=True) class TrackingGap: player_ids: tuple[PlayerId, ...]; start_ms: int; end_ms: int
@dataclass(frozen=True) class GenerationManifest:
    manifest_version: Literal["1"]; match_id: str; config: SimulationConfig
    segments: tuple[SegmentLabel, ...]; tracking_gaps: tuple[TrackingGap, ...]
    feed_sha256: str; event_count: int; frame_count: int; duration_ms: int
```

`expected_pattern` per family: space_creation → `space_creation`; press_turnover → `press_turnover`; switch_escape →
`switch_escape`; run_no_channel → `shot` (negative_of `space_creation`); press_no_turnover → `None` (negative_of
`press_turnover`); switch_closed → `None` (negative_of `switch_escape`); tracking_gap → `shot` (negative_of
`space_creation`, reason missing tracking); circulation → `None`.

## Validation (`simulator/validate.py`)

```python
IssueCode = Literal["schema_invalid", "speed_exceeded", "accel_exceeded", "ball_detached", "pass_start_mismatch",
                    "pass_end_mismatch", "pass_ball_speed", "event_coord_mismatch", "illegal_transition",
                    "attack_direction_inconsistent", "sequence_gap", "frame_gap", "roster_incomplete", "out_of_bounds"]
@dataclass(frozen=True) class ValidationIssue: code: IssueCode; record_id: str; detail: str
@dataclass(frozen=True) class ValidationReport:
    issues: tuple[ValidationIssue, ...]; unchecked: int
    @property
    def ok(self) -> bool: ...
def validate_output(output: SimulationOutput) -> ValidationReport: ...
def validate_envelopes(envelopes: Sequence[FeedEnvelope]) -> ValidationReport: ...   # same checks from a feed file
```

Tolerances on serialized (0.01 m) data: speed via 1-frame difference ≤ 9.5 + 0.15 m/s; acceleration via 200 ms second
difference ≤ 6.0 + 0.5 m/s²; distances +0.02 m. Speed/accel are only measured between consecutive visible frames; across an
invisibility gap the mean speed over the gap must be ≤ 9.5 m/s. `attack_direction_inconsistent`: every shot moves toward
the goal the shooter's team attacks in that period, and `on_target`/`off_target` shots end within 2 m of that goal line;
kickoff at (52.5, 34) ± 0.5 m; metadata `periods` contains every period used by a record.

## Files (`simulator/io.py`)

```python
BASE_PUBLISHED_EPOCH_MS = 1_792_000_000_000
def to_envelopes(output: SimulationOutput) -> list[FeedEnvelope]: ...   # metadata first, then by session_clock_ms, events before frames at equal time; published_ms = BASE + session_clock_ms
def canonical_line(obj: Mapping[str, object]) -> bytes: ...               # sort_keys, separators=(",", ":"), ensure_ascii=False, "\n"
def write_output(output: SimulationOutput, out_dir: Path, *, force: bool = False) -> WrittenFiles: ...   # feed.jsonl, manifest.json via temp dir + rename
@dataclass(frozen=True) class WrittenFiles: feed_path: Path; manifest_path: Path; feed_sha256: str
```

`feed.jsonl` is readable by 001's `transport/fixtures.load_fixture`.

## Replay additions (`transport/replayer.py`, extends 001)

```python
ALLOWED_SPEEDS = (0.5, 1.0, 2.0)
@dataclass(frozen=True) class SeekResult: to_ms: int; rewound: bool; published: int; last_record_id: str | None
class FeedReplayer:                                    # 001 fields unchanged; added:
    wall_ms: Callable[[], int] = epoch_ms              # re-stamps published_ms at publish
    on_rewind: Callable[[], Awaitable[None]] | None = None
    @property
    def duration_ms(self) -> int: ...
    def set_speed(self, speed: float) -> None: ...     # ValueError if not in ALLOWED_SPEEDS; re-anchors clock
    async def seek(self, to_ms: int) -> SeekResult: ...
```

State transitions:

```text
Playback: paused --play--> playing --pause--> paused; playing --(last record)--> ended
          any --set_speed(s)--> same state; session clock continuous (anchor = current session time)
          any --seek(t ≥ cursor)--> publish records in (cursor, t] as burst --> paused or playing (unchanged); t ≥ duration --> ended
          any --seek(t < cursor)--> on_rewind() --> cursor = 0 --> publish metadata + records ≤ t as burst
Session:  seek requested --> bulk=True (suppress per-record WS) --> consumer applies last_record_id --> bulk=False --> broadcast snapshot
```

## API additions (`api/scenarios.py`, `api/routes_sessions.py`, `api/session.py`)

```python
@dataclass(frozen=True) class ScenarioInfo: scenario: str; display_name: str; variants: tuple[str, ...]; default_seed: int; duration_ms: int
def list_scenarios() -> list[ScenarioInfo]: ...                                       # skeleton + 8 simulator scenarios (dev only)
def load_scenario_envelopes(scenario: str, seed: int, variant: str) -> list[FeedEnvelope]: ...   # lru_cache(maxsize=8); skeleton → fixture
class SessionRegistry:                               # 001; added:
    def get_or_create(self, scenario: str, seed: int, variant: str) -> tuple[MatchSession, bool]: ...   # (session, shared)
    max_sessions: int = 8
```
