# Feature Specification: Synthetic Simulator — seeded, deterministic, football-plausible feed

**Feature Branch**: `002-synthetic-simulator`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan, "Make the synthetic data a serious engineering contribution": a deterministic simulator (not a prompt)
with a possession state machine, legal transitions between event types, bounded trajectories, consistent attack directions,
plausible speeds and a ball path consistent with each pass; three scenario families + three negatives + a missing-data
fixture; separate development and evaluation seeds *and* structures; scenario labels kept out of agent inputs. Roadmap exit:
seeded, deterministic event + 10 Hz tracking streams; replay at 1× with pause/reset/new seed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate the hero sequence deterministically (Priority: P1)

The builder runs `tactistream-sim generate --scenario space_creation --seed 42 --variant A --split dev --out data/generated/hero`
and gets `feed.jsonl` (metadata, events and 10 Hz tracking frames as `FeedEnvelope`s) plus a separate `manifest.json`. In the
feed, Blue 9 makes a diagonal off-ball run, Amber 4 moves with him, the central lane between Blue 8 and Blue 11 widens, Blue 8
plays a forward pass to Blue 11, and Blue 11 shoots. Running the command again produces byte-identical files.

**Why this priority**: Every later feature (metrics, moments, agents, Why Mode, the demo video) is built and tested on this
sequence. Determinism is what makes golden tests and the evidence page credible.

**Independent Test**: Run the CLI twice; compare SHA-256 of both files with each other and with the committed golden hash;
run `validate_output` on the result (zero issues); the scenario intent check (lane clearance gain ≥ 2.5 m) passes.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** the builder runs the generate command above twice into two directories,
   **Then** both `feed.jsonl` files and both `manifest.json` files are byte-identical and `feed.jsonl` matches the SHA-256 in
   `backend/tests/golden/simulator_hashes.json` under key `space_creation/42/A`.
2. **Given** the generated feed, **When** it is validated, **Then** every envelope validates against
   `feed_envelope.schema.json`, `match_id = demo-blue-amber-001`, every record has `source = {kind: synthetic,
   generator_version: "0.1.0", seed: 42}`, frames are contiguous at 100 ms, and all 22 player IDs appear in every frame.
3. **Given** the generated feed, **When** the events are listed, **Then** they contain a `pass` by `blue-08` to `blue-11`
   with `outcome = complete` followed (after a `carry` by `blue-11`) by a `shot` by `blue-11`, and Blue 9's tracked
   displacement over ≤ 3.2 s before that pass is ≥ 10 m at an angle of 30–60° to the attack axis.
4. **Given** the feed and the manifest, **When** the feed is searched for any manifest-only field
   (`scenario`, `variant`, `intended_explanation`, `expected_pattern`, `segments`), **Then** none is found.

---

### User Story 2 - Replay any scenario and seed in the app (Priority: P1)

A viewer opens TactiStream, picks a scenario in the session controls (default "Demo match"), keeps seed 42 or types another,
presses Start, and watches the synthetic match at 1×. They can pause, reset, switch speed between 0.5×, 1× and 2×, and press
**New seed** to load the same scenario with a fresh random development seed. The 001 skeleton fixture is still selectable and
behaves exactly as before.

**Why this priority**: The build plan's essential completion condition ("Replay at 1× speed with pause, reset and a new seed")
and the demo beat "Load an unseen seed" (0:58–1:13).

**Independent Test**: Backend integration test with `FakeClock` (create session from a scenario + seed, play, pause, speed,
seek, reset) and the Playwright test `simulator.spec.ts` (scenario selector, New seed, 2× speed) — both without Azure.

**Acceptance Scenarios**:

1. **Given** the app is running, **When** the viewer starts `space_creation` with seed 42, **Then** `POST /api/sessions`
   returns `match_id = demo-blue-amber-001`, the WebSocket snapshot carries `playback.seed = 42`, and event rows appear in
   session-time order at 1×.
2. **Given** a playing session, **When** the viewer selects 2×, **Then** after 2.0 s of wall time the session clock has
   advanced 4.0 s (± one frame) and the clock stays continuous (no jump) at the moment of the change.
3. **Given** a session on seed 42, **When** the viewer presses New seed, **Then** a new session starts with a seed in
   1–9999 that differs from 42, a different `match_id`, and a feed that differs from seed 42's.
