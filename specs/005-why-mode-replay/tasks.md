---
description: "Task list for 005 Why Mode replay"
---

# Tasks: Why Mode — evidence-backed 3D tactical replay

**Input**: `specs/005-why-mode-replay/` (spec, plan, research, data-model, contracts/replay-api.md, quickstart)

**Prerequisites**: 001–004 merged (WsHub, MatchSession, EvidenceIndex, MatchSnapshot, MetricEngine, detector,
`explain_moment`, scripted model client, InsightBundle with 4 variants).

**Tests**: REQUIRED (constitution V). Each implementation task is preceded by a test task that must fail first for the
stated reason.

**Format**: `[ID] [P?] [Story] Description` — `[P]` = parallelizable (different files, no unmet dependency).

## Phase 1: Setup

- [ ] T001 [P] Add exact-pinned (`npm install --save-exact`) `three`, `@react-three/fiber` (9.x), `@react-three/drei` (10.x) and dev deps `@types/three`, `@react-three/test-renderer`, `@axe-core/playwright` to `frontend/package.json`; commit `frontend/package-lock.json`; record resolved versions in `specs/005-why-mode-replay/research.md` R1
- [ ] T002 [P] Extend `frontend/tests/setup.ts` (wired in `frontend/vite.config.ts` `test.setupFiles`) with `window.matchMedia` stub (controllable `prefers-reduced-motion`), `ResizeObserver` stub and `requestAnimationFrame` fake helpers
- [ ] T003 [P] Add `three`, `@react-three/fiber`, `@react-three/drei` (MIT, URLs, versions) to `docs/permitted-assets.md` (create with a table header `Asset | Licence | Source | Used for` if absent)
- [ ] T004 [P] Update `frontend/playwright.config.ts`: webServer env `TACTISTREAM_AGENTS=scripted`, chromium launch args `--use-angle=swiftshader --enable-unsafe-swiftshader`, `trace: "retain-on-failure"`

**Checkpoint**: `make install && make test` green; versions recorded.

---

## Phase 2: Foundational (blocks all stories)

### Contracts

- [ ] T005 Write failing rows in `backend/tests/contract/test_examples.py`: `scene_annotations.json`→`SceneAnnotations`, `replay_response.json`→`ReplayResponse`, `replay_unavailable.json`→`ReplayUnavailable` (schema-valid and Pydantic round-trip equal); negative cases rejected by both schema and model: channel with one keyframe, keyframes out of time order, path segment with 1 point, annotation ID `highlight_red_09`, `unresolved.reason = "other"`
- [ ] T006 Create `contracts/schemas/scene_annotations.schema.json` (`$defs` `SceneAnnotations`, `ReplayResponse`, `ReplayUnavailable`, annotation kinds as in `specs/005-why-mode-replay/contracts/replay-api.md`, reusing `common.schema.json` defs) and examples `contracts/examples/{scene_annotations,replay_response,replay_unavailable}.json` (replay_response with 3 frames and 1 event); add the schema row to `contracts/README.md`
- [ ] T007 Implement `backend/src/tactistream/contracts/scene.py` per data-model.md (discriminated union on `kind`, keyframe order validator) and export from `contracts/__init__.py`. Run T005 → green
- [ ] T008 Run `npm run contracts:gen` and commit regenerated `frontend/src/contracts/generated.ts` (`make contracts` clean)

### Pure primitives

