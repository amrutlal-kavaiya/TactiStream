# Feature Specification: Evaluation Evidence — measure the claims judges can challenge

**Feature Branch**: `008-evaluation-evidence`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan, "Measure the claims that judges can challenge" and "Treat reliability as part of the demonstration";
constitution VI ("Measure, don't claim"). Roadmap exit (22–23 Oct): held-out evaluation, failure fixtures, three-way agent
comparison, latency/fps/economics measured; `/evidence` page shows honest results.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compare deterministic, single-agent and three-agent outputs on identical frozen inputs (Priority: P1)

The builder freezes ~30 held-out scenarios (eval seeds ≥ 10000, variants D–F) into input files that contain only what an
agent may see, then runs four configurations — `deterministic`, `single_agent`, `three_agent`, `three_agent_fixed_tokens` —
over exactly those inputs. Each run writes every claim, insight packet, usage figure, latency and fallback to
`eval/results/<run_id>/outputs.jsonl`. Automatic scoring reports useful coverage on positives, false-explanation rate on
negatives, abstention correctness on missing-data cases, deterministic-check pass rate, latency, tokens, calls and cost per
match and per validated story, and recovery on injected failures.

**Why this priority**: The "Best Multi-Agent System" claim stands or falls on this comparison. If three agents cost more without
a quality gain, the report must say so and the claim is narrowed.

**Independent Test**: `make eval-smoke` freezes 3 scenarios and runs all four configs with `ScriptedModelClient`; outputs validate
against the `OutputRecord` model and `tactistream-eval score` produces per-config scores. Re-running produces byte-identical
frozen inputs and identical scores.

**Acceptance Scenarios**:

1. **Given** `eval/scenarios/heldout.yaml`, **When** `tactistream-eval freeze --set heldout` runs twice, **Then** the
   `eval/frozen/heldout/*.json` files are byte-identical across runs and their SHA-256 values are listed in
   `eval/frozen/heldout/MANIFEST.json`.
2. **Given** frozen inputs, **When** inspected by the label-leak test, **Then** no frozen input contains the scenario family,
   expected outcome, variant letter, generation manifest fields, or a `match_id` containing a family name (match ids are
   rewritten to `eval-{scenario_id}`).
3. **Given** the four configs, **When** `tactistream-eval run --config eval/configs/<cfg>.yaml --set heldout` completes, **Then**
   every frozen moment has exactly one `OutputRecord` per config — including timeouts and fallbacks — and `run.json` records git
   commit, model deployment, region, start/end time and failure counts.
4. **Given** a completed run, **When** `tactistream-eval score` runs, **Then** it re-executes deterministic output checks on every
   released packet against the frozen snapshot and reports the pass rate; any failure is listed by `insight_id`.
5. **Given** `three_agent` costs more tokens than `single_agent` without a support-rate or useful-coverage gain outside the 95%
   intervals, **When** the report is built, **Then** it states this verbatim in the comparison section and `limitations`.

---

### User Story 2 - Every enumerated failure degrades usefully (Priority: P1)

A failure-fixture suite drives the real session pipeline (in-memory bus, fake clock, scripted model) through missing positions,
late events, duplicated events, model timeout, bad claim, reconnect and history unavailability, and asserts the specific
WebSocket messages and UI-visible outcomes for each. The suite runs in CI and its JUnit result feeds the "Failure handling"
release gate.

**Why this priority**: Failure handling is a release gate and a demo beat (1:13–1:28). It is cheap, deterministic and protects
every later change.

**Independent Test**: `uv run pytest backend/tests/integration/test_failure_fixtures.py --junitxml=eval/results/fixtures-junit.xml`
passes; each fixture asserts its outcome table row.

**Acceptance Scenarios**:

1. **Given** the `tracking_gap` scenario, **When** the space-creation moment is explained, **Then** the event card is released,
   the spatial explanation is replaced by `claim_status = insufficient_data` with text "Insufficient tracking for this
   explanation", the related metric has `status = unavailable`, and no annotation references a missing player.
2. **Given** an insight released on facts later revised by a late event, **When** the late event arrives, **Then** an
   `insight_revoked {reason: late_event_revision}` is sent, the revised bundle (new `insight_version`) or no card replaces it,
   and pass counts equal the in-order run.
