---
description: "Task list for 003 live state & metrics"
---

# Tasks: Live State & Metrics

**Input**: `specs/003-live-state-metrics/` (spec, plan, research, data-model, contracts, quickstart)

**Prerequisites**: 001 merged (contracts, `MatchState`, `EvidenceIndex`, `WsHub`, `MatchSession`, `FeedReplayer`, `FakeClock`,
`compute_forward_progress`, fact path); 002 US1 + US3 merged (hero, negatives, `tracking_gap`), 002 US4 for `demo_match` tests.

**Tests**: REQUIRED (constitution V). Each implementation task follows a test task that must fail first for the stated reason.

**Format**: `[ID] [P?] [Story] Description`. `[P]` means parallelizable (different files, no unmet dependency).

## Phase 1: Setup

- [ ] T001 Update `backend/src/tactistream/settings.py` with `data_dir: Path = Path(".data")`, `reorder_window_ms: int = 500`, `checkpoint_every_records: int = 100`, `checkpoint_every_ms: int = 10000`, `restore_on_start: bool = True` (env prefix `TACTISTREAM_`); add these names to `.env.example`; add `.data/` to `.gitignore`; extend `backend/tests/unit/test_settings.py` to assert the defaults
- [ ] T002 [P] Create empty modules with docstrings: `backend/src/tactistream/state/{ingest,snapshot,checkpoint}.py`, `backend/src/tactistream/storage/{__init__,base,local}.py`, `backend/src/tactistream/metrics/{geometry,pass_completion,rhythm,pressure,channel,receiver_separation,defender_follow,off_ball_run,contribution,registry}.py`, `backend/src/tactistream/moments/{__init__,detector,ranking,pipeline}.py`, `backend/src/tactistream/api/{insight_ledger,routes_snapshot}.py`, test package dirs `backend/tests/unit/{state,metrics,moments}/__init__.py`, and `backend/tests/golden/metrics_space_creation_42_A.json` containing `{}`
- [ ] T003 [P] Create test fixtures. `backend/tests/fixtures/sim.py` provides session-cached `sim_output(scenario, seed, variant="A")`, `envelopes(output)` (canonical order) and `shuffled_delivery(envelopes, rng_seed, block=8, dup_rate=0.2)`, which permutes within blocks of 8 and inserts duplicates right after the original or up to 8 positions later. `backend/tests/fixtures/snapshots.py` provides `SnapshotBuilder`: a default 4-3-3 with all 22 visible, Blue attacking +x in period 1, and `.at(t_ms).place(player_id, x, y)`, `.hide(player_id)`, `.drop_frame(t_ms)`, `.event(type, actor, t_ms, **fields)`, `.build(as_of_ms)` returning a `MatchSnapshot`

**Checkpoint**: `make lint && make test` pass; 001/002 suites unchanged.

---

## Phase 2: Foundational (blocks all stories)

- [ ] T004 [P] Write failing `backend/tests/unit/state/test_match_state_store.py`:
  - applying 3 events and 5 frames keeps all of them: events by sequence, frames by index
  - `state_version == 9` after metadata + 8 records; a duplicate leaves `state_version` unchanged
  - `StateDelta.revision is None` and `late_frame is False` for in-order records
  - an event with a lower sequence gives `delta.revision == Revision(record_id, "event", t)`, is inserted in sequence order, and increments `state_version` by 1
  - a frame with a lower index gives `delta.late_frame is True`, but `latest_frame` keeps the highest index
  - 001's `state_hash` is unchanged for the skeleton fixture; `full_state_hash` is equal for the same records applied in two different orders
- [ ] T005 [P] Write failing `backend/tests/unit/state/test_snapshot.py` (via `MatchState.snapshot`):
  - `snapshot(12000)` contains only records with `session_clock_ms ≤ 12000`
  - `frame_at(1049)` returns the frame at 1000 and `frame_at(1051)` returns `None` when frames exist at 1000 and 1100 only
  - `position("blue-09", t)` is `None` when blue-09 is invisible
  - `attack_direction("blue", 1) == 1` and `attack_direction("blue", 2) == -1` for two-period metadata
  - `events_between(5800, 8800)` is inclusive at both ends
  - assigning to an attribute raises `FrozenInstanceError`
  - `snapshot()` without `as_of` uses `state.session_clock_ms`
  - two calls at the same `state_version` return equal tuples without copying (`is` on `events`)
- [ ] T006 [P] Write failing `backend/tests/unit/artifact_store_contract.py`, a reusable `ArtifactStoreContract` class whose tests use a `store` fixture:
  - put/get round-trip of bytes; `get` on a missing key raises `ArtifactNotFound`; `exists` works before and after `put`
  - `list("checkpoints/m1/")` returns sorted keys and excludes `checkpoints/m10/…`
  - `append` creates the key, then concatenates; `delete` is idempotent
  - keys `"../x"`, `"/abs"`, `"A/b"` and `""` raise `ValueError`

  Also write `backend/tests/unit/state/test_local_store.py`, which subclasses the contract with `LocalArtifactStore(tmp_path)` and adds atomicity: a put interrupted by a patched `os.replace` raising `OSError` leaves the previous content intact
