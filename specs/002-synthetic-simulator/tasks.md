---
description: "Task list for 002 synthetic simulator"
---

# Tasks: Synthetic Simulator

**Input**: `specs/002-synthetic-simulator/` (spec, plan, research, data-model, contracts, quickstart)

**Prerequisites**: 001 merged (contracts, `FeedReplayer`, `Clock`/`FakeClock`, `InMemoryBus`, `MatchSession`, `SessionRegistry`, `WsHub`, frontend shell).

**Tests**: REQUIRED (constitution V). Each implementation task is preceded by a test task that must fail first for the stated reason.

**Format**: `[ID] [P?] [Story] Description` — `[P]` = parallelizable (different files, no unmet dependency).

## Phase 1: Setup

- [x] T001 Update `backend/pyproject.toml`: console script `tactistream-sim = tactistream.simulator.cli:app`; dev dependency `hypothesis`; pytest marker `slow` excluded by default (`addopts = -m "not live and not slow"`); add `data/generated/` to `.gitignore`; add `TACTISTREAM_MAX_SESSIONS=8` to `.env.example`; add Makefile target `sim-hero` (`cd backend && uv run tactistream-sim generate --scenario space_creation --seed 42 --variant A --split dev --out ../data/generated/hero --force`)
- [x] T002 [P] Create package skeletons with empty modules and docstrings: `backend/src/tactistream/simulator/{__init__,config,roster,possession,kinematics,script,program,manifest,engine,validate,io,cli}.py`, `backend/src/tactistream/simulator/scenarios/__init__.py`, `backend/tests/unit/simulator/__init__.py`, `backend/tests/simulator/__init__.py`, `backend/tests/golden/simulator_hashes.json` containing `{}`

**Checkpoint**: `make lint && make test` pass (empty suites).

---

## Phase 2: Foundational (blocks all stories)

### Config, roster, possession

- [x] T003 [P] Write failing `backend/tests/unit/simulator/test_config.py`: every row of data-model.md "Configuration" rules raises `ConfigError` with the listed `code` (dev+10000 → `eval_seed_requires_eval_split`; dev+"D" → `eval_variant_requires_eval_split`; eval+42 → `dev_seed_in_eval_split`; eval+"A" → `invalid_variant`; 0 and 2**31 → `invalid_seed`); `SimulationConfig(42,"space_creation").match_id == "demo-blue-amber-001"`; `SimulationConfig(42,"demo_match").match_id == "demo-blue-amber-002"`; `SimulationConfig(43,"space_creation").match_id` matches `^sim-[0-9a-f]{10}$` and contains neither `space` nor `43`; same config → same `canonical_json()`; `VARIANTS["D"]` has focus `blue`, period 2, y-mirror True, build-up 4, time scale 0.90
- [x] T004 [P] Implement `backend/src/tactistream/simulator/config.py` (`SimulationConfig`, `VariantSpec`, `VARIANTS`, `ConfigError`, `HERO_MATCH_IDS`, seed/variant constants). Run T003 → green
- [x] T005 [P] Write failing `backend/tests/unit/simulator/test_roster.py`: `build_metadata(SimulationConfig(42,"space_creation"), periods=[P1])` equals `contracts/examples/match_metadata.json` exactly (match_id `demo-blue-amber-001`, same teams, players, roles, colours, display names, period 1 only, `source.seed = 42`); metadata validates via `schema_registry.validate("match_metadata", …)`; `slots("blue","in_possession",1)["blue-01"] == (6.0, 34.0)` and with attack dir −1 → `(99.0, 34.0)`; each team has 11 slots
- [x] T006 [P] Implement `backend/src/tactistream/simulator/roster.py` (`build_metadata`, `FORMATION_433`, `slots`). Run T005 → green
- [x] T007 [P] Write failing `backend/tests/unit/simulator/test_possession.py`: one parametrized case per row of the legal-transition table in data-model.md asserting the resulting `PossessionState`; illegal cases raise `IllegalTransition`: `carry` by a player not in control; `interception` by the last-touch team; `pressure` by the possessing team or from 4.0 m; `tackle` from 2.0 m; any event after `period_end`; `kickoff` at (50, 34); restart `pass` by the team that put the ball out; `check_sequence([kickoff, shot])` returns one `ValidationIssue(code="illegal_transition", record_id="evt-0002")`
- [x] T008 [P] Implement `backend/src/tactistream/simulator/possession.py` (`Phase`, `PossessionState`, `TransitionRule`, `LEGAL_TRANSITIONS`, `transition`, `check_sequence`, `is_turnover(prev_state, event)`). Run T007 → green