- [ ] T009 [P] Extend `backend/tests/unit/test_annotation_ids.py` (module created by 004 T033; add any case below not yet covered and confirm it fails first if behaviour is missing): `parse_annotation_id("highlight_blue_09")` → kind `highlight`, `player_id="blue-09"`; `"path_amber_04"` → `path`, `amber-04`; `"show_channel_0042"` → `channel`, `seq=42`, `metric_id="metric-channel-0042"`; `"pressure_ring_blue_08"` → `pressure_ring`, `blue-08`; `"highlight_blue_9"`, `"show_channel_42"`, `"glow_blue_09"` → `AnnotationIdError`; `annotation_id_for` round-trips all four
- [ ] T010 [P] Complete `backend/src/tactistream/moments/annotation_ids.py` (exists from 004 T033) so T009 passes (`ParsedAnnotation`, `parse_annotation_id`, `annotation_id_for`, `AnnotationIdError`)
- [ ] T011 [P] Write failing `backend/tests/unit/test_replay_window.py`: moment window 36000–46500 → unchanged (10.5 s); 30000–46500 → start 34500 (12 s cap); 42000–46500 → start 38500 (8 s floor); 3000–6000 with first frame at 0 → start 0, end 6000 (short match); first frame 1200 → start 1200
- [ ] T012 [P] Create `backend/src/tactistream/moments/scene.py` with constants (`MIN_REPLAY_COVERAGE=0.6`, `MAX_FRAME_GAP_MS=150`, `REPLAY_MIN_MS=8000`, `REPLAY_MAX_MS=12000`) and `replay_window(moment, first_frame_ms)`. Run T011 → green
- [ ] T013 [P] Write failing `frontend/tests/unit/coords.test.ts`: `toWorld([0,0])` → `[-52.5,0,34]`; `toWorld([105,68])` → `[52.5,0,-34]`; `toWorld([52.5,34],1.2)` → `[0,1.2,0]`
- [ ] T014 [P] Implement `frontend/src/scene/coords.ts` (`toWorld`, `PITCH_LENGTH_M=105`, `PITCH_WIDTH_M=68`)
- [ ] T015 [P] Write failing `frontend/tests/unit/ReplayController.test.ts` using a 5-frame fixture (t = 0,100,200,300,600 ms; `amber-06` invisible at t=200): starts `paused` at window start; `play()`+`tick(150)` → t=150; `sample(50)` lerps `blue-09` halfway between frames 0 and 100; `sample(150)` omits `amber-06` (invisible at 200) and `sample(200)` omits it; `sample(450)` returns `gap=true` and no players (300→600 gap > 150 ms); `sample(300)` exact frame returns supplied positions unchanged; `seek(-500)` → start, `seek(99999)` → end; `setSpeed(0.5)` + `tick(200)` → +100 ms; `setSpeed(2 as never)` throws `RangeError`; reaching end with `loop=false` → `ended`, then `play()` restarts at start; with `loop=true`, `tick` past end wraps to `start + overflow`; `subscribe` fires on status changes and at most once per 100 ms of cursor time
- [ ] T016 [P] Write failing `frontend/tests/unit/frameSource.test.ts`: `liveFrameSource(get)` returns `null` when `get()` is null; maps visible players only, team from ID prefix, ball `null` when invisible, `heightM` default 0.11
- [ ] T017 Implement `frontend/src/scene/frameSource.ts` and `frontend/src/replay/ReplayController.ts` per plan signatures (binary search for bracketing frames; no interpolation across invisibility or gaps > `maxGapMs`). Run T015–T016 → green

**Checkpoint**: contracts green and regenerated; window, IDs, interpolation proven by tests.

---

## Phase 3: User Story 1 — Ask "Why?" and watch the hero replay (P1) 🎯 MVP

**Goal**: card → Why → server scene → 3D replay with highlight, path and animated channel band.

**Independent Test**: `npx playwright test why-mode --grep "replay"` with scripted agents; `test_scene_golden.py`.

### Backend