4. **Given** a session at session time 30 s, **When** a client sends `{"action":"seek","to_ms":12000}`, **Then** the
   server state contains exactly the records with `session_clock_ms ≤ 12000`, every connected client receives one fresh
   `snapshot`, and no per-record `event`/`frame` messages are broadcast for the skipped records.
5. **Given** the session controls, **When** the viewer selects "Skeleton fixture" and presses Start, **Then** the 001
   card "Blue 8 played a forward pass to Blue 11 (13.1 m forward)." appears as before (001 e2e still green).

---

### User Story 3 - Scenario library with negatives and missing data (Priority: P2)

The builder can generate every family — `space_creation`, `press_turnover`, `switch_escape`, the negatives
`run_no_channel`, `press_no_turnover`, `switch_closed`, and the missing-data fixture `tracking_gap` — for development
variants A–C and any development seed. Each output passes plausibility validation and its scenario-intent check, so 003 can
test that positives are detected and negatives are not.

**Why this priority**: Positives without negatives cannot show that metrics discriminate; the missing-data fixture is a
required failure mode (constitution V) and a demo beat (1:13–1:28).

**Independent Test**: Parametrized tests over all 7 families × variants A–C × seeds 1–5 run `validate_output` (zero issues)
and the family's intent check from data-model.md "Scenario intent checks".

**Acceptance Scenarios**:

1. **Given** any family in {space_creation, press_turnover, switch_escape} with a dev variant and seed, **When** generated,
   **Then** its positive intent check passes (e.g. press_turnover: pressure proxy on the losing carrier ≥ 40 within 3 s
   before a Blue interception, tackle won or ball recovery).
2. **Given** any negative family, **When** generated, **Then** its negative intent check passes (run_no_channel: diagonal run
   present but lane clearance gain ≤ 1.0 m; press_no_turnover: pressure ≥ 40 and no turnover within 5 s; switch_closed:
   |Δy| ≥ 30 m switch whose receiver has a defender within 3.5 m at reception and loses a tackle within 2 s).
3. **Given** `tracking_gap` seed 42 variant A, **When** generated, **Then** `blue-09`, `amber-03`, `amber-04` and `amber-05`
   have `visible = false` and no `pos_m` in every frame from 1000 ms before the run starts to 500 ms after the forward pass,
   the ball stays visible, and all other records equal those of `space_creation` seed 42 variant A, except `match_id` and
   the `visible` flags.
4. **Given** `tactistream-sim list`, **When** run, **Then** it prints all 8 scenarios (7 families + `demo_match`), their
   variants per split, and seed ranges.

---

### User Story 4 - A 4–5 minute demo match (Priority: P2)

Selecting "Demo match" plays one continuous synthetic match of 4–5 minutes that contains the three positive patterns and the
three negatives in a fixed order, stitched by neutral circulation, restarts and repositioning, with the hero space-creation
sequence first so the opening card appears within the first ~15 s.

**Why this priority**: A judge needs a single playable match, not a menu of 14-second clips; the timeline and recap (005/006)
need several moments in one match.

**Independent Test**: Generate `demo_match` seed 42 variant A; assert duration 240–300 s, segment order from the manifest,
zero validation issues across segment boundaries, and per-segment intent checks.

**Acceptance Scenarios**:

1. **Given** `demo_match` seed 42 variant A, **When** generated, **Then** `match_id = demo-blue-amber-002`, the final event is
   `period_end` at a `session_clock_ms` in [240000, 300000], and the manifest lists segments in the order of data-model.md
   "Demo match program".
2. **Given** the demo match, **When** validated, **Then** no player exceeds 9.5 m/s or 6 m/s² anywhere, including the
   repositioning intervals between segments, and the ball is invisible during dead-ball intervals until 1.0 s before each
   restart.
3. **Given** the first segment of `demo_match` seed 42 and `space_creation` seed 42 variant A, **When** compared, **Then**
   their events and frames are identical except for `match_id`.
4. **Given** `demo_match` seed 42 variant A, **When** 003's `detect_moments` + unpinned `rank` run over the full match,
   **Then** there are ≥ 3 moments and the rank-1 moment has no `blue-09` in `involved_player_ids` (needed by 006 SC-002:
   pinning Blue 9 must visibly change the top moment). Segment parameters are tuned until this holds; the test lives in
   `backend/tests/integration/test_demo_match_moments.py` and is added when 003's ranking lands.

---