### Kinematics and test helpers

- [x] T009 [P] Write failing `backend/tests/unit/simulator/test_kinematics.py`: `spline_track` passes exactly through every keyframe at its time; `check_bounds` raises `KinematicsError` (with `player_id`, `t_ms`) for 15 m in 1.0 s (speed) and for a 0 → 3 m/s change within 100 ms (30 m/s² accel); hypothesis (`derandomize=True`, 200 examples) random target sequences into `follow_track(max_speed=9.5, max_accel=6.0)` never exceed either bound; `ball_track`: controlled ball within 0.30 ± 0.01 m of carrier, pass midpoint equals the average of `start_m` and `end_m` ± 0.01 m, ball invisible during a dead-ball phase until exactly 1000 ms before the restart; `plan_reposition` returns duration ≥ 3000 ms, a multiple of 100, and tracks that satisfy 7.0 m/s and 4.0 m/s²
- [x] T010 [P] Implement `backend/src/tactistream/simulator/kinematics.py` (constants, `Keyframe`, `KinematicsError`, `spline_track`, `follow_track`, `check_bounds`, `BallPhase`, `ball_track`, `plan_reposition`). Run T009 → green
- [x] T011 [P] Write failing `backend/tests/unit/simulator/test_intent_helpers.py` for test-only helpers in `backend/tests/simulator/intent.py`: `pressure_proxy([1.0, 2.0, 3.0]) == 47.4` (1 dp); `pressure_proxy([5.0, 7.5, 10.0]) == 6.8`; `lane_clearance(passer=(58,32), receiver=(69,27.5), defenders=[(67.5,30.0)])` ≈ 2.4 m (±0.1, design value from data-model hero table); `angle_to_axis_deg((9,10), attack_dir=1)` ≈ 48.0; `normalize((10,20), -1) == (95,48)`
- [x] T012 [P] Implement `backend/tests/simulator/intent.py` (`normalize`, `lane_clearance`, `nearest_opponent_distance`, `pressure_proxy`, `angle_to_axis_deg`, `best_run(frames, player_ids, window)`, and one `check_<family>(output, label_window) -> list[str]` per row of data-model.md "Scenario intent checks"; empty list = pass). Run T011 → green

### Validation, manifest, files, builder

- [x] T013 Write failing `backend/tests/unit/simulator/test_validate.py` using a hand-built 2 s output factory in `backend/tests/unit/simulator/factories.py` (metadata, kickoff, carry, 21 frames, all valid → `report.ok`, `unchecked == 0`); single mutations yield exactly one issue each: player jumps 1.2 m in one frame → `speed_exceeded`; 0 → 7 m/s within 200 ms → `accel_exceeded`; controlled ball 0.8 m from carrier → `ball_detached`; pass at 30 m/s → `pass_ball_speed`; event `start_m` 1.5 m from actor → `event_coord_mismatch`; kickoff then `carry` by an opponent → `illegal_transition`; frame index 7 removed → `frame_gap`; `amber-06` absent from one frame → `roster_incomplete`; Blue shot toward x = 0 in period 1 → `attack_direction_inconsistent`; invisible player reappearing 12 m away after 1.0 s → `speed_exceeded` (gap mean); invisible actor at an event → no issue and `unchecked == 1`; invisible player with `pos_m` → `schema_invalid`
- [x] T014 Implement `backend/src/tactistream/simulator/validate.py` (`IssueCode`, `ValidationIssue`, `ValidationReport`, `validate_output`, `validate_envelopes`) with the tolerances in data-model.md. Run T013 → green
- [x] T015 [P] Write failing `backend/tests/unit/simulator/test_io.py`: `canonical_line({"b":1,"a":[1.0,2]})` == `b'{"a":[1.0,2],"b":1}\n'`; `to_envelopes` puts metadata first, then ascending `session_clock_ms`, events before frames at equal time; `published_ms == 1792000000000 + session_clock_ms`; `write_output` into a non-empty dir raises unless `force=True`; an exception during writing leaves no `feed.jsonl` in `out_dir`; the written feed loads with `transport.fixtures.load_fixture` into the same envelope list; `WrittenFiles.feed_sha256` equals `hashlib.sha256(feed bytes)`
- [x] T016 [P] Implement `backend/src/tactistream/simulator/manifest.py` (`SegmentLabel`, `TrackingGap`, `GenerationManifest`, `to_canonical_json()`)
- [x] T017 Implement `backend/src/tactistream/simulator/io.py` (`BASE_PUBLISHED_EPOCH_MS`, `canonical_line`, `to_envelopes`, `write_output`, `WrittenFiles`). Run T015 → green
- [x] T018 Write failing `backend/tests/unit/simulator/test_script.py`: `SegmentBuilder.beat` raises `IllegalTransition` for an illegal beat; scene transform with focus attacking −x maps nominal (60, 40) → (45, 28), and with y-mirror as well → (45, 40); with a fixed RNG, jitter moves keyframes ≤ 0.5 m per axis and beats ≤ 200 ms, keeps beat order and ≥ 300 ms gaps, and quantizes to 100 ms; `gap(["blue-09"], 1000, 2000)` makes frames 10–20 invisible for `blue-09` only; `build()` returns `end_state.phase == DEAD` after an `out_of_play` beat
- [x] T019 Implement `backend/src/tactistream/simulator/script.py` (`Kickoff`, `Restart`, `SegmentBuilder`, `SegmentResult`, scene transform, jitter, frame sampling at 100 ms, follower assignment for non-scripted players). Run T018 → green