- [ ] T018 [US1] Write failing `backend/tests/unit/test_scene.py` with a hand-built 12-frame mini fixture (metadata, frames, a pass event, `channel`, `defender_follow`, `off_ball_run`, `pressure` metrics): `highlight_blue_09` resolves with `team_id="blue"` and evidence = ok metrics whose subjects include blue-09; `path_amber_04` has two segments when amber-04 is invisible in frame 6, each point equal to the frame `pos_m`; `show_channel_0042` keyframes use `inputs.frame_ids[0]`/`[1]`, endpoints equal passer/receiver frame positions, `clearance_m` equals `clearance_before_m`/`clearance_at_pass_m` exactly, nearest defender is the visible opponent with minimal point-to-segment distance (tie → lowest ID) and `closest_point_m` is its projection; channel metric with components altered by +0.3 → `unresolved inconsistent_geometry`; `pressure_ring_blue_08` radius = max distance of the 3 nearest visible opponents rounded to 0.1, `score` = metric value; unknown player `highlight_blue_77` → `unknown_player`; missing metric → `metric_missing`; `status=unavailable` → `metric_unavailable`; `partial_tracking` true when any invisible entity; annotations sorted by ID; two calls produce identical `json.dumps(sort_keys=True)`; `default_annotations` returns `[highlight_blue_09, path_amber_04, show_channel_0042]` for pattern `space_creation`
- [ ] T019 [US1] Implement `build_scene` and `default_annotations` in `backend/src/tactistream/moments/scene.py` using `metrics/geometry.py` `distance` / `point_segment_distance` (add them there with tests in `backend/tests/unit/test_geometry.py` if 003 did not). Run T018 → green
- [ ] T020 [US1] Write failing `backend/tests/unit/test_scene_golden.py` (+ `--update-golden` option in `backend/tests/conftest.py`): simulate `space_creation` seed 42 (002 `simulate`), apply to `MatchState`, compute metrics, detect moments, take the `space_creation` moment, build the scene with `default_annotations`; assert (a) JSON equals `backend/tests/golden/scene_space_creation_42.json` byte-for-byte; (b) channel keyframe endpoints equal passer/receiver positions in the two referenced frames; (c) both `clearance_m` equal the channel metric components; (d) every path point equals the frame position of that player; (e) window length within 8000–12000 ms
- [ ] T021 [US1] Generate `backend/tests/golden/scene_space_creation_42.json` with `--update-golden`, review it by eye against the frames (runner Blue 9, Amber defender, Blue 8 → Blue 11 channel), commit; rerun 3× to confirm byte-identical (SC-002)
- [ ] T022 [US1] Write failing `backend/tests/integration/test_replay_api.py` (httpx ASGI + FakeClock, `TACTISTREAM_AGENTS=scripted`): create session `{"scenario":"space_creation","seed":42}`, play, advance until an `insight` for the `space_creation` moment is released; `GET /api/matches/{id}/replay/{moment_id}` → 200; frames contiguous at 100 ms covering the window inclusively; all frames/events have `session_clock_ms ≤` current clock; events include the channel metric's anchor pass; `scene.annotation_source == "insight"` and annotation IDs equal the union of the bundle variants' `render.annotations`; second request served from cache (spy on `build_scene` called once); unknown moment → 404 `moment_not_found`; unknown match → 404 `match_not_found`; `Accept-Encoding: gzip` → `content-encoding: gzip`; 20 requests with cache disabled → record p95 server time (assert ≤ 300 ms, print value)
- [ ] T023 [US1] Implement `backend/src/tactistream/api/replay.py` (`ReplayService.get(moment_id)`: look up moment as of clock, frames/events via `MatchSnapshot`, metrics via `EvidenceIndex`, annotation IDs from latest released bundle or defaults, `build_scene`, LRU cache keyed `(moment_id, state_version, sha1(ids))`, cleared on reset)
- [ ] T024 [US1] Implement `backend/src/tactistream/api/routes_replay.py` and register it plus `GZipMiddleware(minimum_size=1000)` in `backend/src/tactistream/api/app.py`. Run T022 → green; record p95 in `specs/005-why-mode-replay/research.md` R7

### Frontend