3. **Given** every envelope is delivered twice, **When** the match completes, **Then** the state hash equals the clean run and
   each moment produces exactly one insight bundle.
4. **Given** `POST /api/matches/{id}/fixtures {"inject":"model_timeout"}`, **When** the next moment is explained, **Then**
   `narrative_status {stage: fallback, fallback_reason: timeout}` arrives no later than deadline + 250 ms, a `fallback_template`
   card is released, and `event` messages keep flowing during the wait (fast path unaffected).
5. **Given** `{"inject":"bad_claim"}`, **When** the Analyst emits a claim with a changed value, **Then** the Verifier rejects or
   the output check blocks it, the trace shows the rejected claim with its reason code, and no released packet contains the bad
   number.
6. **Given** the WebSocket drops after seq K, **When** the client resumes, **Then** it receives a fresh snapshot, no event appears
   twice, and the active insight is preserved.
7. **Given** the history store times out, **When** a moment is explained, **Then** the workflow completes without history and the
   card is released or falls back within the deadline.

---

### User Story 3 - Blind review of atomic claims with honest support rates (Priority: P1)

The reviewer runs `tactistream-eval review`, which serves a local page showing one atomic claim at a time with its evidence records
(resolved values, timestamps, coordinates) and a link to a 2D replay of the evidence window. The configuration that produced the
claim is hidden and the order is randomized. The reviewer labels each claim **supported**, **unsupported** or **unclear** with an
optional note. An optional second reviewer labels an overlapping subset, and disagreement is reported.

**Why this priority**: "≥ 95% supported claims on the reviewed set" is a release gate; without blinding and counts it is not
credible.

**Independent Test**: With a 10-item review set built from scripted outputs, a Playwright test labels all items through the page;
`labels.<reviewer>.jsonl` holds 10 lines, the served HTML never contains a config id, and `score` reports support counts per config.

**Acceptance Scenarios**:

1. **Given** outputs from four configs, **When** `tactistream-eval review build --sample 150 --seed 7` runs, **Then** it samples up
   to 150 atomic claims stratified by config (all claims if fewer), assigns opaque item ids, and writes the config mapping only to
   `eval/review/<review_id>/key.json`, which the server never serves.
2. **Given** the review page, **When** the reviewer presses `S`, `U` or `C` (or clicks), **Then** the label is appended to
   `labels.<reviewer>.jsonl` and the next item loads; reloading resumes at the first unlabeled item.
3. **Given** two reviewers labeled ≥ 30 shared items, **When** scoring runs, **Then** raw agreement, Cohen's κ and the list of
   disagreements are reported; the gate uses the primary reviewer's labels and reports the second reviewer's rate alongside.
4. **Given** no football expert reviewed, **When** the report is rendered, **Then** the review is labelled "internal review" and
   never "expert validated".

---

### User Story 4 - Measure live latency, replay consistency and frame rate (Priority: P2)

The builder measures, against the deployed app, fast-overlay and narrative latency with 10 simultaneous WebSocket viewers on one
match; replay consistency over 20 shuffled/duplicated deliveries; and replay frame rate on a named demo machine with a Playwright
performance script. Each measurement writes a JSON result with sample sizes, hardware, browser and network description.

**Why this priority**: These are four of the eight release gates; they need the deployed app (007) and the replay (005), so they
come after the offline evaluation.

**Independent Test**: `tactistream-eval load --base-url http://localhost:8000 --viewers 3 --duration-s 20` against a local app
produces a `LoadResult` with fast-overlay and narrative samples; `tactistream-eval consistency --runs 5` reports one distinct hash.

**Acceptance Scenarios**:

1. **Given** the deployed app, **When** `tactistream-eval load --viewers 10 --seed 42` runs, **Then** 10 WebSocket clients join
   one match, send `display_ack` for every event and insight they receive, and the result reports per-kind n, p50, p95, max,
   fallback count and timeout rate, computed from server-side samples (`GET /api/diagnostics/latency`), with fallbacks included.
2. **Given** a real browser viewer also open during the load run, **When** the run ends, **Then** its samples are reported as a
   separate "browser display" row so synthetic-client acks are not passed off as rendered displays.
3. **Given** seed 42, **When** `tactistream-eval consistency --runs 20` runs with per-run shuffling (bounded displacement ≤ 3) and
   10% duplication, **Then** all 20 metric state hashes are identical, or the report lists distinct hashes and the first differing
   metric.