**Checkpoint**: Foundations green — state machine, kinematics, validation, files and builder are proven without any scenario.

---

## Phase 3: User Story 1 — Hero sequence, deterministic (P1) 🎯 MVP

**Goal**: `space_creation` seed 42 variant A → valid, byte-identical feed + isolated manifest via CLI.

**Independent Test**: `uv run pytest tests/unit/simulator/test_space_creation.py tests/unit/simulator/test_determinism.py tests/unit/simulator/test_cli.py tests/unit/simulator/test_manifest_isolation.py`.

- [x] T020 [US1] Write failing `backend/tests/unit/simulator/test_space_creation.py`: `simulate(SimulationConfig(42,"space_creation"))` has exactly 9 events with types `[kickoff, carry, pass, pass, pass, carry, shot, out_of_play, period_end]`; `evt-0005` is a complete pass `blue-08` → `blue-11`; `evt-0007` is a `shot` by `blue-11` with outcome in {on_target, off_target, blocked}; `len(frames) == duration_ms // 100 + 1`; every frame lists all 22 player IDs; `validate_output(...).ok`; `intent.check_space_creation(...) == []`; and for seeds 1–20 × variants A, B, C the report is ok and the intent check passes
- [x] T021 [US1] Implement `backend/src/tactistream/simulator/scenarios/space_creation.py` using the hero beats in data-model.md (build-up count from `VariantSpec`, key-actor sets primary/alternate) and register it in `backend/src/tactistream/simulator/scenarios/__init__.py` (`FAMILIES`). Run T020 → green
- [x] T022 [US1] Write failing `backend/tests/unit/simulator/test_determinism.py`: `simulate(cfg)` twice → equal `to_envelopes` bytes and equal manifest JSON; `space_creation/42/A` feed SHA-256 equals `backend/tests/golden/simulator_hashes.json["space_creation/42/A"]` (when `TACTISTREAM_UPDATE_GOLDEN=1`, the test writes the hash instead and is skipped); seed 43 produces a different hash; `metadata.source == {"kind":"synthetic","generator_version":"0.1.0","seed":42}` and every event and frame carries the same `source`
- [x] T023 [US1] Implement `backend/src/tactistream/simulator/engine.py` (`SimulationOutput`, `simulate`: family dispatch, contract models, manifest with `feed_sha256`, `event_count`, `frame_count`, `duration_ms`). Run T022 once with `TACTISTREAM_UPDATE_GOLDEN=1`, commit `simulator_hashes.json`, then rerun → green
- [x] T024 [P] [US1] Write failing `backend/tests/unit/simulator/test_manifest_isolation.py`: AST scan of every `.py` under `backend/src/tactistream/{state,metrics,moments,agents,narrative,api,transport,recap,history,storage,telemetry}` finds no import of `tactistream.simulator.manifest` or name `GenerationManifest`; serialized `to_envelopes(hero)` contains none of the keys `scenario`, `variant`, `segments`, `expected_pattern`, `intended_explanation`, `negative_of`; hero manifest has one segment with `expected_pattern == "space_creation"`, `key_players["runner"] == "blue-09"`, `key_players["follower"] == "amber-04"`, `key_event_ids == {"forward_pass": "evt-0005", "shot": "evt-0007"}`
- [x] T025 [US1] Populate `SegmentLabel` in `backend/src/tactistream/simulator/scenarios/space_creation.py` (key players, key events, intended explanation "Blue 9's diagonal run draws Amber 4; the Blue 8 → Blue 11 lane widens; forward pass, then shot.") until T024 is green
- [ ] T026 [P] [US1] Write failing `backend/tests/unit/simulator/test_cli.py` (typer `CliRunner`, tmp dirs): `generate --scenario space_creation --seed 42 --variant A --split dev --out D` exits 0, prints `match_id=demo-blue-amber-001 events=9` and a `feed_sha256=` line equal to the golden; `D/feed.jsonl` and `D/manifest.json` exist; rerun into the same non-empty `D` exits 2 with `error:`; with `--force` exits 0; `--scenario nope` exits 2 listing valid names; `list` exits 0 and prints 8 scenario rows; no output contains `Traceback`
- [ ] T027 [US1] Implement `backend/src/tactistream/simulator/cli.py` (`generate`, `list`; `ConfigError` → exit 2; `KinematicsError`/`IllegalTransition`/validation issues → exit 3 with `code record_id detail` lines). Run T026 → green; `make sim-hero` works