- [ ] T025 [P] [US1] Write failing `frontend/tests/unit/client.replay.test.ts` and `frontend/tests/unit/matchStore.replay.test.ts`: `getReplay` resolves `{ok:true, replay}` on 200, `{ok:false, unavailable}` on 409, throws `ApiError` on 404; `openReplay(m)` sets `surface={kind:"replay",momentId:m}` and `replays[m]` `loading` → `ready`; second `openReplay(m)` does not refetch; `closeReplay()` → `surface.kind="live"`; snapshot after reset clears `replays` and returns to live
- [ ] T026 [P] [US1] Implement `getReplay` in `frontend/src/api/client.ts` and `surface`, `replays`, `openReplay`, `closeReplay` in `frontend/src/store/matchStore.ts`. Run T025 → green
- [ ] T027 [P] [US1] Write failing `frontend/tests/unit/annotationGeometry.test.ts` and `cameraPoses.test.ts` with the `contracts/examples/scene_annotations.json` fixture: `channelBandAt` invisible before keyframe 0, half-width 1.9 at keyframe 0, 3.6 at the midpoint time, 5.3 at keyframe 1 and for 2 s after, invisible afterwards; endpoints interpolate linearly; `trailUntil` returns only points with `t ≤ tMs` per segment plus the sampled head; `pressureRingAt` visible only within ±1500 ms of `t_ms`; `cameraPose("broadcast", null)` → position `(0,38,62)`; `follow_runner` with focus `(10,20)` offsets from `toWorld([10,20])`
- [ ] T028 [P] [US1] Implement `frontend/src/scene/annotationGeometry.ts` and `frontend/src/scene/cameraPoses.ts`. Run T027 → green
- [ ] T029 [US1] Write failing `frontend/tests/unit/Players.test.tsx` and `PitchScene.test.tsx` with `@react-three/test-renderer`: given a `SampledFrame` with 11 Blue visible, 10 Amber visible, 1 Amber invisible → Blue instanced mesh `count=11`, Amber `count=10`; Blue and Amber geometries differ (disc vs diamond); 21 text labels showing shirt numbers; ball mesh absent when `ball=null`; pitch plane is 105 × 68 and centre-circle radius 9.15
- [ ] T030 [US1] Implement `frontend/src/scene/PitchScene.tsx` (Canvas, lights, pitch plane + markings, `FrameSource` driven `useFrame` loop writing instance matrices via refs), `Players.tsx`, `Ball.tsx`. Run T029 → green
- [ ] T031 [US1] Write failing `frontend/tests/unit/Annotations.test.tsx` (test-renderer): with the example scene at `t = keyframes[1].t_ms` renders one highlight ring at Blue 9's sampled position, one trail line whose last point equals the sampled defender position, a channel band whose scale equals `2 × 5.3` across the segment, and a label text `"1.9 m → 5.3 m"`; annotations not listed in the `visibleIds` prop are not rendered; unresolved annotations are never rendered
- [ ] T032 [US1] Implement `frontend/src/scene/Annotations.tsx` (props `scene`, `visibleIds`, `source`) and `frontend/src/scene/CameraRig.tsx` (presets via `cameraPose`, damped transition ≤ 600 ms). Run T031 → green
- [ ] T033 [P] [US1] Write failing `frontend/tests/unit/WhyButton.test.tsx`: renders only when the store has the packet's `moment_id`; click and Enter call `openReplay(momentId)`; accessible name "Why?" (en) / "क्यों?" (hi); `InsightCard` container has `aria-live="polite"`
- [ ] T034 [P] [US1] Implement `frontend/src/components/WhyButton.tsx`, add it and the `aria-live` region to `frontend/src/components/InsightCard.tsx`, add chrome strings (`why`, `tactical_replay`, `back_to_live`, `speed`, `loop`, `camera_broadcast`, `camera_top_down`, `camera_follow_runner`, `partial_tracking`, `insufficient_tracking`) to `frontend/src/i18n/en.ts` and draft `hi.ts`. Run T033 → green
- [ ] T035 [US1] Write failing `frontend/tests/unit/ReplayView.test.tsx` and `SceneDescription.test.tsx` (mock `../scene/PitchScene` to capture props): loading state → spinner with label; ready → `data-testid="replay-view"`, "Tactical replay" heading, Synthetic badge, `PitchScene` receives a `ReplayController` source and `visibleIds` = active variant's `render.annotations`; play/pause/0.5×/loop/camera buttons update the controller cursor; scrubber `aria-valuemin/max` = window; Escape and "Back to live" call `closeReplay` and return focus to the Why button; SceneDescription lists "Highlighted: Blue 9", "Path: Amber 4", "Channel Blue 8 → Blue 11: 1.9 m → 5.3 m"
- [ ] T036 [US1] Implement `frontend/src/components/ReplayView.tsx`, `frontend/src/scene/SceneDescription.tsx`, and extend `frontend/src/components/PlaybackControls.tsx` with optional `speed`/`onSpeed`/`loop`/`onLoop` props (match controls keep current behaviour). Run T035 → green
- [ ] T037 [US1] Write failing `frontend/tests/unit/MainSurface.test.tsx` (mock PitchScene): `surface.kind="live"` renders PitchScene with a live source and no replay; `replay` renders `ReplayView`; incoming `insight` with higher priority during replay does not change `surface` and sets a "New" badge flag in the store
- [ ] T038 [US1] Implement `frontend/src/components/MainSurface.tsx` and lay out `frontend/src/App.tsx` (top bar, main surface ~70% width, side panel with card, bottom timeline slot). Run T037 → green
- [ ] T039 [US1] Write `frontend/tests/e2e/why-mode.spec.ts` (replay part): Start demo match → expect card "Space opened before the shot" within 60 s of session start → click Why? → expect `[data-testid="replay-view"]` and a `canvas` within 1.5 s (measure with `performance.now()`), replay status `playing`, scene description contains "Blue 9"; Escape returns to live. Run with `--repeat-each=5`