### User Story 5 - Held-out evaluation split with structural variants (Priority: P3)

The evaluator generates held-out scenarios with seeds ≥ 10000 and variants D–F, which change structure (attacking team,
period/attack direction, mirrored side, key actors, number of build-up passes, tempo, a decoy run), not just noise. The tool
refuses to mix splits so evaluation data cannot leak into development.

**Why this priority**: The build plan requires separate dev/eval seeds and structurally varied evaluation; 008 consumes it.
Lower priority because nothing user-facing depends on it before 22 Oct.

**Independent Test**: CLI tests for each refusal case (exit code 2) and generation of every family × D–F × seeds
10000–10002 with zero validation issues and passing intent checks.

**Acceptance Scenarios**:

1. **Given** `--split dev --seed 10000`, **When** generating, **Then** the CLI exits 2 with
   `error: seed 10000 is reserved for split=eval` and writes nothing.
2. **Given** `--split dev --variant D`, **When** generating, **Then** the CLI exits 2 with
   `error: variant D is reserved for split=eval`.
3. **Given** `--split eval --seed 42`, **When** generating, **Then** the CLI exits 2 with
   `error: split=eval requires seed >= 10000`.
4. **Given** `space_creation --split eval --seed 10000 --variant D`, **When** generated, **Then** the focus team (Blue)
   attacks −x in period 2, metadata lists both periods with Blue `-1` in period 2, the runner is `blue-10`, and the run
   still satisfies the positive intent check after attack-direction normalization.
5. **Given** an eval output, **When** its `match_id` is inspected, **Then** it is opaque (`sim-` + 10 hex chars) and does
   not contain the scenario name, seed or variant.

### Edge Cases

- Seed outside 1–9999 for `split=dev`, < 10000 for `split=eval`, or > 2^31 − 1 → `ConfigError` (CLI exit 2, API 422 `invalid_seed`).
- Unknown scenario → CLI exit 2 listing valid names; API 422 `invalid_scenario`.
- `--out` exists and is not empty → exit 2 unless `--force`; files are written to a temp dir and moved only after validation passes.
- A scenario script needing a trajectory beyond 9.5 m/s or 6 m/s² → `KinematicsError(player_id, t_ms, speed, accel)`, generation
  fails (exit 3). The generator never silently clamps a scripted actor.
- `validate_output` finds any issue in a generated output → exit 3, issues printed one per line (`code record_id detail`), nothing written.
- Invisible player at an event time (tracking_gap) → event coordinates are still emitted from the event stream; the
  coordinate-vs-frame check skips that pair and counts it in `ValidationReport.unchecked`.