**Checkpoint**: US1 demonstrable — the hero feed exists, is valid, deterministic and label-free.

---

## Phase 4: User Story 2 — Replay any scenario and seed (P1)

**Goal**: sessions from (scenario, seed, variant); speed 0.5/1/2; seek; New seed in the UI; skeleton unchanged.

**Independent Test**: `uv run pytest tests/unit/test_replayer_speed_seek.py tests/integration/test_sim_sessions.py tests/integration/test_sim_seek.py` and `npx playwright test simulator.spec.ts`.

### Backend

- [ ] T028 [US2] Write failing `backend/tests/unit/test_replayer_speed_seek.py` (FakeClock + InMemoryBus, hero envelopes): at speed 2.0 the forward pass (`evt-0005`, session time `t5`) is published when the clock reaches `t5 / 2`, not before; switching 1.0 → 2.0 at clock 3000 keeps `session_clock_ms == 3000` at the switch, then advances 200 ms per 100 ms; `set_speed(1.5)` raises `ValueError`; `seek(8000)` from 2000 returns `SeekResult(rewound=False, published=<count of records in (2000, 8000]>, last_record_id="frm-000080")`; `seek(1000)` from 8000 calls `on_rewind` once, republishes metadata first and returns `rewound=True`; `seek(10**7)` sets state `ended`; published envelopes carry `published_ms` from an injected `wall_ms` stub returning 1800000000000
- [ ] T029 [US2] Extend `backend/src/tactistream/transport/replayer.py` (`ALLOWED_SPEEDS`, `SeekResult`, `wall_ms`, `on_rewind`, `duration_ms`, `set_speed`, `seek`) without changing 001 behaviour; 001 `test_replayer.py` stays green. Run T028 → green
- [ ] T030 [P] [US2] Write failing `backend/tests/unit/test_api_scenarios.py`: `list_scenarios()` returns 9 entries in the order of contracts/api-delta.md, `skeleton.variants == ("A",)`, simulator scenarios list `("A","B","C")`, all `default_seed == 42`; `load_scenario_envelopes("space_creation", 42, "A")` twice calls `simulate` once (monkeypatched counter) and returns envelopes whose first is metadata with `match_id == "demo-blue-amber-001"`; `load_scenario_envelopes("skeleton", 42, "A")` returns the 001 fixture; seed 10000 → `ConfigError("eval_seed_requires_eval_split")`
- [ ] T031 [US2] Implement `backend/src/tactistream/api/scenarios.py` (`ScenarioInfo`, `list_scenarios`, `load_scenario_envelopes` with `functools.lru_cache(maxsize=8)` and mandatory `validate_output`). Run T030 → green
- [ ] T032 [US2] Write failing `backend/tests/integration/test_sim_sessions.py` (httpx ASGI + FakeClock): `GET /api/scenarios` 200 with 9 items; `POST /api/sessions {"scenario":"space_creation","seed":42}` → 200 `match_id="demo-blue-amber-001"`, `variant="A"`, `shared=false`; same POST again → same `session_id`, `shared=true`; `{"scenario":"space_creation","seed":10000}` → 422 `eval_split_not_served`; `{"scenario":"space_creation","variant":"D"}` → 422 `eval_split_not_served`; `{"scenario":"skeleton","seed":7}` → 422 `invalid_seed`; `{"scenario":"nope"}` → 422 `invalid_scenario`; WS snapshot `playback.seed == 42`; `play` then advance clock past `t5` → an `event` message with `event_id == "evt-0005"`; control `{"action":"speed","speed":2.0}` → `playback.speed == 2.0`; `{"action":"speed","speed":3}` → 422 `invalid_action`; with `max_sessions=2`, a third config evicts the viewer-less oldest session, and when both have WS viewers → 429 `too_many_sessions`
- [ ] T033 [US2] Extend `backend/src/tactistream/api/routes_sessions.py` (request model `{scenario, seed=42, variant="A"}`, `GET /api/scenarios`, control `speed`/`seek`), `backend/src/tactistream/api/session.py` (`SessionRegistry.get_or_create`, LRU limit, `MatchSession.set_speed`) and `backend/src/tactistream/settings.py` (`max_sessions: int = 8`). Run T032 → green; 001 `test_session_flow.py` stays green
- [ ] T034 [US2] Write failing `backend/tests/integration/test_sim_seek.py` (`demo_match` seed 42): play to session 30000 ms, `seek` 12000 → state events are exactly the feed events with `session_clock_ms ≤ 12000`; the WS receives exactly one `snapshot` and zero `event`/`frame` messages between the control call and that snapshot; snapshot `session_clock_ms == 12000`; then `seek` 60000 → snapshot `events` count equals feed events ≤ 60000; `{"action":"seek","to_ms":-1}` → 422 `invalid_action`; skeleton session `reset` still yields the 001 card after replay (regression)
- [ ] T035 [US2] Implement `MatchSession.seek` bulk mode in `backend/src/tactistream/api/session.py` (rewind = 001 reset path; suppress per-record WS and fact cards while `bulk`; broadcast snapshot after `SeekResult.last_record_id` is applied). Run T034 → green