**Checkpoint**: Hero Why replay demonstrable locally (US1 independent test passes).

---

## Phase 4: User Story 2 — Inspect the evidence behind the explanation (P1)

**Goal**: evidence drawer with definitions, windows, components, coordinates, source events and status labels.

**Independent Test**: `EvidenceDrawer.replay.test.tsx` + Evidence step in `why-mode.spec.ts`.

- [ ] T040 [P] [US2] Write failing `backend/tests/unit/test_evidence_presentation.py` and extend `backend/tests/integration/test_evidence_api.py`: `GET …/evidence/metric-channel-0042?language=en` body has `presentation.definition` equal to catalog `metric_def.channel` (en), `limitation` equal to `limitation.channel`, `unit_label="m"`; `language=hi` returns the hi strings; event records have no `presentation`; `language=fr` → 422 `invalid_language`; every metric kind in the registry enum has `metric_title.*` and `metric_def.*` keys in both catalogs
- [ ] T041 [P] [US2] Add `metric_title.*`, `metric_def.*`, `limitation.*`, `unit.*`, `label.partial_tracking`, `label.verified_fact` keys (en final; hi draft marked for 006 review) to `backend/src/tactistream/narrative/catalog/{en,hi}.json` and the `?language=` + `presentation` extension to `backend/src/tactistream/api/routes_evidence.py`. Run T040 → green
- [ ] T042 [US2] Write failing `frontend/tests/unit/EvidenceDrawer.replay.test.tsx` (mock client): metric record shows title, definition, limitation, window `00:38.3 – 00:42.3`, value `3.4 m`, components `clearance_before_m 1.9 m` / `clearance_at_pass_m 5.3 m`, `definition_version`, frame count with first/last IDs, input event `evt-0042` as a button that navigates to the event record with a Back button; opened with a `scene` prop shows "Scene geometry" with passer/receiver/nearest-defender coordinates for both keyframes formatted `(x, y)` with 1 decimal identical to the payload; header shows "Interpretation" for `interpretation_supported` and none for `verified_fact`; records labelled "Verified fact"; drawer is a labelled dialog that traps focus and returns it on close
- [ ] T043 [US2] Extend `frontend/src/components/EvidenceDrawer.tsx` (record-kind sections, status header, scene geometry, in-drawer navigation) and `getEvidence(matchId, id, language)` in `frontend/src/api/client.ts`; open the drawer from both InsightCard and ReplayView (passing `scene`). Run T042 → green
- [ ] T044 [US2] Extend `frontend/tests/e2e/why-mode.spec.ts`: from the replay press Evidence → drawer contains text matching `/metric-channel-\d{4}/`, a value matching `/\d+\.\d m/`, the definition text, and the label "Interpretation"; Escape closes and focus returns. Run `--repeat-each=5` (SC-001)

**Checkpoint**: US1 + US2 = complete hero demo segment 0:00–0:43.

---

## Phase 5: User Story 3 — Honest degradation when tracking is missing (P2)

**Goal**: 409 with events + clear message; partial tracking drawn honestly.

**Independent Test**: `test_replay_insufficient.py` + `why-mode-insufficient.spec.ts`.