- [ ] T007 [P] Write failing `backend/tests/unit/metrics/test_geometry.py`.

  Exact cases:
  - `normalize((10.0, 20.0), -1) == (95.0, 48.0)`
  - `point_segment_distance((1,1), (0,0), (2,0)) == 1.0` and `point_segment_distance((3,0), (0,0), (2,0)) == 1.0`
  - `folded_angle_deg((6,8), 1) ≈ 53.1`; `folded_angle_deg((-6,8), 1) ≈ 126.9`; `folded_angle_deg((-6,-8), -1) ≈ 53.1`
  - `cosine((4,6), (6,8)) ≈ 0.9985`; `cosine((0,0), (1,0)) == 0.0`
  - `nearest_visible(snapshot, t, "blue-08", team="amber", k=3)` returns ids ordered by distance, ties broken by `player_id`
  - `visible_count(frame, "amber") == 11` by default and 9 after two `hide`s

  Hypothesis properties (`derandomize=True`):
  - `normalize(normalize(p, -1), -1) == p`
  - the distance is ≥ 0 and ≤ the distance to either endpoint
  - the folded angle lies in [0, 180]
- [ ] T008 Implement `backend/src/tactistream/state/snapshot.py` (`MatchSnapshot` per data-model.md, bisect slicing helpers). Run the T005 snapshot-only cases → green
- [ ] T009 Extend `backend/src/tactistream/state/match_state.py`:
  - add `Revision` and the new `StateDelta` fields
  - keep whole-match stores
  - add `snapshot`, `session_clock_ms`, `max_frame_index`, `record_keys` and `full_state_hash`
  - cache frozen tuples per `state_version`

  Run T004 and T005, then the 001 suite → green
- [ ] T010 [P] Implement `backend/src/tactistream/storage/base.py` (`ArtifactStore` Protocol, `ArtifactNotFound`), `storage/__init__.py` exports, and `storage/local.py` (`LocalArtifactStore`; key regex `^[a-z0-9._-]+(/[a-z0-9._-]+)*$` without `..`; tmp file + `os.replace`; `append` opens in `ab`). Run T006 → green
- [ ] T011 [P] Implement `backend/src/tactistream/metrics/geometry.py` (`normalize`, `point_segment_distance`, `nearest_visible`, `visible_count`, `displacement`, `folded_angle_deg`, `cosine`, NumPy-vectorized distance helper). Run T007 → green
- [ ] T012 Write failing `backend/tests/unit/metrics/test_registry.py`:
  - `MetricEngine.metric_id("channel", 5) == "metric-channel-0005"`
  - `metric_id("contribution", 45, "blue-09") == "metric-contribution-0045-blue-09"`
  - `definitions()` returns 9 kinds, each with `definition_version == f"{kind}.v1"` and `limitation_key == f"limitation.{kind}"`
  - `compute("forward_progress", …)` on the 001 skeleton pass equals 001's `compute_forward_progress` result (13.1 m)
  - `forward_progress` on a carry is `unavailable/not_applicable`
  - an anchor with `session_clock_ms > as_of` raises `AnchorNotFound`
  - a second identical call returns the cached object (`is`) and calls the module function once (spy)
  - a new `state_version` misses the cache
- [ ] T013 Implement `backend/src/tactistream/metrics/registry.py` (`MetricParams`, `MetricDefinition` table for all 9 kinds, `AnchorNotFound`, `MetricEngine` with LRU cache keyed per data-model.md, dispatch table with `forward_progress` wrapper; other kinds registered as they land). Run T012 → green except dispatch of unimplemented kinds (marked `xfail(strict=True)` until US2)
- [ ] T014 Write failing `backend/tests/unit/api/test_evidence_snapshot.py`:
  - `EvidenceIndex` resolves `evt-0005` and the `frm-` ID of the frame at 8800 through `state.snapshot(as_of)` for the hero
  - an event after `as_of` → `None`
  - adding `metric-channel-0005` twice with different `state_version` returns the later one
- [ ] T015 Modify `backend/src/tactistream/api/evidence.py` (event/frame lookup through `MatchState.snapshot`, metric map latest-wins). Run T014 and 001 `test_evidence_api.py` → green

**Checkpoint**: snapshots, storage and geometry are usable by every story.

---

## Phase 3: User Story 1 — Reliable ingest (P1) 🎯 MVP

**Goal**: guarded ingest with dedupe, reorder window, gaps, revisions and late frames.

**Independent Test**: `uv run pytest tests/unit/state/test_ingest.py tests/integration/test_replay_consistency.py tests/integration/test_ingest_ws.py`.

- [ ] T016 [P] [US1] Write failing `backend/tests/unit/state/test_ingest.py` with `FakeClock` and `wall_ms=lambda: 1_700_000_000_000`. Cases:
  - **reorder**: events 10, 12, 11 at clock 0/100/200 are applied in order 10, 11, 12, with 12 `held` at 100 and no gap
  - **gap**: 12 alone after 10; `tick()` at 499 ms releases nothing; at 500 ms it releases 12 with `gap == (11, 11)` and `stats.gaps == 1`
  - **duplicates**: every envelope twice gives `stats.duplicates == n`; a same-key, different-payload copy gives `payload_conflicts == 1` and the first payload is kept
  - **late frame**: frame 431 after 440 gives `status == "late_frame"`, is present in `state.snapshot().frames_between`, and `stats.late_frames == 1`
  - **revision**: sequence 8 after 10 applied (8 never seen) gives `status == "revision"`
  - **metadata**: an event before metadata is `held` with no timer; after `metadata` arrives it is released
  - **ignored kinds**: `insight`, `agent_trace` and `latency` are `ignored`
  - **invalid**: a schema-invalid envelope is `invalid`, does not change `state_version`, and is still `archive.buffer`ed
  - **first event**: seq 1 is released immediately; first seq 40 is held, then released alone at 500 ms with `gap is None`
  - **receipt stamping**: `server_receipt_ms` is stamped only when absent
  - **flush**: `flush()` releases everything in order