4. **Given** the named demo machine, **When** `npm run perf:fps` runs `frontend/tests/perf/replay-fps.spec.ts` headed, **Then** it
   replays the hero Why Mode window three times, records median fps, 5th-percentile fps and long frames (> 50 ms) per run, and
   writes `eval/results/perf/fps-<machine>.json` with CPU, GPU, RAM, OS, browser name/version, viewport and device pixel ratio.

---

### User Story 5 - Judges read honest results on the Evidence page (Priority: P2)

A judge selects **Evidence** in the top bar (route `/evidence`) and sees the release-gates table (target, measured value,
pass/fail/not measured, sample size, method), the agent comparison, latency and economics, sample sizes, the measured environment
(app region, model deployment and region, demo machine, network) and limitations. The same content is rendered to
`docs/results.md`.

**Why this priority**: Published evidence is what turns measurements into judging value; it depends on US1–US4 results but can be
built and tested with a fixture report.

**Independent Test**: With `eval/results/latest/report.json` set to the committed fixture report, `GET /api/evaluation/results`
returns it, and the Vitest + Playwright tests assert the page shows all eight gates, sample sizes, the "internal review" label
and limitations.

**Acceptance Scenarios**:

1. **Given** a valid report, **When** a judge opens `/evidence`, **Then** the gates table lists exactly the eight build-plan gates
   in order with status chips (pass, fail, not measured) that use text, not colour alone.
2. **Given** a gate was not measured, **When** shown, **Then** it reads "Not measured" with the reason; it never shows a target as
   a result.
3. **Given** no report file, **When** the API is called, **Then** it returns 404 `report_not_found` and the page says "Results not
   published yet" with a link to `docs/results.md` in the repository.
4. **Given** the top bar, **When** a judge activates "Evidence" (mouse or keyboard), **Then** `/evidence` opens and "Back to match"
   returns to the previous view without losing the session.

### Edge Cases

- A config errors on a moment (exception, invalid JSON) → recorded as `status = fallback`, `fallback_reason = model_error`, latency
  counted; never skipped.
- Foundry throttling (429) during a held-out run → the runner retries per the model client's policy within the deadline; if the
  deadline passes it is a timeout. A run with > 10% `model_error` is marked `degraded` in `run.json` and the report says so.
- Re-running the held-out set after prompt changes → allowed only with a new run id; the report lists every held-out run id per
  config and uses the latest complete run, with the count of runs disclosed (no cherry-picking).
- Fewer than 100 atomic claims are available → review all of them and state the number; the support gate shows its sample size.
- Reviewer labels "unclear" → counted in the denominator of the gated support rate (conservative) and reported separately.
- A scenario produces no candidate moment → recorded as a scenario-level row with `moments = 0`; for positives this counts as not
  covered.
- Clock skew between load clients and server → all latency values are server-side (`ack_received_ms − receipt_ms` on the server
  clock); clients only send acks.
- fps capture on a hidden/background tab → the script fails the run (document visibility checked) instead of recording throttled
  frames.
- Report built while some gates lack inputs → those gates are `not_measured` with a reason; the page still renders.
- Pricing unknown for the deployed model → cost columns show "not priced" while tokens/calls are still reported.

## Requirements *(mandatory)*

### Functional Requirements

**Scenario sets and freezing**

- **FR-001**: `eval/scenarios/heldout.yaml` MUST define 30 scenarios with `split: eval`, seeds ≥ 10000 and variants D–F: 18 positives
  (space_creation, press_turnover, switch_escape × variants D, E, F × 2 seeds), 9 negatives (run_no_channel, press_no_turnover,
  switch_closed × D, E, F) and 3 missing-data cases (`tracking_gap` × D, E, F). Each entry: `scenario_id` (`ho-01`…`ho-30`),
  `scenario`, `seed`, `variant`, `expect ∈ {positive, negative, missing_data}`.
- **FR-002**: `eval/scenarios/dev.yaml` MUST define ≥ 12 scenarios with `split: dev`, seeds 1–9999, variants A–C across all families
  (used for prompt/template iteration and the fixed-token budget); `load_scenario_set` MUST reject a held-out entry with a dev seed or
  variant and vice versa, and reject any seed appearing in both sets.