- [ ] T045 [P] [US3] Write failing `backend/tests/integration/test_replay_insufficient.py`: (a) 002 missing-data fixture moment → 409 body `error="insufficient_tracking"`, `detail` mentions coverage or metric, `moment.moment_id` matches, `events` non-empty and within window; (b) unit `assess_tracking`: coverage 0.59 → insufficient, 0.6 → ok; ok coverage but `metric-channel-*` `unavailable/insufficient_tracking` while `show_channel_*` requested → insufficient; same metric unavailable but not requested → ok; (c) partial fixture (hero frames with `amber-06` invisible for 10 frames) → 200, `partial_tracking=true`; (d) `path_amber_06` when amber-06 invisible for the whole window → `unresolved player_not_visible`
- [ ] T046 [US3] Implement `assess_tracking` in `backend/src/tactistream/moments/scene.py` and the 409 path (`ReplayInsufficientTracking` → JSON body) in `backend/src/tactistream/api/replay.py` / `routes_replay.py`. Run T045 → green
- [ ] T047 [P] [US3] Write failing tests: `frontend/tests/unit/ReplayView.test.tsx` — `insufficient` state renders "Insufficient tracking for this explanation" (en) / hi string, the ordinary event card(s) for `events` via `EventList`, no PitchScene; `partial_tracking=true` renders "Partial tracking" badge; `frontend/tests/unit/ReplayController.test.ts` — over a 10-frame invisibility window `amber-06` absent from every sample strictly inside the gap (SC-003)
- [ ] T048 [US3] Implement the insufficient and partial-tracking states in `frontend/src/components/ReplayView.tsx` (reusing `EventList` and `SourceBadge`). Run T047 → green
- [ ] T049 [US3] Write `frontend/tests/e2e/why-mode-insufficient.spec.ts`: start the missing-data scenario → ordinary card visible → Why? → message "Insufficient tracking for this explanation" + event card, no canvas; Evidence still opens (SC-004)

**Checkpoint**: degradation proven end to end.

---

## Phase 6: User Story 4 — Two more patterns replay correctly (P2)

**Goal**: `press_turnover` and `switch_escape` replays with pattern annotations.

**Independent Test**: `test_replay_patterns.py` + `why-mode-patterns.spec.ts`.

- [ ] T050 [P] [US4] Write failing `backend/tests/integration/test_replay_patterns.py` parametrized over (`press_turnover`, `pressure_ring`+`highlight`+`path`) and (`switch_escape`, `pressure_ring`+`highlight`+`path`), seed 42, both `annotation_source` paths (scripted insight and defaults by disabling agents): 200; expected kinds resolved; press: `highlight` player = actor of the first tackle/interception/ball_recovery in window, ring `radius_m` = max distance of up to 3 nearest visible opponents at the anchor frame; switch: ring carrier = switch passer, highlight/path player = its recipient; every coordinate in the scene equals a frame position or is derived from frame positions (re-derive in test)
- [ ] T051 [US4] Complete `default_annotations` pattern rules and pressure-ring metric selection in `backend/src/tactistream/moments/scene.py` until T050 passes; add golden files `backend/tests/golden/scene_press_turnover_42.json` and `scene_switch_escape_42.json` to `test_scene_golden.py`
- [ ] T052 [US4] Write `frontend/tests/e2e/why-mode-patterns.spec.ts`: for each scenario start session via `POST /api/sessions`, open the app on that match, wait for the pattern card, Why? → replay visible, scene description lists the expected annotation kinds, 0 console errors (SC-005)

**Checkpoint**: Scope-table completion condition "one polished replay plus two additional event patterns" met.

---

## Phase 7: User Story 5 — Live 3D pitch, keyboard timeline, comfortable motion (P3)

**Goal**: shared live/replay pitch, keyboard timeline, reduced motion, FPS tooling, accessibility.

**Independent Test**: `Timeline.test.tsx`, `a11y.spec.ts`, `capture-fps.mjs` output.