- [ ] T017 [P] [US1] Write failing `backend/tests/integration/test_replay_consistency.py` for `demo_match` seed 42 A:
  - baseline: in-order delivery through `Ingestor` + `flush()`
  - 20 runs of `shuffled_delivery(…, rng_seed=i)` for i in 0..19, each followed by `flush()`
  - every run has `full_state_hash` equal to the baseline, and `MetricEngine.compute("pass_completion", snapshot, last_event_id)` components `completed`/`attempted` for both teams equal the baseline
  - `stats.duplicates` equals the number of injected copies
- [ ] T018 [P] [US1] Write failing `backend/tests/integration/test_ingest_ws.py` (session on `InMemoryBus`, `FakeClock`, WS test client):
  - a bus that delivers every envelope twice yields exactly one `event` WS message per `event_id`
  - withholding seq 11 of the hero yields one `error` message `{"error":"sequence_gap","detail":"missing 11-11"}` after the clock advances 500 ms
  - a late frame produces no `frame` message
  - Start/Pause/Reset from 001 still work
- [ ] T019 [US1] Implement `backend/src/tactistream/state/ingest.py` (`IngestStatus`, `IngestResult`, `IngestStats`, `Ingestor` rules 1–9 from data-model.md, `max_buffer` overflow → oldest held released with gap). Run T016 and T017 → green
- [ ] T020 [US1] Modify `backend/src/tactistream/api/session.py`:
  - the live-state subscription feeds `Ingestor.accept`
  - a tick task every 100 ms on `Clock` calls `Ingestor.tick`
  - broadcast applied events and frames (not late frames)
  - send the `sequence_gap` error on gaps
  - skip broadcasts in 002 bulk mode
  - 001 fact path unchanged for applied events

  Run T018 and the 001/002 session suites → green

**Checkpoint**: duplicates and reorderings no longer change state; roadmap item "ingest dedupes/reorders" met.

---

## Phase 4: User Story 2 — Explainable metrics (P1)

**Goal**: nine metric kinds with evidence, parameters, components and honest unavailability.

**Independent Test**: `uv run pytest tests/unit/metrics`.

All tests use `SnapshotBuilder` positions; expected values are exact after the documented rounding, and every result passes `schema_registry.validate("metric_result", …)`.

- [ ] T021 [P] [US2] Write failing `backend/tests/unit/metrics/test_pass_completion.py`:
  - Blue window with 4 completed, 1 incomplete and 1 `outcome=None` pass → `value == 0.8`, components `{completed: 4, attempted: 5}`, `inputs.excluded_count == 1`, `inputs.event_ids` = the 5 counted passes
  - a pass at `t − 300001` is excluded
  - zero attempts → `unavailable/missing_events`
- [ ] T022 [P] [US2] Write failing `backend/tests/unit/metrics/test_rhythm.py`:
  - first event at 0, anchor at 120000, 9 completed Blue passes and 2 Blue turnovers → `value == 4.5`, `turnovers_per_min == 1.0`, `window_min == 2.0`
  - anchor at 59000 → `unavailable/not_applicable`
  - there is no single combined score field
- [ ] T023 [P] [US2] Write failing `backend/tests/unit/metrics/test_pressure.py`:
  - Amber defenders at 1.0/2.0/3.0 m from carrier `blue-08` → `value == 47.4`, `d1_m=1.0`, `d2_m=2.0`, `d3_m=3.0`, `subject_ids[0] == "blue-08"`, params `{scale_m: 2.5, k: 3, min_visible_opponents: 10}`
  - defenders at 5.0/7.5/10.0 m → `6.8`
  - only one defender within 30 m and the others at 40+ m → `22.3`
  - 9 visible opponents → `unavailable/insufficient_tracking` with no `value`
  - carrier hidden → same
  - frame dropped at t → same
  - anchor on a `tackle` → `unavailable/not_applicable`
- [ ] T024 [P] [US2] Write failing `backend/tests/unit/metrics/test_channel.py`:
  - passer (50,34), receiver (60,34); nearest opponent to the lane at (55,35.04) at t−4000 and (55,37.96) at t → components `1.0` and `4.0`, `value == 3.0`
  - this shows that rounding happens before subtraction: the raw difference would be 2.92, whose 1 dp rounding is 2.9
  - `inputs.frame_ids` = [frame t−4000, frame t]; `subject_ids == ["blue-08","blue-11"]`
  - an opponent beyond the segment end is measured to the endpoint
  - passer hidden at t−4000 → `insufficient_tracking`
  - 9 visible opponents at t−4000 only → `insufficient_tracking`
  - pass without `recipient_id` → `not_applicable`