- **FR-003**: `eval/frozen.py` MUST simulate each scenario with 002's `simulate(SimulationConfig(seed, scenario, variant, split))`, feed
  records through 003's ingest, `MetricEngine` and `detect_moments`, and write `eval/frozen/<set>/<scenario_id>.json` (`FrozenScenario`)
  holding metadata, events, frames within ±15 s of each moment, moments, per-moment as-of snapshots and metric results — with
  `match_id` rewritten to `eval-{scenario_id}` in every record — plus `MANIFEST.json` (file SHA-256, generator version, git commit).
- **FR-004**: Scorer-only labels (`family`, `expect`, `variant`, the generation manifest's intended pattern and key event ids) MUST be
  written to `eval/labels/<set>.json`, separate from frozen inputs; the runner MUST NOT open the labels directory (enforced by a test
  that runs the runner with the labels directory unreadable).
- **FR-005**: Freezing MUST be deterministic: two runs yield byte-identical files (canonical JSON, sorted keys, no timestamps inside
  frozen inputs).

**Configurations and runner**

- **FR-006**: `eval/configs/{deterministic,single_agent,three_agent,three_agent_fixed_tokens}.yaml` MUST define `config_id`,
  `kind ∈ {deterministic, single_agent, three_agent}`, `model ∈ {scripted, foundry}`, `deadline_ms` (8000), `token_budget`
  (`null` or integer), `temperature` (0), and `repeats` (1).
- **FR-007**: `kind = deterministic` MUST use 004's `agents/baselines.deterministic_summary` (no model calls); `single_agent` MUST use
  `agents/baselines.single_agent` with the same read-only tools; `three_agent` MUST use `agents/workflow.explain_moment`; all receive
  only the `FrozenMoment` (snapshot, metrics, moment) and identical tool access.
- **FR-008**: `tactistream-eval budget --from-run <dev single_agent run>` MUST set `three_agent_fixed_tokens.token_budget` to the median
  total tokens per moment of that run and write it into the config file with the source run id; the workflow MUST fall back when the
  budget would be exceeded (004 `WorkflowContext.token_budget`).
- **FR-009**: `tactistream-eval run --config <yaml> --set heldout [--model foundry|scripted] [--inject-every N]` MUST process every frozen
  moment sequentially with the configured deadline, write one `OutputRecord` per moment to `eval/results/<run_id>/outputs.jsonl` and
  `run.json` (`RunManifest`); `run_id = {config_id}-{set}-{UTC yyyymmddTHHMMSS}`.
- **FR-010**: With `--inject-every N` the runner MUST inject alternately `bad_claim` and `model_timeout` (004 fixtures) on every Nth
  moment and mark those records `injected_fixture`, so recovery is measured on the same inputs for all model configs.
- **FR-011**: Every record MUST include status (`released | fallback | abstained`), `fallback_reason`, released packets, atomic claims
  (claim id, kind, template id, rendered English analyst text, evidence ids, verifier decision if any), check failures, usage
  (`model_calls`, `input_tokens`, `output_tokens` per agent), `latency_ms` and `trace_id`.

**Review**

- **FR-012**: `tactistream-eval review build --runs <run_id>… --sample N --seed S` MUST create `eval/review/<review_id>/{items.json,key.json}`;
  items contain only opaque `item_id`, claim text, claim kind label (Fact / Interpretation), resolved evidence and replay window; `key.json`
  maps `item_id → (run_id, config_id, scenario_id, claim_id)`.
- **FR-013**: `tactistream-eval review serve --review <review_id> --reviewer <name> [--port 8765]` MUST serve the page (127.0.0.1 only), show
  items in a per-reviewer seeded random order, provide keyboard shortcuts S/U/C, optional note, progress count, and a replay link that
  opens a 2D top-down animation of the frozen frames for the evidence window (no scenario names, families or config ids anywhere in served
  content).
- **FR-014**: Labels MUST be appended to `eval/review/<review_id>/labels.<reviewer>.jsonl` (`item_id, label, note, reviewer, labeled_at`);
  the last label per item wins.

**Scoring**

- **FR-015**: `eval/score.py` MUST compute per config, using scorer-only labels: useful coverage (positives with ≥ 1 released interpretation
  claim whose template belongs to the scenario family in `eval/configs/family_templates.yaml`, and — on the reviewed subset — labelled
  supported), false-explanation rate (negatives with a released interpretation claim of the family's positive template), abstention
  correctness (missing-data cases where no spatial interpretation was released **and** the event-level card was released), deterministic
  check pass rate on released packets, reviewed support rate = supported / (supported + unsupported + unclear) with Wilson 95% interval,
  plus supported / (supported + unsupported) shown separately.
- **FR-016**: Latency scoring MUST report p50, p95 and max over all moments **including** fallbacks and timeouts, the released-only
  p50/p95 separately, and the timeout rate; no record may be excluded.
- **FR-017**: Economics MUST report per match and per validated story (released with supported or verified-fact status): model calls,
  input/output tokens, runner compute seconds, and cost computed from `eval/configs/pricing.yaml` (price per 1M tokens, source URL,
  retrieval date), labelled "list-price estimate"; plus deployed-app measurements from 007 (Event Hubs envelopes and bytes per match,
  Blob bytes written, container vCPU-seconds, Fabric capacity CU as read from the Fabric Capacity Metrics app).
- **FR-018**: Recovery MUST be reported per config on injected records: share ending in a released supported card or a fallback template
  within the deadline with zero released packets containing the injected bad value.
- **FR-019**: Agreement MUST report shared item count, raw agreement and Cohen's κ (3 labels) when a second reviewer exists.

**Failure fixtures**

- **FR-020**: `backend/tests/integration/test_failure_fixtures.py` MUST implement the seven fixtures of US2 with the expected-outcome
  table in `research.md` R7 as assertions on WebSocket messages, REST responses and state hashes; CI MUST export JUnit XML that the report
  ingests.

**Live measurements**

- **FR-021**: `GET /api/diagnostics/latency?match_id=` MUST return the session's recorded `LatencySample`s (fast overlay and narrative, all
  outcomes) and viewer count; disabled when `TACTISTREAM_DIAGNOSTICS=off`.
- **FR-022**: `eval/load.py` MUST open N (default 10) concurrent WebSocket viewers on one match created with the given seed, ack every
  `event` and `insight` on receipt with `display_ack`, inject one `model_timeout` fixture mid-run, collect server samples at the end, and
  write `eval/results/perf/load-<timestamp>.json` (`LoadResult`) including client host, region of the client, median WebSocket RTT and
  the deployed app URL.
- **FR-023**: `eval/consistency.py` MUST run the hero scenario `runs` times through ingest + metrics with seeded shuffles (bounded
  displacement) and duplications, compute 003's metric state hash per run and report distinct hashes (target: 1).
- **FR-024**: `frontend/tests/perf/replay-fps.spec.ts` MUST measure frames via `requestAnimationFrame` deltas during three Why Mode replays
  of the hero moment, require `document.visibilityState === "visible"`, read machine description from `TACTISTREAM_DEMO_MACHINE`
  (name; CPU; GPU; RAM; OS) and fail if it is unset, and write the result JSON.

**Report and evidence page**

- **FR-025**: `eval/report.py` MUST build `EvaluationReport` (data-model.md) from the latest complete held-out run per config, review
  labels, fixture JUnit, load, consistency, fps and economics inputs; evaluate the eight release gates exactly as in the table below;
  write `eval/results/<report_id>/report.json`, copy to `eval/results/latest/report.json`, and render `docs/results.md`.
- **FR-026**: Each gate MUST carry `status ∈ {pass, fail, not_measured}`, measured value with unit, sample size, method and an
  `evidence_path` to the raw result file; a gate with missing inputs is `not_measured` with a reason.
- **FR-027**: `GET /api/evaluation/results` MUST return the latest report JSON (validated against `evaluation_report.schema.json`) or 404
  `{"error":"report_not_found"}`; responses carry `Cache-Control: no-cache`.
- **FR-028**: `frontend/src/routes/EvidencePage.tsx` at `/evidence` MUST show gates table, agent comparison table, latency table, economics,
  sample sizes, measured environment, review label (internal/expert), limitations, report id and generation date; the top bar MUST include an
  "Evidence" link; the page MUST meet the existing contrast and keyboard rules.
- **FR-029**: The report and page MUST state: synthetic data only; results describe this controlled environment, not professional-match
  accuracy; sample sizes; hardware; network; all failures.
- **FR-030**: If `three_agent` shows no useful quality gain over `single_agent` at higher cost, `report.py` MUST add a limitation
  "Three-agent workflow did not outperform a single agent with the same tools on this set" and set `comparison.claim_narrowed = true`
  (009 uses it to narrow the multi-agent claim).

**Release gates (verbatim from the build plan; targets are hypotheses until measured)**

| Measure | Proposed release gate | Measurement method |
|---|---|---|
| Fast overlay latency | p95 at or below 2 seconds | Server receipt to browser display acknowledgement |
| Narrative latency | p95 at or below 8 seconds, with timeout rate reported separately | Trigger receipt to validated narrative display; count fallback separately |
| Reference and numeric integrity | All released cards pass deterministic checks | Compare IDs, units and values against the frozen snapshot |
| Tactical support | Target at least 95% supported claims on the reviewed synthetic set | Blind manual review, with counts and disagreement reported |
| UI responsiveness | At least 30 fps on the named demo machine | Browser performance capture during replay |
| Replay consistency | Identical metric state for identical inputs | Repeat replay with shuffled/duplicated delivery |
| Failure handling | All enumerated failure fixtures degrade usefully | Missing positions, late events, model timeout, bad claim, reconnect |
| Economics | Measured usage per match and per validated story | Tokens, calls, compute time, storage, capacity and egress |

### Key Entities

- **ScenarioSpec / ScenarioSet**: one held-out or dev scenario definition; a set file.
- **FrozenScenario / FrozenMoment**: agent-visible, label-free inputs per scenario / per moment.
- **ScenarioLabel**: scorer-only family, expectation and key events.
- **EvalConfig**: one configuration under comparison.
- **OutputRecord / RunManifest**: one moment's output under one config; one run's metadata.
- **ReviewItem / ReviewLabel / AgreementStats**: blinded claim for review; a reviewer's verdict; inter-reviewer agreement.
- **ConfigScores**: aggregated quality, latency, economics and recovery per config.
- **LoadResult / ConsistencyResult / FpsResult**: live measurement outputs.
- **ReleaseGate / EvaluationReport**: one gate's evaluation; the published report.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 30 held-out scenarios are frozen with a manifest; the label-leak test passes; refreezing is byte-identical.
- **SC-002**: All four configs complete a held-out run with one record per frozen moment (0 missing), and the report shows per-config
  coverage, false-explanation, abstention, support, latency (incl. fallbacks) and cost.
- **SC-003**: At least 100 atomic claims are blind-reviewed (or all available claims, with the count stated), with the review label
  ("internal review" unless an expert reviewed) and, if a second reviewer exists, κ and disagreements.
- **SC-004**: The failure-fixture suite passes 7/7 in CI on three consecutive runs.
- **SC-005**: The deployed load test with 10 viewers yields ≥ 500 fast-overlay samples and ≥ 30 narrative samples, all included in the
  reported p95 values.
- **SC-006**: Consistency reports 20/20 identical metric state hashes (or the report shows the failure and the gate as fail).
- **SC-007**: fps is captured on one named demo machine with three runs and full hardware/browser description.
- **SC-008**: `/evidence` on the deployed app shows all eight gates with status, measured value and sample size; `docs/results.md`
  matches the served report (same `report_id`).
- **SC-009**: Every number on the evidence page traces to a file under `eval/results/` via its `evidence_path`.

## Assumptions

- 002 provides `simulate(config)`, `SimulationConfig(seed, scenario, variant, split)`, scenario families and negatives listed in FR-001,
  `tracking_gap`, dev/eval seed and variant ranges, and a `GenerationManifest` kept separate from the output records.
- 003 provides ingest, `MatchSnapshot`, `MetricEngine`, `detect_moments`, `state_hash` and a metric-state hash function; 004 provides
  `explain_moment`, `deterministic_summary`, `single_agent`, `AgentTrace`, `ScriptedModelClient`, `FoundryModelClient`, output checks and the
  fixtures endpoint; 005 provides Why Mode replay with an fps-capable scene; 007 provides the deployed app, `LatencySample` and App Insights.
- Review is done by the builder (internal review); a second reviewer is optional.
- Held-out runs use the deployed Foundry model; CI uses `ScriptedModelClient` only.
- The named demo machine is the laptop used to record the demo video (009).