- [ ] T053 [P] [US5] Write failing `frontend/tests/unit/Timeline.test.tsx`: renders one marker button per store moment positioned by trigger time; slider `role="slider"` with `aria-valuetext` `mm:ss`; live mode → ArrowRight / ArrowLeft call `control({action:"seek", to_ms: clock ± 1000})`, Home → 0, End → current session clock; replay mode → same keys call `controller.seek` within window and show event ticks; Enter on focused marker calls `openReplay(momentId)`; "New" badge shown when the store flag is set
- [ ] T054 [US5] Implement `frontend/src/components/Timeline.tsx` and mount it in `frontend/src/App.tsx`. Run T053 → green
- [ ] T055 [P] [US5] Write failing tests for reduced motion in `frontend/tests/unit/ReplayView.test.tsx` and `Annotations.test.tsx`: with `prefers-reduced-motion: reduce` replay opens `paused` at window start, camera preset change sets pose immediately (no transition), highlight ring has no pulse animation; default motion → autoplay `playing`
- [ ] T056 [US5] Implement `frontend/src/scene/useReducedMotion.ts` and apply it in `ReplayView.tsx`, `CameraRig.tsx`, `Annotations.tsx`. Run T055 → green
- [ ] T057 [P] [US5] Write failing `frontend/tests/unit/FpsOverlay.test.tsx` then implement `frontend/src/scene/FpsOverlay.tsx`: hidden unless `DEV` or `?fps=1`; given deltas of 16.7 ms shows `60 fps` (rolling 1 s mean); appends `{t, fps}` to `window.__tactistreamFps`
- [ ] T058 [US5] Write `frontend/scripts/capture-fps.mjs` (args `--url --scenario --seed --seconds --machine-label --out`): start a session via the UI, open Why on the first pattern card, read `window.__tactistreamFps` for N s, write `eval/results/fps/fps-<ISO>.json` with `fps_mean`, `fps_p5`, `fps_min`, `samples`, `duration_ms`, `user_agent`, `viewport`, `gpu`, `machine_label`; add npm script `perf:fps`; smoke it once against `make dev` and check the JSON parses (008 reuses this script)
- [ ] T059 [US5] Write failing-then-passing WebGL fallback test in `frontend/tests/unit/MainSurface.test.tsx` (mock `WebGL2RenderingContext` absent → `EventList` + notice "3D replay unavailable in this browser") and implement the guard in `frontend/src/components/MainSurface.tsx`
- [ ] T060 [US5] Write `frontend/tests/e2e/a11y.spec.ts`: axe (`@axe-core/playwright`) on live and replay views → 0 serious/critical violations; keyboard-only flow: Tab to card → Why? (Enter) → Space pause → ArrowRight seek → Escape back → Tab to timeline marker → Enter opens replay (SC-008); fix violations found

**Checkpoint**: All five stories independently demonstrable.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T061 Run `npm run perf:fps -- --seconds 20 --machine-label dev` on the development machine against the hero replay; record mean/p5 fps, GPU, browser, duration in `specs/005-why-mode-replay/research.md` R7 (labelled development figure, SC-006)
- [ ] T062 [P] Document replay limitations (linear interpolation between 10 Hz samples, 0.6 coverage floor, 150 ms gap rule, simplified pitch, server-resolved annotations) in `docs/limitations.md` (create section "Why Mode replay")
- [ ] T063 [P] Run `specs/005-why-mode-replay/quickstart.md` on a fresh clone and fix gaps
- [ ] T064 19 Oct stop-rule check: run the full backend suite and `npx playwright test why-mode why-mode-insufficient why-mode-patterns a11y`; if any US1–US4 scenario fails, apply the roadmap stop rule (upload/screen-share/forecast stay cut; remaining time goes to Why Mode) and note it in the PR
- [ ] T065 Update the 005 row in `specs/README.md` feature table: mark the exit condition met with the date (and note any stop-rule action from T064)

---

## Dependencies & Execution Order

- Setup (T001–T004) → Foundational (T005–T017) → US1 (T018–T039) → US2 (T040–T044) → US3 (T045–T049) and US4
  (T050–T052) in parallel → US5 (T053–T060) → Polish (T061–T065).
- Within US1: backend T018 → T019 → T020/T021 → T022 → T023 → T024; frontend T025–T028 can start after T008 and run in
  parallel with the backend; T029 → T030 → T031 → T032; T033/T034 parallel; T035 → T036 → T037 → T038; T039 needs
  T024 and T038.
- US2 backend (T040–T041) only needs T024; frontend T042–T043 need T036.
- US3 T045–T046 need T023; T047–T048 need T036.
- US4 needs T019 and 002's `press_turnover`/`switch_escape` scenarios; 004 scripted outputs for those patterns are
  optional (defaults cover them).
- US5 T053–T056 need T038; T058 needs T057 and T039.

## Parallel Example

```text
18 Oct morning:   T018–T019 (scene.py)  ||  T025–T028 (client/store/geometry)  ||  T013–T017 if not done
18 Oct afternoon: T020–T024 (golden + endpoint)  ||  T029–T034 (R3F components, Why button)
19 Oct morning:   T040–T044 (evidence)  ||  T045–T049 (insufficient)  ||  T050–T052 (patterns)
19 Oct afternoon: T053–T060 (timeline, a11y, fps), T061–T065
```

## Implementation Strategy

MVP = Phases 1–4 (hero replay + evidence) by end of 18 Oct; patterns and degradation on the morning of 19 Oct; US5
is the cut line if the 19 Oct stop rule bites (keep the live event list as the main surface, keep Timeline markers
without seek).
