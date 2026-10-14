# Implementation Plan: Why Mode — evidence-backed 3D tactical replay

**Branch**: `005-why-mode-replay` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-why-mode-replay/spec.md`

## Summary

Add a deterministic replay endpoint that packages the 8–12 s before a candidate moment (10 Hz frames, events) with
server-computed `SceneAnnotations` resolved from annotation IDs (`highlight_*`, `path_*`, `show_channel_*`,
`pressure_ring_*`). The frontend gains a React Three Fiber pitch shared by the live surface and the tactical replay,
a pure-TS `ReplayController` (play/pause/scrub/0.5×–1×/loop, gap-aware linear interpolation), annotation drawing,
camera presets, a keyboard timeline, a Why button, and an evidence drawer extended with definitions, windows,
coordinates and fact/interpretation status. Missing tracking produces a 409 with events and an honest message.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend), Node 22

**Primary Dependencies**: existing FastAPI/Pydantic stack (001); new frontend deps `three`, `@react-three/fiber`
(9.x, React 19 compatible), `@react-three/drei` (10.x) pinned to exact versions (research R1); dev deps `@types/three`,
`@react-three/test-renderer`, `@axe-core/playwright`

**Storage**: in-memory (MatchState frames/events from 003; replay response LRU cache, 32 entries)

**Testing**: pytest (unit, golden, integration via httpx ASGI + FakeClock); Vitest + Testing Library +
`@react-three/test-renderer`; Playwright (chromium) e2e + axe

**Target Platform**: Chromium/Edge/Firefox with WebGL 2; Linux container backend

**Project Type**: Web application (backend + frontend), registry layout from `specs/README.md`

**Performance Goals**: ≥ 30 fps during replay on the demo machine (measured, 008 release gate); replay endpoint p95
≤ 300 ms server time for a 12 s window; Why → visible replay ≤ 1.5 s

**Constraints**: no model call on the replay path; no client-invented positions; per-frame updates via refs (no React
re-render per animation frame); Why never sends match control commands

**Scale/Scope**: 1 match, ≤ 10 viewers, ≤ 121 frames × 23 entities per replay, 3 patterns (hero + 2)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Evidence before narrative | PASS | Every drawn position is a supplied frame position or interpolation between two visible consecutive frames; channel clearance values are copied from metric components; `inconsistent_geometry` guard; insufficient tracking → 409 with events and "Insufficient tracking for this explanation"; drawer separates "Verified fact" and "Interpretation" |
| II Provenance | PASS | Synthetic badge on replay; "Partial tracking" badge; fictional Blue/Amber; three/R3F/drei licences in `docs/permitted-assets.md` |
| III Deterministic core | PASS | `moments/scene.py` is pure and deterministic (golden test, byte-identical); annotation IDs from 004 are only resolved, never coordinates; replay path has no model call |
| IV Contract-first | PASS | New `scene_annotations.schema.json` + examples + Pydantic `contracts/scene.py` + generated TS; contract tests first (T005) |
| V Test-first | PASS | Every implementation task preceded by a failing test; golden + fixture tests for scene; ReplayController unit tests; e2e |
| VI Measure | PASS | FPS overlay + `capture-fps.mjs`; dev-machine number recorded with hardware and labelled; release measurement deferred to 008 |
| VII Scope | PASS | Simplified pitch only (no stadium/video); stop rule recorded in spec; no new backend services |

Post-design re-check: PASS (no violations).

## Project Structure

### Documentation (this feature)

```text
specs/005-why-mode-replay/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
└── contracts/
    └── replay-api.md        # replay endpoint, SceneAnnotations, evidence presentation extension
```

### Source Code (repository root)

```text
contracts/
├── schemas/scene_annotations.schema.json          NEW ($defs SceneAnnotations, ReplayResponse, ReplayUnavailable)
└── examples/{scene_annotations,replay_response,replay_unavailable}.json   NEW
backend/
├── src/tactistream/
│   ├── contracts/scene.py                         NEW Pydantic models
│   ├── moments/annotation_ids.py                  (from 004) parse/format annotation IDs
│   ├── moments/scene.py                           NEW replay_window, assess_tracking, default_annotations, build_scene
│   ├── api/replay.py                              NEW ReplayService (assemble + cache)
│   ├── api/routes_replay.py                       NEW GET /api/matches/{id}/replay/{moment_id}
│   ├── api/routes_evidence.py                     EXTEND ?language= + presentation for metrics
│   ├── api/app.py                                 EXTEND register router, GZipMiddleware
│   └── narrative/catalog/{en,hi}.json             EXTEND metric_title.*, metric_def.*, limitation.*, unit.*, label.partial_tracking
└── tests/
    ├── contract/test_examples.py                  EXTEND rows for new examples
    ├── golden/scene_space_creation_42.json        NEW golden scene
    ├── unit/{test_annotation_ids,test_replay_window,test_scene,test_scene_golden,test_evidence_presentation}.py
    └── integration/{test_replay_api,test_replay_insufficient,test_replay_patterns}.py