- [ ] T025 [P] [US2] Write failing `backend/tests/unit/metrics/test_receiver_separation.py`:
  - nearest opponent to the receiver is 2.0 m at t−4000 and 6.5 m at t → `value == 4.5`
  - with a reception frame at t+800 where it is 5.2 m → `separation_at_reception_m == 5.2` and its frame ID is in `inputs.frame_ids`
  - without that frame in the snapshot, the component is absent
  - receiver hidden → `insufficient_tracking`
- [ ] T026 [P] [US2] Write failing `backend/tests/unit/metrics/test_off_ball_run.py`. The pass is at t = 10000, Blue attacks +x, and `blue-09` moves linearly (60,30)→(66,38) from 5000 to 7000 then stands still. Cases:
  - **qualifying run**: `value == 10.0`, `duration_ms == 2000`, `mean_speed_mps == 5.0`, `angle_deg == 53.1`, `subject_ids == ["blue-09"]`, `inputs.frame_ids == [frm@5000, frm@7000]` (spans such as 4500–7000 also reach 10.0 m but are longer; ties → shorter duration, then earlier s)
  - **attack direction**: the same run mirrored for attack direction −1 (66,38)→(60,30) gives the same value and angle
  - **direction filter**: a straight (10,0) run → `not_applicable`; a lateral (0,10) run → `not_applicable`
  - **speed filter**: 8.4 m over 4000 ms (2.1 m/s) → `not_applicable`
  - **passer/receiver excluded**: the passer and receiver are never candidates
  - **tracking**: `blue-10` hidden in 31% of window frames → `insufficient_tracking`
  - **tie-break**: two runners of equal 10.0 m → the lower `player_id`
- [ ] T027 [P] [US2] Write failing `backend/tests/unit/metrics/test_defender_follow.py`:
  - with the T026 run, `amber-04` nearest at 5000 moving (68,30)→(72,36) → `value == 1.0` (0.9985 rounded), `defender_displacement_m == 7.2`, `runner_displacement_m == 10.0`, `subject_ids == ["amber-04","blue-09"]`
  - a defender moving 0.6 m → `value == 0.0`
  - the run is `not_applicable` → `defender_follow` is `not_applicable`
  - defender hidden at 7000 → `insufficient_tracking`
- [ ] T028 [P] [US2] Write failing `backend/tests/unit/metrics/test_contribution.py`:
  - `blue-09` is the actor of 2 events and the recipient of 1 completed pass inside one moment window, plus the subject of an ok `off_ball_run` in a second moment → `value == 4`, components `{direct_events: 3, off_ball_involvements: 1, moments_considered: 2}`, `metric_id == "metric-contribution-0045-blue-09"`
  - events outside the windows are not counted
  - `moments=()` → `unavailable/missing_events`
  - schema validation is skipped (`xfail` with reason "MetricId extension pending") until the cross-cutting change lands