### Frontend

- [ ] T036 [P] [US2] Write failing `frontend/tests/unit/SessionControls.test.tsx`: renders options from a mocked `listScenarios` (first option "Demo match (scripted, ~4.5 min)"); seed field shows an error and disables Start for 0 and 10000; New seed with `crypto.getRandomValues` mocked to yield the current seed 42 first, then 777, calls `createSession({scenario, seed: 777, variant: "A"})`; choosing 2× calls `control({action: "speed", speed: 2})`; the speed radio group responds to ArrowRight/ArrowLeft; all controls have accessible names
- [ ] T037 [US2] Implement `frontend/src/api/client.ts` (`listScenarios`, `createSession(config)`, `control` with speed/seek), `frontend/src/store/matchStore.ts` (`session: {scenario, seed, variant, speed}`), `frontend/src/components/SessionControls.tsx`, chrome strings in `frontend/src/i18n/{en,hi}.ts`, and wire into `frontend/src/App.tsx` (Start uses the selected config; New seed reconnects the socket to the new `ws_path`). Run T036 → green; 001 unit tests stay green
- [ ] T038 [US2] Write `frontend/tests/e2e/simulator.spec.ts`: choose "Space creation (scripted)", seed 42, Start → event rows include a shot row within 16 s; select 2× → the session clock advances ≥ 3.5 s during 2.0 s wall time; New seed → seed field ≠ 42 and the event list restarts; choose "Skeleton fixture" → Start → card "Blue 8 played a forward pass to Blue 11 (13.1 m forward)." Run with `--repeat-each=5` (SC-004)

**Checkpoint**: Roadmap exit condition met — replay at 1× with pause/reset/new seed (+ speed, seek).

---

## Phase 5: User Story 3 — Scenario library with negatives and missing data (P2)

**Goal**: all seven families for dev variants A–C pass validation and intent checks.

**Independent Test**: `uv run pytest tests/unit/simulator/test_press_switch.py tests/unit/simulator/test_negatives_and_gap.py tests/unit/simulator/test_library_matrix.py`.