frontend/
├── package.json                                   EXTEND exact-pinned three, @react-three/fiber, @react-three/drei
├── scripts/capture-fps.mjs                        NEW Playwright FPS capture → eval/results/fps/
├── src/
│   ├── api/client.ts                              EXTEND getReplay, getEvidence(language)
│   ├── store/matchStore.ts                        EXTEND surface, replay cache, openReplay/closeReplay
│   ├── scene/{coords.ts,frameSource.ts,annotationGeometry.ts,cameraPoses.ts,useReducedMotion.ts}   NEW pure helpers
│   ├── scene/{PitchScene,Players,Ball,Annotations,CameraRig,FpsOverlay,SceneDescription}.tsx          NEW
│   ├── replay/ReplayController.ts                 NEW
│   ├── components/{WhyButton,ReplayView,Timeline,MainSurface}.tsx                                     NEW
│   ├── components/{InsightCard,EvidenceDrawer,PlaybackControls}.tsx                                   EXTEND
│   ├── App.tsx                                    EXTEND MainSurface + Timeline layout
│   └── i18n/{en,hi}.ts                            EXTEND replay/evidence chrome strings
└── tests/
    ├── setup.ts                                   EXTEND matchMedia / ResizeObserver stubs
    ├── unit/{coords,frameSource,ReplayController,annotationGeometry,cameraPoses,matchStore.replay,client.replay}.test.ts
    ├── unit/{Players,Annotations,PitchScene,WhyButton,ReplayView,MainSurface,Timeline,EvidenceDrawer.replay,SceneDescription}.test.tsx
    └── e2e/{why-mode,why-mode-insufficient,why-mode-patterns,a11y}.spec.ts