- [ ] T029 [P] [US2] Implement `backend/src/tactistream/metrics/pass_completion.py`. Run T021 → green
- [ ] T030 [P] [US2] Implement `backend/src/tactistream/metrics/rhythm.py`. Run T022 → green
- [ ] T031 [P] [US2] Implement `backend/src/tactistream/metrics/pressure.py`. Run T023 → green
- [ ] T032 [P] [US2] Implement `backend/src/tactistream/metrics/channel.py`. Run T024 → green
- [ ] T033 [P] [US2] Implement `backend/src/tactistream/metrics/receiver_separation.py`. Run T025 → green
- [ ] T034 [P] [US2] Implement `backend/src/tactistream/metrics/off_ball_run.py` (exhaustive span search on the 100 ms grid, vectorized per candidate). Run T026 → green
- [ ] T035 [US2] Implement `backend/src/tactistream/metrics/defender_follow.py` (calls `off_ball_run` via the engine for the same anchor). Run T027 → green
- [ ] T036 [P] [US2] Implement `backend/src/tactistream/metrics/contribution.py`. Run T028 → green
- [ ] T037 [US2] Register all kinds in `backend/src/tactistream/metrics/registry.py`; remove the T013 `xfail`s. Run `tests/unit/metrics` → green
- [ ] T038 [US2] Write failing `backend/tests/unit/metrics/test_golden_sim.py`:
  - **hero `space_creation` 42 A**: the dump of all 9 kinds anchored on `evt-0005` (contribution for `blue-09` with no moments) equals `tests/golden/metrics_space_creation_42_A.json`; `channel ≥ 2.0`; `off_ball_run.subject_ids == ["blue-09"]`, value ≥ 8.0, angle in [20, 70]; `defender_follow.subject_ids[0] == "amber-04"`, value ≥ 0.7
  - **`run_no_channel` 42 A**: channel < 2.0 at its forward pass (from the manifest's `key_event_ids`)
  - **`tracking_gap` 42 A**: `pressure`/`channel`/`off_ball_run`/`defender_follow` at the forward pass are `unavailable/insufficient_tracking`
  - **SC-007**: every `ok` result references ≥ 1 event ID, and tracking-based kinds reference ≥ 1 frame ID
- [ ] T039 [US2] Record the golden (`TACTISTREAM_UPDATE_GOLDEN=1 uv run pytest tests/unit/metrics/test_golden_sim.py`), check the recorded channel value against the 002 design value (clearance ≈ 2.4 → ≈ 6.0 m, gain ≈ 3.6 m ± jitter; 002 data-model hero table), commit, rerun T038 → green
- [ ] T040 [P] [US2] Write failing `backend/tests/unit/narrative/test_catalog_limitations.py`: `narrative/catalog/en.json` and `hi.json` contain `limitation.{kind}` for all 9 kinds; the EN texts equal the data-model.md table; `render_claim` can render each key without slots
- [ ] T041 [P] [US2] Add the 9 limitation keys to `backend/src/tactistream/narrative/catalog/en.json` and `hi.json` (HI drafted, flagged for 006 review). Run T040 → green
- [ ] T042 [P] [US2] Write `docs/metrics.md`: per kind, the formula, parameters with defaults (from `MetricParams`), unit, rounding, unavailable conditions and limitation text, plus a "prototype parameters, not validated statistics" note. Add `backend/tests/unit/metrics/test_docs_metrics.py`, which asserts each kind heading and every `MetricParams` field name appears in the doc

**Checkpoint**: every number later shown is reproducible from `MetricEngine` with evidence; roadmap item "metrics explainable" met.

---

## Phase 5: User Story 3 — Candidate moments (P1)

**Goal**: pure detection, ranking, lifecycle and live broadcast of moments.

**Independent Test**: `uv run pytest tests/unit/moments tests/integration/test_moments_ws.py`.

- [ ] T043 [P] [US3] Write failing `backend/tests/unit/moments/test_detector_rules.py` (SnapshotBuilder):
  - **window**: sequence start at t−15000 → start t−12000; at t−5000 → start t−8000; at t−10000 → start t−10000; trigger at 3000 → start 0; `end == t + duration + 500`
  - **settling**: a shot is not evaluated before a frame ≥ t+duration+200 exists
  - **coverage**: a 101-frame window with 5 frames missing and 5 frames where an involved player is hidden → `0.901`; a frame where Amber has only 9 visible counts as uncovered
  - **press_turnover**: pressure 36.0 on the victim's pass 2000 ms before an interception → `press_turnover` with `metric_ids == [pressure(V)]`; pressure 34.9 → none; 3100 ms gap → none
  - **switch_escape**: completed pass with Δy 32 m and reception separation 5.5 m → `switch_escape`; Δy 28 m → none; separation 4.9 m → none
  - **shot**: a shot without a qualifying pass → `shot`
  - **no-shot space pass**: a qualifying pass with no shot within 12 s → `space_creation` with `mom-{pass seq}` once settled at t_P + 12000
  - **precedence**: a pass that is both a switch and a space pass yields only `switch_escape`
  - **purity**: two calls return equal lists
- [ ] T044 [P] [US3] Write failing `backend/tests/unit/moments/test_ranking.py`:
  - hero-like space_creation with channel 3.6 and coverage 1.0 → `0.93`; pinned `blue-09` → `1.23`; pinned `amber-99` → `0.93`
  - press_turnover with pressure 52.5 and coverage 0.9 → `0.55 + 0.1875 + 0.135 = 0.8725`
  - shot on_target with coverage 0.5 → `0.4 + 0.125 + 0.075 = 0.6`
  - equal scores order by `window.end_ms`, then `moment_id`
  - `rank` returns copies; originals are unchanged
- [ ] T045 [P] [US3] Write failing `backend/tests/unit/moments/test_pipeline.py` (stub engine/detector):
  - first detection → `MomentChange("new")` and the `on_moment` hook is called once
  - the same moment with only `state_version` changed → no change
  - changed pattern → `"revised"` with `previous` set, and `on_moment_revised` is called
  - disappearance → `"removed"`
  - `on_snapshot` skips detection when nothing changed (detector spy count) and runs on `revision=True`
  - `metric_state_hash` ignores `state_version` and is order-independent over moments and metrics
- [ ] T046 [P] [US3] Write failing `backend/tests/unit/moments/test_moments_sim.py`:
  - **hero**: after the feed, `moments() == [mom-0007]` with `pattern="space_creation"`, `trigger_event_id="evt-0007"`, involved ⊇ {blue-08, blue-11, blue-09, amber-04}, `metric_ids` ⊇ {metric-off_ball_run-0005, metric-defender_follow-0005, metric-channel-0005}, `tracking_coverage == 1.0`, `rank_score ≥ 0.85`
  - **`tracking_gap` 42 A**: one `shot` moment with coverage < 0.9
  - **`demo_match` 42 A**: exactly 4 moments with patterns {space_creation, press_turnover, switch_escape, shot}, `space_creation` first
  - **matrix over seeds 1–20 × A–C** (`@pytest.mark.slow` for the full matrix, seeds 1–3 by default):
    - each positive yields its pattern in every run
    - `run_no_channel`/`press_no_turnover`/`switch_closed` never yield their positive pattern
    - `tracking_gap` never yields space_creation and has coverage < 0.9

  All produced moments validate as `candidate_moment`.
- [ ] T047 [P] [US3] Extend `backend/tests/integration/test_replay_consistency.py`: each of the 20 runs also runs `MomentPipeline.reconcile` and asserts `metric_state_hash` equals the baseline (SC-001)
- [ ] T048 [P] [US3] Write failing `backend/tests/integration/test_moments_ws.py` (hero session, `FakeClock`). Live play:
  - the client receives `metric` messages for each of `mom-0007`'s `metric_ids` (any order), then one `moment`, and the `moment` arrives ≤ 1500 ms of fake time after the shot's receipt
  - every ID in the moment's `metric_ids` and in each metric's `inputs` resolves via `GET /api/matches/demo-blue-amber-001/evidence/{id}` (200)

  Snapshots and bulk mode:
  - a WS reconnect snapshot contains `moments == [mom-0007]`
  - a 002 seek to 14100 sends no `moment` messages, and the closing snapshot contains `mom-0007`
- [ ] T049 [US3] Implement `backend/src/tactistream/moments/detector.py` (`DetectionParams`, turnover/sequence-start helpers, `moment_window`, `tracking_coverage`, `detect_moments` with the trigger table and precedence rules). Run T043 → green
- [ ] T050 [US3] Implement `backend/src/tactistream/moments/ranking.py` (`BASE`, `PINNED_BONUS`, `strength`, `score`, `rank`); `detect_moments` sets `rank_score` via `score`. Run T044 → green
- [ ] T051 [US3] Implement `backend/src/tactistream/moments/pipeline.py` (`MomentChange`, `MomentPipeline`, `metric_state_hash`). Run T045, T046 and T047 → green
- [ ] T052 [US3] Modify `backend/src/tactistream/api/session.py`:
  - the tick task calls `pipeline.on_snapshot(state.snapshot())`
  - for a new or revised moment: `EvidenceIndex.add` each metric, broadcast the `metric` messages, then the `moment`
  - include `pipeline.moments()` in the WS snapshot and the 002 seek snapshot
  - bulk mode suppresses moment/metric broadcasts
  - expose `session.pipeline.add_hook` for 004

  Run T048 → green
- [ ] T053 [P] [US3] Write failing `frontend/tests/unit/matchStore.moments.test.ts`:
  - `moment` upserts by `moment_id`; an older `state_version` is ignored
  - `metric` is stored by `metric_id`
  - `insight_revoked` for the active insight hides it and marks (id, version) revoked; a later `insight` with the same id and version is ignored
  - `error{sequence_gap}` sets `feedGap = true` until the next snapshot
  - a snapshot replaces moments
- [ ] T054 [P] [US3] Write failing `frontend/tests/unit/MomentList.test.tsx`:
  - renders moments sorted by `rank_score` with the EN pattern names "Space creation" / "Press turnover" / "Switch escape" / "Shot" and the HI equivalents after a language switch
  - shows session time as `m:ss`
  - shows a "Partial tracking" badge only when `tracking_coverage < 1.0`
  - is an accessible list (`role="list"`)
- [ ] T055 [US3] Modify `frontend/src/store/matchStore.ts` per FR-029. Run T053 → green
- [ ] T056 [US3] Implement `frontend/src/components/MomentList.tsx`, add strings to `frontend/src/i18n/{en,hi}.ts`, render in the `frontend/src/App.tsx` side panel with the feed-gap indicator. Run T054 → green

**Checkpoint**: roadmap item "candidate moments detected" met; 004/005 can consume `MomentPipeline` and `MatchSnapshot`.

---

## Phase 6: User Story 4 — Late-event revision (P2)

**Goal**: late data revises state and moments; affected insights are revoked, never silently kept.

**Independent Test**: `uv run pytest tests/unit/moments/test_insight_ledger.py tests/integration/test_late_event_revision.py`.

- [ ] T057 [P] [US4] Write failing `backend/tests/unit/moments/test_insight_ledger.py`:
  - `register(ins-0007 v1, moment_id="mom-0007", evidence_ids=["evt-0007"])`; `affected({"mom-0007"}, set()) == [("ins-0007", 1)]`; `affected(set(), {"evt-0007"})` returns the same
  - after `revoke(..., "late_event_revision")` it returns `[]`, and the returned `InsightRevoked` validates against `ws_message` `$defs/InsightRevoked`
  - registering v2 makes v2 the latest; `affected` lists only v2
  - `released(5000)` excludes bundles with `as_of_session_ms > 5000` and revoked ones
- [ ] T058 [P] [US4] Write failing `backend/tests/integration/test_late_event_revision.py` (hero session, `FakeClock`, a bus wrapper that holds back `evt-0005` until released by the test):
  - **shot without the pass**: after the shot settles, `mom-0007` is broadcast with `pattern == "shot"`
  - **revocation**: the test calls `session.ledger.register(ins-0007 v1, moment_id="mom-0007", evidence_ids=["evt-0007"])` and then releases `evt-0005`. Within one 100 ms tick, the client receives in order:
    1. `event` evt-0005
    2. exactly one `insight_revoked{insight_id:"ins-0007", insight_version:1, reason:"late_event_revision"}`
    3. `metric` × n
    4. `moment` mom-0007 with `pattern == "space_creation"` and a higher `state_version`
  - **no stale card**: no fact card is produced for the late `evt-0005`
  - **late frames**: a late frame inside the window that does not change content causes no `moment` message; a late frame that hides `blue-09` revises `mom-0007` to `shot` with lower coverage and revokes again
- [ ] T059 [US4] Implement `backend/src/tactistream/api/insight_ledger.py`. Run T057 → green
- [ ] T060 [US4] Modify `backend/src/tactistream/api/session.py`:
  - create `InsightLedger` per session; register 001 fact-card bundles on release
  - revision and late-frame results call `pipeline.on_snapshot(..., revision=True)`
  - `revised` changes revoke `ledger.affected(...)` before broadcasting metrics and the moment
  - `removed` changes revoke, then broadcast a fresh `snapshot`
  - skip the fact path for `revision` results (stale show window)
  - reset/backward seek rebuilds ingestor, pipeline and ledger

  Run T058 → green

**Checkpoint**: SC-005 demonstrable; the constitution's "late events" failure fixture exists.

---

## Phase 7: User Story 5 — Checkpoint, restore, snapshots, resume (P2)

**Goal**: restart recovery through `ArtifactStore`, as-of REST snapshots, and resume with moments.

**Independent Test**: `uv run pytest tests/unit/state/test_checkpoint.py tests/integration/test_restore.py tests/integration/test_snapshot_api.py tests/integration/test_ws_resume_moments.py`.

- [ ] T061 [P] [US5] Write failing `backend/tests/unit/state/test_checkpoint.py` (`LocalArtifactStore(tmp_path)`, `FakeClock`):
  - **record trigger**: after 250 accepted records, `list("checkpoints/m1/") == ["checkpoints/m1/00000100.json", "checkpoints/m1/00000200.json"]`; after 500 only `00000300`–`00000500` remain (keep 3)
  - **time trigger**: 5 records and a 10,000 ms clock advance → `due()`
  - **archive**: the archive has one line per received envelope including duplicates and invalid ones; `archive_lines` equals the lines flushed at write time
  - **round-trip**: `MatchState.from_checkpoint(state.to_checkpoint())` has an equal `full_state_hash` and `record_keys`
  - **failure handling**: a store whose `put` raises → `write` returns `None`, increments `failures`, and does not raise
  - **clear**: `clear` deletes all `checkpoints/m1/` and `feed-archive/m1/` keys
  - the checkpoint JSON has `format == "tactistream.checkpoint.v1"`
- [ ] T062 [P] [US5] Write failing `backend/tests/integration/test_restore.py`. For each N in {150, 1234, 2500} records of `demo_match` 42 A:
  - ingest N with checkpointing (`every_records=100`)
  - drop the session objects, then `restore(store, match_id, clock)`
  - feed records N+1..end through the restored ingestor (duplicates of already-archived records are counted as duplicates)
  - reconcile; assert `full_state_hash` and `metric_state_hash` equal the uninterrupted run

  Then simulate an app restart with `create_app` (`restore_on_start=True`) and assert:
  - `/api/health` lists the restored session `paused` at the checkpoint's `session_clock_ms`
  - the next WS message has `seq == ws_head_seq + 10000 + 1`
- [ ] T063 [P] [US5] Write failing `backend/tests/integration/test_snapshot_api.py` (hero after seek 14100):
  - `GET /api/matches/demo-blue-amber-001/snapshot?as_of_ms=12000` → 200, validates as `Snapshot`, 6 events (`evt-0001`–`evt-0006`), `latest_frame.session_clock_ms == 12000`, `moments == []`
  - without `as_of_ms` → contains `mom-0007`
  - `as_of_ms=999999` → `session_clock_ms == 14100`
  - `as_of_ms=-1` and `as_of_ms=abc` → 422 `invalid_as_of`
  - unknown match → 404 `match_not_found`
- [ ] T064 [P] [US5] Write failing `backend/tests/integration/test_ws_resume_moments.py`: hero played past the shot; a client that saw seq K reconnects with `resume{last_seq: K}` and receives a snapshot listing `mom-0007` once; subsequent live messages have seq > the snapshot's seq
- [ ] T065 [P] [US5] Write failing `backend/tests/unit/transport/test_replayer_set_cursor.py`: `set_cursor(9000)` on the hero publishes nothing, and `play()` then publishes the first record with `session_clock_ms > 9000`
- [ ] T066 [US5] Implement `backend/src/tactistream/state/checkpoint.py`: `CHECKPOINT_FORMAT`, `checkpoint_key`, `archive_key`, `FeedArchive`, `Checkpointer` and `clear`. Also add `MatchState.to_checkpoint`/`from_checkpoint` in `backend/src/tactistream/state/match_state.py`. Run T061 → green
- [ ] T067 [US5] Add `set_cursor(to_ms)` to `backend/src/tactistream/transport/replayer.py`. Run T065 → green
- [ ] T068 [US5] Implement `restore` and `RestoredMatch` in `backend/src/tactistream/state/checkpoint.py` (latest checkpoint → state + ingest cursor + dedupe keys → archive lines after `archive_lines` through `Ingestor`). Run the first part of T062 → green
- [ ] T069 [US5] Modify `backend/src/tactistream/api/session.py`:
  - `FeedArchive` in the `Ingestor`; `Checkpointer.note_applied` on every accepted record
  - write in the background when `due()`
  - `clear(store, match_id)` on reset/backward seek
  - a restored session is built from `RestoredMatch`: replayer rebuilt from `session_config` plus `set_cursor`, hub seq starting at `ws_head_seq + 10000`, then `pipeline.reconcile`
- [ ] T070 [US5] Modify `backend/src/tactistream/api/app.py`:
  - `LocalArtifactStore(settings.data_dir / "artifacts")`, overridable through the app factory for 007
  - when `restore_on_start` is set, the lifespan restores every match under `checkpoints/` into paused sessions
  - include the snapshot router

  Run T062 and T064 → green
- [ ] T071 [US5] Implement `backend/src/tactistream/api/routes_snapshot.py` per `contracts/api-delta.md` (snapshot assembled from `state.snapshot(min(as_of, clock))`, `rank(detect_moments(...))`, `ledger.released(as_of)`). Run T063 → green

**Checkpoint**: roadmap item "reconnect resumes from last seq" met; 007 can plug `BlobArtifactStore` into the same contract suite.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T072 [P] Confirm 002's `backend/tests/unit/simulator/test_manifest_isolation.py` scans `state/`, `storage/`, `metrics/`, `moments/` and `api/` (incl. the new modules) and passes; add `backend/tests/unit/test_no_model_calls_core.py` asserting no import of `openai`, `azure.ai`, `agent_framework` or `httpx` under `state/`, `metrics/` and `moments/`
- [ ] T073 [P] Run `specs/003-live-state-metrics/quickstart.md` on a fresh clone; fix gaps; add a "Live state & metrics" section to `README.md` (moments panel, `docs/metrics.md`, `.data/` checkpoints, snapshot endpoint)
- [ ] T074 Add `backend/tests/perf/test_state_perf.py` (`@pytest.mark.slow`, median of 5 runs on `demo_match` 42 A). Thresholds:
  - cold `MomentPipeline.reconcile` on the final snapshot with an empty cache < 1 s
  - `Ingestor` throughput ≥ 2,000 records/s (in-order, no archive)
  - `restore` < 2 s
  - hero moment latency from shot receipt to `moment` broadcast ≤ 1.5 s on the real clock

  Run on the Codespace and record values plus hardware in `specs/003-live-state-metrics/research.md` R11 (SC-006, SC-008)
- [ ] T075 [US3] Write `backend/tests/integration/test_demo_match_moments.py`: simulate `demo_match` seed 42 variant A, feed it through `Ingestor` + `detect_moments`, unpinned `rank` → ≥ 3 moments, rank-1 moment has no `blue-09` in `involved_player_ids`, and `rank(..., pinned_player_id="blue-09")` puts the `space_creation` segment's moment first (002 US4 scenario 4; 006 SC-002). If it fails, tune 002 segment parameters, not the ranking formula
- [ ] T076 Update `specs/README.md` feature table: mark the 003 exit condition met with date and link `docs/metrics.md`

---

## Dependencies & Execution Order

- Setup (T001–T003) → Foundational (T004–T015) → US1 (T016–T020) → US2 (T021–T042) → US3 (T043–T056) → US4 (T057–T060) ‖ US5 (T061–T071) → Polish (T072–T075).
- Within Foundational:
  - T004–T007 are parallel
  - T008 → T009 (state uses snapshot)
  - T010 and T011 are independent
  - T012–T013 need T009 and T011
  - T014–T015 need T009
- US1 needs only Foundational. US2 metric tests and modules are pairwise parallel; T035 needs T034; T037 needs T029–T036; T038–T039 need T037 and 002 US3 outputs.
- US3 needs US2 (moments reference metrics). T053–T056 (frontend) can start as soon as the message shapes are fixed (they are contract types), in parallel with T049–T052.
- US4 and US5 both modify `api/session.py`: run T060 before T069, or merge carefully. Their tests (T057–T058, T061–T065) can be written in parallel.
- T046's `demo_match` cases and T017/T047/T062 need 002 US4 (`demo_match`); until it lands they are `skip`ped with reason "002 US4 pending".
- 004 needs US3 (`MomentPipeline.add_hook`, `MatchSnapshot`, `MetricEngine`) and US4 (`InsightLedger`). 005 needs US3 and T071. 007 needs T006 and T010 (contract suite, protocol).

## Parallel Example

```text
15 Oct morning:   T004‖T005‖T006‖T007 → T008‖T010‖T011 → T009 → T012–T015 → T016‖T017‖T018 → T019 → T020
15 Oct midday:    T021‖…‖T028 (tests) → T029‖T030‖T031‖T032‖T033‖T034‖T036 → T035 → T037–T039 ‖ T040–T042
15 Oct afternoon: T043‖T044‖T045‖T046‖T047‖T048 → T049 → T050 → T051 → T052 ‖ (T053‖T054 → T055 → T056)
15 Oct evening:   T057‖T058‖T061‖…‖T065 → T059 → T060 → T066‖T067 → T068 → T069 → T070 → T071 → T072–T075
```

## Implementation Strategy

MVP = Phases 1–5 (ingest + metrics + moments = the three roadmap exit items besides resume). US5 completes the exit
condition (reconnect/resume with moments, restart recovery). US4 is the reliability demonstration and may slip to the
morning of 16 Oct, before 004 needs the ledger. Stop and validate at each checkpoint.