- Seek beyond the feed duration → clamps to the end; state becomes `ended`. Negative `to_ms` → 422 `invalid_action`.
- Speed not in {0.5, 1, 2} → 422 `invalid_action`; speed change while paused is stored and applies on play.
- New seed collides with the current seed → frontend re-draws until different.
- `{"scenario":"skeleton","seed":7}` → 422 `invalid_seed` (skeleton is fixed at seed 42); variants other than A for skeleton → 422 `invalid_variant`.
- API asked for an eval variant or eval seed → 422 `eval_split_not_served` (eval data is generated by CLI only).
- A ninth concurrent session → least-recently-used session with no connected WebSocket is stopped; if all eight have viewers → 429 `too_many_sessions`.
- Same (scenario, seed, variant) requested twice → the existing session is returned (`"shared": true`); viewers share playback.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide `simulate(config: SimulationConfig) -> SimulationOutput` (metadata, events, frames, manifest) in `tactistream.simulator.engine`, with no model calls and no I/O.
- **FR-002**: `SimulationConfig` MUST carry `seed`, `scenario`, `variant` (A–F), `split` (`dev` | `eval`) and `generator_version = "0.1.0"`; it MUST reject dev seeds outside 1–9999, eval seeds < 10000, variants D–F with `split=dev` and A–C with `split=eval`.
- **FR-003**: All randomness MUST come from `numpy.random.Generator(PCG64(SeedSequence([seed, segment_index])))`; identical configs MUST produce byte-identical `feed.jsonl` and `manifest.json` (canonical JSON: sorted keys, compact separators, UTF-8, floats rounded to 0.01 m / whole ms).
- **FR-004**: Output MUST use the 105 × 68 m pitch, origin bottom-left, 10 Hz frames (`frame_interval_ms = 100`), frame indices contiguous from 0, event sequences contiguous from 1, event times on the 100 ms grid, Blue attacking +x in period 1, and all 22 roster player IDs in every frame.
- **FR-005**: Rosters MUST be the fictional Blue/Amber 11-player squads from `contracts/examples/match_metadata.json` (4-3-3 roles), with base formations per team and phase.
- **FR-006**: Every event sequence MUST be produced through the possession state machine in `simulator/possession.py`; any event not allowed by the legal-transition table in data-model.md raises `IllegalTransition` at generation time.
- **FR-007**: Player trajectories MUST respect max speed 9.5 m/s and max acceleration 6 m/s²; the ball MUST stay within 0.5 m of the carrier while controlled and move linearly from `start_m` to `end_m` during passes at 8–25 m/s.
- **FR-008**: Unavailable entities MUST be emitted with `visible = false` and no `pos_m`; the generator never fabricates positions. During dead-ball intervals the ball is invisible until 1000 ms before the restart.
- **FR-009**: System MUST implement scenario families `space_creation`, `press_turnover`, `switch_escape`, `run_no_channel`, `press_no_turnover`, `switch_closed`, `tracking_gap` (one module each under `simulator/scenarios/`) plus the program filler `circulation`, each satisfying its intent check in data-model.md for every supported variant and seed.
- **FR-010**: Variants MUST change structure per the variant table in data-model.md (focus team, period/attack direction, y-mirror, key-actor set, build-up passes, time scale, decoy run); A–C are dev, D–F are eval.
- **FR-011**: `MatchProgram` MUST stitch segments into scenario `demo_match` (4–5 min) in the fixed order in data-model.md, ending each segment with a dead ball, inserting kinematically feasible repositioning (≥ 3000 ms) and a restart, and ending with `period_end`.
- **FR-012**: `GenerationManifest` (segment labels, expected pattern, key players, key event IDs, intended explanation, tracking gaps, output SHA-256) MUST be written only to `manifest.json`, never published on a `FeedBus`, never loaded by the API, and never imported by `state/`, `metrics/`, `moments/`, `agents/`, `narrative/` or `api/` modules (enforced by an import-scan test).
- **FR-013**: Match IDs MUST be `demo-blue-amber-001` for (space_creation, 42, A, dev), `demo-blue-amber-002` for (demo_match, 42, A, dev), and otherwise opaque `sim-{sha256(config)[:10]}` so scenario labels never reach agents through IDs.
- **FR-014**: `validate_output(output) -> ValidationReport` MUST check schema validity, speed ≤ 9.5 m/s (+0.15 tolerance, 1-frame step), acceleration ≤ 6 m/s² (+0.5 tolerance, 200 ms second difference), ball-to-carrier ≤ 0.5 m, ball-to-passer at pass start and ball-to-receiver at completed-pass end ≤ 0.5 m, pass ball speed 8–25 m/s, event coordinates within 1.0 m of the actor's frame position, legal transitions, attack-direction consistency, contiguity and roster completeness; `generate` MUST fail on any issue.
- **FR-015**: `tactistream-sim generate --scenario --seed --variant --split --out [--force]` MUST write `feed.jsonl` + `manifest.json` and print counts and the feed SHA-256; `tactistream-sim list` MUST print scenarios, variants per split and seed ranges. Exit codes: 0 ok, 2 usage/config error, 3 generation/validation failure.
- **FR-016**: `POST /api/sessions` MUST accept `{"scenario": "skeleton"}` or `{"scenario": <name>, "seed"?: int = 42, "variant"?: "A"|"B"|"C" = "A"}`, serve only the dev split, return `session_id`, `match_id`, `ws_path`, `scenario`, `seed`, `variant`, `duration_ms`, `shared`, and reuse an existing session for an identical config.
- **FR-017**: `GET /api/scenarios` MUST list selectable scenarios with display names, dev variants, default seed 42 and duration.
- **FR-018**: `FeedReplayer` MUST add `set_speed(speed)` for {0.5, 1.0, 2.0} with a continuous session clock, `seek(to_ms)` (forward: publish skipped records as a burst; backward: rewind via `on_rewind` then burst), `duration_ms`, and re-stamp `published_ms` with an injectable wall clock at publish time.
- **FR-019**: `POST /api/matches/{id}/control` MUST support `speed` and `seek`; during a seek burst the session MUST suppress per-record WS broadcasts and send one fresh `snapshot` when the burst has been applied.
- **FR-020**: Frontend MUST add `SessionControls.tsx` with scenario selector, seed input (1–9999), New seed button, and speed control (0.5×/1×/2×), keyboard-operable with visible labels; existing playback controls keep working.
- **FR-021**: `SessionRegistry` MUST hold at most 8 sessions (setting `TACTISTREAM_MAX_SESSIONS`), evicting the least-recently-used session without connected viewers, else 429 `too_many_sessions`.
- **FR-022**: Simulator outputs MUST be cached per config in the API process (LRU, 8 entries) so New seed / reconnect does not regenerate a known config.