- [ ] T039 [P] [US3] Write failing `backend/tests/unit/simulator/test_press_switch.py`: for seeds 1–20 × A–C, `press_turnover` and `switch_escape` validate ok and pass `check_press_turnover` / `check_switch_escape`; `press_turnover` seed 42 A has ≥ 2 `pressure` events by Blue before an `interception` by `blue-10` with outcome `won`; `switch_escape` seed 42 A has a complete pass with |Δy| ≥ 34 m whose ball `height_m` peaks between 5.5 and 6.5 m
- [ ] T040 [P] [US3] Implement `backend/src/tactistream/simulator/scenarios/press_turnover.py` and register it. Run its part of T039 → green
- [ ] T041 [P] [US3] Implement `backend/src/tactistream/simulator/scenarios/switch_escape.py` and register it. Run T039 → green
- [ ] T042 [P] [US3] Write failing `backend/tests/unit/simulator/test_negatives_and_gap.py`: for seeds 1–20 × A–C, `run_no_channel`, `press_no_turnover` and `switch_closed` validate ok and pass their negative intent checks; `tracking_gap` seed 42 A: `blue-09`, `amber-03`, `amber-04`, `amber-05` are `visible=false` without `pos_m` in every frame of `[run_start − 1000, forward_pass + 500]`; the ball is visible in all of them; every other event/frame equals `space_creation` 42 A after normalizing `match_id` and `visible` flags; manifest `tracking_gaps == [TrackingGap(("amber-03","amber-04","amber-05","blue-09"), start, end)]`, `expected_pattern == "shot"`, `negative_of == "space_creation"`
- [ ] T043 [P] [US3] Implement `backend/src/tactistream/simulator/scenarios/run_no_channel.py` and register it
- [ ] T044 [P] [US3] Implement `backend/src/tactistream/simulator/scenarios/press_no_turnover.py` and register it
- [ ] T045 [P] [US3] Implement `backend/src/tactistream/simulator/scenarios/switch_closed.py` and register it (single closer; second-nearest opponent ≥ 8 m at reception)
- [ ] T046 [US3] Implement `backend/src/tactistream/simulator/scenarios/tracking_gap.py` (reuses the `space_creation` builder output, then `builder.gap(...)`; never re-simulates positions). Run T042 → green
- [ ] T047 [US3] Write `backend/tests/unit/simulator/test_library_matrix.py`: parametrized 7 families × A–C × seeds 1–5 → `validate_output(...).ok` and intent check `== []`; the same with seeds 1–100 under `@pytest.mark.slow`; per-run failure message prints `family/seed/variant` and the first 5 issues

**Checkpoint**: positives and negatives proven for dev variants; missing-data fixture ready for 003/005.

---

## Phase 6: User Story 4 — Demo match program (P2)

**Goal**: `demo_match` — 4–5 min, fixed segment order, feasible transitions, hero first.

**Independent Test**: `uv run pytest tests/unit/simulator/test_program.py`.

- [ ] T048 [US4] Write failing `backend/tests/unit/simulator/test_program.py`: a standalone 30 s `circulation` segment has no pass with |Δy| ≥ 30 m, no shot, no turnover, nearest opponent to the carrier ≥ 4 m at every on-ball event, no `intent.best_run` hit (≥ 8 m within ≤ 4 s, ≥ 4 m/s, 20–70°) for any attacking non-carrier, and ends with `out_of_play` handing the restart to the requested team; `demo_match` seed 42 A: `match_id == "demo-blue-amber-002"`, the last event is `period_end` at a session time in [240000, 300000], manifest segment scenarios equal the order in data-model.md "Demo match program", segment 1 events and frames equal `space_creation` 42 A (ignoring `match_id`), `validate_output(...).ok` (covers repositioning), the ball is invisible during every dead-ball interval until 1000 ms before each restart, each labelled segment passes its intent check within its manifest window, and the feed hash equals golden key `demo_match/42/A`; seeds 1–20 validate ok
- [ ] T049 [US4] Implement `backend/src/tactistream/simulator/scenarios/circulation.py` (params `duration_ms`, `end_restart_team`, `final: bool`)
- [ ] T050 [US4] Implement `backend/src/tactistream/simulator/program.py` (`Segment`, `MatchProgram.run`, `DEMO_MATCH`; per-segment `SeedSequence([seed, i])`; dead ball + `plan_reposition` + restart between segments) and route `scenario == "demo_match"` in `engine.simulate`; record the golden with `TACTISTREAM_UPDATE_GOLDEN=1`, commit, rerun T048 → green

**Checkpoint**: a judge can play one continuous match containing every pattern.