docs/permitted-assets.md                           EXTEND three / R3F / drei (MIT)
```

**Structure Decision**: Registry layout. Scene resolution lives in `moments/` because it is deterministic match-engine
geometry (constitution III), not an agent concern; HTTP assembly lives in `api/replay.py`. Frontend splits pure
logic (`scene/*.ts`, `replay/ReplayController.ts`) from R3F components so most behaviour is testable without WebGL.

## Key Design Notes

**Backend signatures**

```python
# moments/annotation_ids.py
AnnotationKind = Literal["highlight", "path", "channel", "pressure_ring"]
@dataclass(frozen=True)
class ParsedAnnotation:
    kind: AnnotationKind
    player_id: PlayerId | None        # highlight/path/pressure_ring
    seq: int | None                   # channel
    @property
    def metric_id(self) -> str | None: ...   # "metric-channel-{seq:04d}" for channel
def parse_annotation_id(annotation_id: str) -> ParsedAnnotation: ...   # raises AnnotationIdError
def annotation_id_for(kind: AnnotationKind, *, player_id: PlayerId | None = None, seq: int | None = None) -> str: ...

# moments/scene.py
MIN_REPLAY_COVERAGE: Final = 0.6
MAX_FRAME_GAP_MS: Final = 150
REPLAY_MIN_MS: Final = 8000
REPLAY_MAX_MS: Final = 12000
def replay_window(moment: CandidateMoment, first_frame_ms: int) -> Window: ...
def assess_tracking(moment: CandidateMoment, metrics: Sequence[MetricResult],
                    annotation_ids: Sequence[str]) -> TrackingVerdict: ...   # ok | insufficient(detail)
def default_annotations(moment: CandidateMoment, metrics: Mapping[str, MetricResult],
                        events: Sequence[MatchEvent], frames: Sequence[TrackingFrame]) -> list[str]: ...
def build_scene(moment: CandidateMoment, annotation_ids: Sequence[str], *, source: Literal["insight", "default"],
                frames: Sequence[TrackingFrame], events: Sequence[MatchEvent],
                metrics: Mapping[str, MetricResult], metadata: MatchMetadata) -> SceneAnnotations: ...

# api/replay.py
class ReplayInsufficientTracking(Exception):
    body: ReplayUnavailable
class ReplayService:
    def __init__(self, session: MatchSession, cache_size: int = 32) -> None: ...
    def get(self, moment_id: str) -> ReplayResponse: ...   # raises KeyError (404) / ReplayInsufficientTracking (409)
```

- Inputs come from 003's `MatchSnapshot` (frames/events between times, as of the session clock), the 001
  `EvidenceIndex` (metric records by ID, as-of), and the session's released bundles (004) for annotation IDs.
- Geometry reuses 003's `metrics/geometry.py` (`distance`, `point_segment_distance(p, a, b) -> tuple[float, PointM]`);
  if absent, those two helpers are added there (they are metric geometry) rather than duplicated in `scene.py`.
- Serialisation: `model_dump(mode="json", exclude_none=True)`; floats already rounded to 0.1 m where they are computed
  (closest points, radius); copied frame positions untouched. Golden test compares `json.dumps(sort_keys=True)`.
- Cache key `(moment_id, moment.state_version, sha1(sorted annotation_ids))`; reset clears the cache.
- `build_scene` resolves each annotation ID through 004's `moments.annotations.resolve_annotation` (player, metric and frame
  IDs) and only adds geometry on top. The output checks and the replay therefore accept and reject exactly the same IDs.

**Frontend signatures**

```ts
// scene/coords.ts
export function toWorld(p: readonly [number, number], heightM?: number): [number, number, number];
// scene/frameSource.ts
export interface SampledEntity { id: string; team: "blue" | "amber"; pos: [number, number] }
export interface SampledFrame { tMs: number; players: SampledEntity[]; ball: { pos: [number, number]; heightM: number } | null; gap: boolean }
export interface FrameSource { tick?(dtMs: number): void; sample(): SampledFrame | null }
export function liveFrameSource(get: () => TrackingFrame | null): FrameSource;
// replay/ReplayController.ts
export type ReplaySpeed = 0.5 | 1;
export type ReplayStatus = "playing" | "paused" | "ended";
export interface ReplayCursor { tMs: number; status: ReplayStatus; speed: ReplaySpeed; loop: boolean }
export class ReplayController implements FrameSource {
  constructor(frames: TrackingFrame[], window: { start_ms: number; end_ms: number },
              opts?: { speed?: ReplaySpeed; loop?: boolean; maxGapMs?: number });
  play(): void; pause(): void; seek(tMs: number): void; setSpeed(s: ReplaySpeed): void; setLoop(on: boolean): void;
  tick(dtMs: number): void; sample(tMs?: number): SampledFrame; get cursor(): ReplayCursor;
  subscribe(listener: (c: ReplayCursor) => void): () => void;   // status changes + ≤ 10 Hz time updates
}
// scene/annotationGeometry.ts
export function channelBandAt(a: ChannelAnnotation, tMs: number): { a: Vec2; b: Vec2; halfWidthM: number; visible: boolean };
export function trailUntil(p: PathAnnotation, tMs: number, sample: SampledFrame): Vec2[][];
export function pressureRingAt(r: PressureRingAnnotation, tMs: number): { center: Vec2; radiusM: number; visible: boolean };
// scene/cameraPoses.ts
export type CameraPreset = "broadcast" | "top_down" | "follow_runner";
export function cameraPose(preset: CameraPreset, focus: Vec2 | null): { position: Vec3; target: Vec3; fov: number };
// store/matchStore.ts (additions)
surface: { kind: "live" } | { kind: "replay"; momentId: string };
replays: Record<string, ReplayLoadState>;   // idle | loading | ready(ReplayResponse) | insufficient(ReplayUnavailable) | error
openReplay(momentId: string): Promise<void>; closeReplay(): void;
```

- **Interpolation rule**: `sample(t)` finds frames `f0.t ≤ t < f1.t`. If `f1.t − f0.t > 150 ms` → `gap = true` and no
  entity is drawn. Otherwise an entity is drawn iff visible in both `f0` and `f1`, at `lerp(p0, p1, (t − f0.t)/(f1.t − f0.t))`;
  at `t == f.t` exactly, entities visible in `f` are drawn at their supplied position.
- **Channel band**: hidden before `keyframes[0].t_ms`; between keyframes endpoints and half-width interpolate linearly;
  holds the `at_pass` state for 2 s after `keyframes[1].t_ms`, then fades. Label "1.9 m → 5.3 m" uses the two
  `clearance_m` values formatted with 1 decimal (numbers come only from the payload).
- **Render loop**: `PitchScene` calls `source.tick?.(delta)` and `source.sample()` inside `useFrame`, writing
  instance matrices via refs; React state changes only on cursor subscription (≤ 10 Hz) for the scrubber.
- **Live surface**: `liveFrameSource(() => useMatchStore.getState().latestFrame)` (transient read, no subscription).
- **Camera**: broadcast `(0, 38, 62)` → target `(0, 0, 0)`, fov 40; top_down `(0, 95, 0.01)`, fov 45; follow_runner
  offset `(−12, 18, 22)` from the focus player; transitions use damped lerp ≤ 600 ms, instant under reduced motion.
- **Accessibility**: canvas `role="img"` with `aria-label` "Tactical replay"; `SceneDescription` renders a visually
  hidden list derived from the scene and metadata names (`useT`); `InsightCard` container `aria-live="polite"`.
- **FPS**: `FpsOverlay` uses `useFrame` deltas, rolling 1 s mean, pushes `{t, fps}` to `window.__tactistreamFps`.
  `capture-fps.mjs --url --scenario space_creation --seed 42 --seconds 20` starts a session, opens Why on the hero
  card, records for N seconds, writes `{fps_mean, fps_p5, fps_min, samples, duration_ms, user_agent, viewport,
  gpu (WEBGL_debug_renderer_info if available), machine_label}` JSON.

## Complexity Tracking

No violations. (New dependencies `three` / R3F / drei are named in the constitution's platform constraints; the new
schema follows principle IV.)