### Key Entities

- **SimulationConfig**: seed, scenario, variant, split, generator_version; derives `match_id`.
- **SimulationOutput**: `MatchMetadata`, ordered `MatchEvent`s, ordered `TrackingFrame`s, and a `GenerationManifest` kept apart from the feed.
- **GenerationManifest**: ground-truth labels for evaluation only (segments, expected pattern, key players, key events, intended explanation, gaps, feed hash).
- **PossessionState**: phase (`dead`, `controlled`, `in_flight`, `loose`, `ended`), team, player — the state machine that makes event sequences legal.
- **VariantSpec**: structural parameters for A–F.
- **MatchProgram / Segment**: ordered scenario segments with restarts that form `demo_match`.
- **ValidationReport / ValidationIssue**: plausibility findings (`code`, `record_id`, `detail`) and `unchecked` count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Generating the same config twice yields byte-identical files for 100% of the 7 × 3 dev (family, variant) pairs at seed 42; `space_creation/42/A` and `demo_match/42/A` feed hashes equal the committed goldens in CI.
- **SC-002**: `validate_output` reports zero issues for 7 families × 6 variants × 5 seeds (210 outputs) in default CI and × 100 seeds (4,200 outputs) in the `slow` suite, plus `demo_match` seeds 1–20.
- **SC-003**: Intent checks pass for 100% of the same 210 (default) / 4,200 (slow) outputs.
- **SC-004**: With `FakeClock`, a record with session time T is published exactly when the session clock reaches T at speeds 0.5, 1 and 2; Playwright `simulator.spec.ts` passes 5/5 consecutive runs.
- **SC-005**: 100% of split-mixing attempts are rejected (CLI exit 2, API 422), and the import-scan test finds zero imports of `simulator.manifest` outside `simulator/`, `eval/` and tests.
- **SC-006**: On the Codespace (4 vCPU), `simulate` takes ≤ 0.5 s for any single family and ≤ 3 s for `demo_match` (median of 5, recorded in research.md); `POST /api/sessions` for an uncached `demo_match` responds in ≤ 4 s.

## Assumptions

- The 001 walking skeleton (contracts, `FeedReplayer`, `MatchSession`, `SessionRegistry`, WS hub, frontend shell) is merged; this feature extends it without renaming any interface.
- Scenarios never contain goals (shot outcomes are `on_target` parried, `off_target` or `blocked`, each followed by `out_of_play`), so no post-goal kickoff logic is needed; each standalone scenario starts with a kickoff at session time 0 and ends with `period_end`.
- `period_clock_ms = 840000 + session_clock_ms` within a standalone scenario (period clock restarts at 0 each period; scenarios are placed at 14:00); `demo_match` is entirely period 1.
- `team_id`/`player_id` on `out_of_play` is the last-touch player, and on `period_end` the player in possession (or the last actor), because the event schema requires both.
- Sessions are shared per config ("a match everyone watches"): any viewer's pause/seek/speed affects all viewers of that match. Acceptable for ≤ 10 judges on one replica; recorded in docs as an MVP limitation.
- Seek is exposed by the API now and used by 005's timeline; 002's UI has no scrubber.
- Floating-point determinism is guaranteed on the CI/Codespace platform (x86-64 Linux, pinned NumPy); outputs are rounded to 0.01 m to absorb last-bit differences. Any output change for an existing config requires bumping `generator_version` and the goldens in the same commit.
- Contract examples (`evt-0042` etc.) stay illustrative; the simulator's hero sequence uses its own sequence numbers and is frozen by the golden hash, not by the examples.
- Display names in the scenario selector name the scripted family openly (e.g. "Space creation (scripted)") — honest to viewers; labels only must not reach agents.