---

## Phase 7: User Story 5 — Held-out evaluation split (P3)

**Goal**: structural variants D–F behind split guards.

**Independent Test**: `uv run pytest tests/unit/simulator/test_variants_eval.py`.

- [ ] T051 [US5] Write failing `backend/tests/unit/simulator/test_variants_eval.py`: CLI `--split dev --seed 10000` → exit 2 `error: seed 10000 is reserved for split=eval`, `--split dev --variant D` → exit 2 `error: variant D is reserved for split=eval`, `--split eval --seed 42` → exit 2 `error: split=eval requires seed >= 10000`, and nothing is written in each case; `space_creation` eval 10000 D: metadata periods `[{1: blue 1, amber -1}, {2: blue -1, amber 1}]`, every record `period == 2`, runner `blue-10`, intent passes after normalization; E: focus Amber, runner `amber-09`, 0 build-up passes; F: a decoy straight run (angle < 15°, displacement ≥ 8 m) by another Amber player and the intent check still passes; eval `match_id` matches `^sim-[0-9a-f]{10}$`; `demo_match` with `split="eval"` → `ConfigError("invalid_variant")`
- [ ] T052 [US5] Implement variant D–F handling in `backend/src/tactistream/simulator/script.py` (period 2 metadata and records, Amber focus, decoy run hook) and in each family module's key-actor tables; `demo_match` refuses eval in `backend/src/tactistream/simulator/config.py`. Run T051 → green
- [ ] T053 [US5] Extend `backend/tests/unit/simulator/test_library_matrix.py` with variants D–F × seeds 10000–10004 (default) and 10000–10099 (`slow`) for all 7 families (SC-002/SC-003 totals: 210 default, 4,200 slow)

**Checkpoint**: 008 can generate held-out data that development never saw.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T054 [P] Write `docs/simulator.md`: pitch/clock conventions, possession table, kinematic limits, families and intent checks, variants and split policy, manifest isolation, determinism and golden-update policy (bump `generator_version`), limitation statement ("synthetic performance is evidence about this controlled environment, not professional-match accuracy")
- [ ] T055 [P] Add `backend/tests/perf/test_sim_perf.py` (`@pytest.mark.slow`): median of 5 runs, single family ≤ 0.5 s, `demo_match` ≤ 3 s; run on the Codespace and record values plus hardware in `specs/002-synthetic-simulator/research.md` R10 (SC-006)
- [ ] T056 [P] Update `README.md` with a "Synthetic simulator" section (`tactistream-sim list/generate`, scenario selector, seeds) and run `specs/002-synthetic-simulator/quickstart.md` on a fresh clone; fix gaps
- [ ] T057 Update `specs/README.md` feature table: mark the 002 exit condition met with date, and link `docs/simulator.md`

---

## Dependencies & Execution Order

- Setup (T001–T002) → Foundational (T003–T019) → US1 (T020–T027) → US2 (T028–T038) ‖ US3 (T039–T047) → US4 (T048–T050) → US5 (T051–T053) → Polish (T054–T057).
- Within Foundational: T003–T012 are pairwise parallel (separate modules); T013–T014 need T008 + T010; T017 needs T016; T018–T019 need T008, T010, T014.
- US2 backend (T028–T035) needs only T023 (engine) and T031; frontend T036–T037 can start once T033 fixes the API shape; T038 needs both.
- US3 families are independent modules ([P]) after T021 sets the pattern; T046 needs T021.
- US4 needs US3 (all families exist). US5 touches `script.py` and every family, so run it after US3/US4 to avoid conflicts.
- 003 can start after US1 + US3 (it needs the hero, negatives and `tracking_gap`); `demo_match` (US4) is needed for 003's replay-consistency test.

## Parallel Example

```text
Morning 14 Oct:   T003‖T005‖T007‖T009‖T011 (tests) → T004‖T006‖T008‖T010‖T012
Afternoon 14 Oct: T013–T019 → T020–T027 (hero)
15 Oct:           T028–T035 (replay backend) ‖ T039–T046 (families) ‖ T036–T037 (frontend) → T048–T050 → T051–T053
```

## Implementation Strategy

MVP = Phases 1–4 (hero + replay with new seed = roadmap exit condition). Then US3 (needed by 003), US4 (demo), US5
(needed by 008 on 22 Oct; may slip to 16 Oct without blocking 003/004). Stop and validate at each checkpoint.
