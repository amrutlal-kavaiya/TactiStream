---
description: "Task list for 008 evaluation evidence"
---

# Tasks: Evaluation Evidence

**Input**: `specs/008-evaluation-evidence/` (spec, plan, research, data-model, contracts/evaluation-api.md, quickstart)

**Tests**: REQUIRED (constitution V). Every module task is preceded by a failing test. Measurement tasks (runs, review, load,
fps) are executions whose outputs are committed under `eval/results/` and consumed by tested code.

**Format**: `[ID] [P?] [Story] Description` — `[P]` = parallelizable (different files, no unmet dependency).

## Phase 1: Setup

- [ ] T001 Add `pyyaml`, `jinja2` to `backend/pyproject.toml`, console script `tactistream-eval = tactistream.eval.cli:app`, package data `eval/review_templates/*`, `eval/report_templates/*`; update `uv.lock`
- [ ] T002 [P] Create `backend/src/tactistream/eval/__init__.py` and `eval/cli.py` typer app with stub commands `freeze`, `run`, `budget`, `score`, `review build`, `review serve`, `load`, `consistency`, `report` (each exits 2 "not implemented"); add `backend/tests/unit/eval/test_cli.py` asserting `--help` lists all commands
- [ ] T003 [P] Add Makefile targets `eval-smoke` (runs `backend/tests/integration/test_eval_smoke.py`), `eval-fixtures` (failure fixtures with JUnit to `eval/results/fixtures-junit.xml`); add CI step in `.github/workflows/ci.yml` running `make eval-smoke` and uploading `fixtures-junit.xml` as an artifact

---

## Phase 2: Foundational (blocks all stories)

- [ ] T004 Write failing `backend/tests/contract/test_evaluation_report.py`: `contracts/examples/evaluation_report.json` validates against `contracts/schemas/evaluation_report.schema.json` and round-trips through `EvaluationReport`; a report with 7 gates is rejected; a gate `status="not_measured"` without `reason` is rejected; `review_label` outside `{internal_review, expert_review}` rejected; `data_source` must be `synthetic`
- [ ] T005 Create `contracts/schemas/evaluation_report.schema.json` (draft 2020-12, `$defs` for Rate, LatencyStats, Economics, ConfigScores, LoadResult, ConsistencyResult, FpsResult, FixtureResult, ReleaseGate, MeasuredEnvironment, Comparison, AgreementStats), example `contracts/examples/evaluation_report.json` (plausible but clearly fake values, `report_id: rep-fixture`, `limitations` includes "Fixture report for tests — not a measurement"), and `backend/src/tactistream/contracts/evaluation.py`; regenerate TS types (`make contracts`); run T004 → green
- [ ] T006 [P] Write failing `backend/tests/unit/eval/test_scenarios.py`: `load_scenario_set` accepts valid sets; rejects held-out seed < 10000 or variant A–C, dev seed ≥ 10000 or variant D–F, duplicate `scenario_id`, unknown `scenario`; `check_disjoint(dev, heldout)` rejects a shared (scenario, seed, variant)
- [ ] T007 Implement `backend/src/tactistream/eval/models.py` (all internal models in data-model.md) and `eval/scenarios.py` (`load_scenario_set`, `check_disjoint`); run T006 → green
- [ ] T008 [P] Author `eval/scenarios/heldout.yaml` (30 entries exactly per FR-001: ho-01..ho-18 positives with seeds 10001–10018, ho-19..ho-27 negatives seeds 10101–10109, ho-28..ho-30 `tracking_gap` seeds 10201–10203) and `eval/scenarios/dev.yaml` (≥ 12 entries across all 7 scenario names, seeds 1–9999, variants A–C); add `backend/tests/unit/eval/test_scenario_files.py` asserting counts by `expect` (18/9/3), family × variant coverage, and disjointness

**Checkpoint**: report contract + scenario sets in place.

---

## Phase 3: User Story 1 — Three-way comparison on frozen inputs (P1) 🎯 MVP

**Goal**: identical label-free inputs, four configs, every moment recorded, automatic scores.

**Independent Test**: `make eval-smoke` (3 scenarios, scripted model, all configs) passes and is deterministic.

### Freezing

- [ ] T009 [P] [US1] Write failing `backend/tests/unit/eval/test_frozen.py`: `freeze_scenario(ScenarioSpec(ho-01, space_creation, 10001, D, positive))` returns a `FrozenScenario` whose every record has `match_id == "eval-ho-01"`, frames limited to ±15 s around moments, ≥ 1 moment with snapshot as-of == trigger time (no event after as-of inside the snapshot), and a `ScenarioLabel` with family `space_creation`; two calls produce identical canonical bytes; `input_sha256` matches recomputation
- [ ] T010 [P] [US1] Write failing `backend/tests/unit/eval/test_label_leak.py`: for frozen outputs of one scenario per scenario name, the canonical JSON contains none of: the 7 scenario names, `variant`, `expect`, `family`, `intended`, `manifest`, `label`, the variant letter as a standalone value, nor any 002 `GenerationManifest` field name (imported list)
- [ ] T011 [US1] Implement `backend/src/tactistream/eval/frozen.py` (`freeze_scenario`, `freeze_set(set_path, out_dir, labels_path) -> FreezeManifest`, `load_frozen(path) -> FrozenScenario`, `remap_match_id`, canonical JSON writer) and CLI `freeze --set`; run T009–T010 → green
- [ ] T012 [US1] Run `tactistream-eval freeze --set dev` and `--set heldout`; commit `eval/frozen/{dev,heldout}/`, `MANIFEST.json` and `eval/labels/{dev,heldout}.json`; rerun and confirm `git diff --exit-code eval/frozen` (SC-001)

### Configs and runner

- [ ] T013 [P] [US1] Write failing `backend/tests/unit/eval/test_configs.py` then create `eval/configs/{deterministic,single_agent,three_agent,three_agent_fixed_tokens}.yaml`, `eval/configs/family_templates.yaml`, `eval/configs/pricing.yaml` (price fields left empty until filled from the Azure pricing page on 22 Oct; `load_pricing` returns `None` for empty prices so costs show "not priced") and implement `backend/src/tactistream/eval/configs.py` (`load_config`, `set_token_budget(path, budget, source_run)`, `load_pricing`); test also asserts every template id in `family_templates.yaml` exists in `narrative/catalog/en.json`
- [ ] T014 [US1] Write failing `backend/tests/unit/eval/test_runner.py` (ScriptedModelClient, 2 frozen scenarios): each config writes one `OutputRecord` per frozen moment; `deterministic` has `model_calls == 0`; `single_agent` and `three_agent` receive the same `FrozenMoment` objects (spy) and the same tool list; a scripted timeout produces `status="fallback", fallback_reason="timeout"` with `latency_ms ≥ deadline_ms` and is written; an exception produces `fallback_reason="model_error"`; `--inject-every 2` alternates `bad_claim`/`model_timeout` and sets `injected_fixture`; killing after 1 record then resuming yields no duplicates; with `eval/labels/` made unreadable the run still completes (FR-004); `run.json` fields complete and `degraded` set when > 10% errors
- [ ] T015 [US1] Implement `backend/src/tactistream/eval/runner.py` (`ConfigRunner`, `runner_for`, `EvalContext` → 004 `WorkflowContext` with `InMemoryHistoryStore` from frozen events, `run_config`) and CLI `run`; record usage per agent from 004's `AgentTrace.usage`; run T014 → green
- [ ] T016 [P] [US1] Write failing `backend/tests/unit/eval/test_budget.py` then implement CLI `budget`: median total tokens per moment from a run's records (fallbacks included) written to the fixed-token config with `token_budget_source_run`; refuses a held-out run as source

### Scoring (automatic part)

- [ ] T017 [P] [US1] Write failing `backend/tests/unit/eval/test_stats.py`: `wilson(0,0)` → `None` interval and `Rate.value None`; `wilson(19,20)` ≈ (0.764, 0.991) ±0.001; `cohen_kappa` on identical labels = 1.0, on hand-computed 3×3 example equals expected value; `latency_stats` nearest-rank p95 of 1..100 = 95, includes fallback samples, reports released-only p95 separately, timeout rate as `Rate`
- [ ] T018 [P] [US1] Write failing `backend/tests/unit/eval/test_score.py` using a hand-built 6-scenario run (2 positive, 2 negative, 2 missing-data) with known outcomes: useful coverage 1/2, false-explanation 1/2, abstention correctness 1/2 (one case released a spatial claim), check pass re-run finds the one tampered packet (1 failure listed by `insight_id`), recovery on 2 injected records = 1/2, economics per match and per validated story match hand totals, cost uses `pricing.yaml` and is `None` when pricing absent
- [ ] T019 [US1] Implement `backend/src/tactistream/eval/score.py` (`wilson`, `cohen_kappa`, `latency_stats`, `score_run`, deterministic re-check via 004 `check_packet` against the frozen evidence index) and CLI `score` writing `eval/results/<run_id>/scores.json`; run T017–T018 → green
- [ ] T020 [US1] Write `backend/tests/integration/test_eval_smoke.py`: in a temp dir freeze ho-01, ho-19, ho-28; run 4 configs with scripted model; score; build a report (with US3–US5 inputs absent → those gates `not_measured`); assert all records present and the report validates; second execution produces identical `scores.json` (excluding timestamps)
- [ ] T021 [US1] (22 Oct) Run the dev `single_agent` run and `budget` (quickstart §3); then the four held-out runs with `--model foundry --inject-every 5` and `score` (quickstart §4); commit `eval/results/<run_id>/` folders; if any run is `degraded`, re-run once and keep both ids (disclosed in the report)

**Checkpoint**: comparison numbers exist for all four configs (or `three_agent_fixed_tokens` recorded as not run with reason).

---

## Phase 4: User Story 2 — Failure fixtures degrade usefully (P1)

**Goal**: seven deterministic fixtures asserting specific outcomes; JUnit feeds the gate.

**Independent Test**: `make eval-fixtures` passes 7/7.

- [ ] T022 [US2] Write `backend/tests/integration/test_failure_fixtures.py` scaffolding: fixture `session_harness` (create_app with InMemoryBus, FakeClock, ScriptedModelClient, history store injectable; WS test client collecting messages; helpers `play_until(ms)`, `messages_of(type)`) and parametrized ids for the 7 fixtures
- [ ] T023 [P] [US2] Add test `missing_positions` per research R7 (tracking_gap seed 42 variant A); run → record failure reason if red
- [ ] T024 [P] [US2] Add test `late_events` per R7 (custom bus wrapper delays one fact-changing event by 2 s on FakeClock)
- [ ] T025 [P] [US2] Add test `duplicated_events` per R7 (bus wrapper publishes each envelope twice with adjacent swaps; compares `state_hash` with clean run)
- [ ] T026 [P] [US2] Add test `model_timeout` per R7 (POST fixtures; asserts timing ≤ deadline + 250 ms and ≥ 1 `event` while pending)
- [ ] T027 [P] [US2] Add test `bad_claim` per R7 (asserts trace verdict/check failure and absence of the injected value in all released packets)
- [ ] T028 [P] [US2] Add test `reconnect` per R7 (close after seq K, resume, assert snapshot authority and unique events)
- [ ] T029 [P] [US2] Add test `history_unavailable` per R7 (history store sleeping 3 s; deadline met; no history numbers)
- [ ] T030 [US2] Fix any red fixture in the owning module (003 ingest/state, 004 workflow/checks, 001 ws) with a minimal change and a unit test in that module's test file; run `make eval-fixtures` 3× consecutively (SC-004); commit `eval/results/fixtures-junit.xml`

**Checkpoint**: failure-handling gate input exists.

---

## Phase 5: User Story 3 — Blind review (P1)

**Goal**: ≥ 100 blinded atomic claims labelled; support with intervals and agreement.

**Independent Test**: Playwright review e2e labels 10 items; blinding test passes.

- [ ] T031 [P] [US3] Write failing `backend/tests/unit/eval/test_review_build.py`: from 4 scripted runs, `build_review_set(runs, sample=8, seed=7)` returns 2 items per config (stratified), only released claims, opaque ids `rv-` + 10 hex stable across calls; `items.json` contains no config id, run id, scenario id, family or scenario name (string scan); `key.json` maps every item; sample larger than available → all claims
- [ ] T032 [US3] Implement `build_review_set` and CLI `review build` in `backend/src/tactistream/eval/review.py` (resolves evidence from frozen inputs: event type, players, coords, clocks; metric value + unit + definition version; replay window frames ±4 s); run T031 → green
- [ ] T033 [P] [US3] Write failing `backend/tests/unit/eval/test_review_app.py` (httpx ASGI): `GET /` HTML and `GET /items/next` JSON never contain strings from `key.json` values; order is a seeded permutation per reviewer (two reviewers differ, same reviewer stable); `POST /labels {"item_id","label":"supported"}` appends a JSONL line; invalid label → 422; after labelling all items `/items/next` returns `{"done": true, "count": N}`; `GET /items/{id}/replay` returns frames for that window only; server binds 127.0.0.1 (asserted on the `serve` config)
- [ ] T034 [US3] Implement `create_review_app`, `serve` and CLI `review serve` plus `eval/review_templates/index.html.j2` (claim text, Fact/Interpretation tag, evidence table, S/U/C buttons with keyboard shortcuts, note field, progress "12 / 150") and `replay.html.j2` (canvas 2D pitch 105 × 68, players as labelled dots, highlighted evidence players, play/pause); run T033 → green
- [ ] T035 [P] [US3] Write `frontend/tests/e2e/review.spec.ts` (starts `tactistream-eval review serve` on a 10-item fixture set via Playwright `webServer`): label all items using keyboard S/U/C; reload resumes; done screen shows 10; labels file has 10 lines
- [ ] T036 [US3] Extend `score.py` with review inputs: support and support-excluding-unclear per config (Wilson), `label_counts`, reviewed useful coverage, `AgreementStats` from two label files (shared items, raw agreement, κ, disagreement ids); extend `test_score.py` with a 2-reviewer fixture first (red → green)
- [ ] T037 [US3] (23 Oct) Build the review set from the four held-out runs (`--sample 150 --seed 7`), label all items as primary reviewer; if a second reviewer is available, label ≥ 30 shared items; run `score --review`; commit `eval/review/<review_id>/` (SC-003); optionally ingest labels into Eventhouse `ReviewLabels` (007) via `.ingest inline`

**Checkpoint**: tactical-support gate input exists with counts and label.

---

## Phase 6: User Story 4 — Live latency, consistency, fps (P2)

**Goal**: deployed-app latency with 10 viewers, 20-run consistency, named-machine fps.

**Independent Test**: local load with 3 viewers and 5-run consistency produce valid results.

- [ ] T038 [P] [US4] Write failing `backend/tests/unit/test_routes_diagnostics.py`: after a session with 2 viewers acking, `GET /api/diagnostics/latency?match_id=` returns all samples (fast + narrative, fallback included) with `viewer_id`s and `viewers == 2`; unknown match → 404 `match_not_found`; `TACTISTREAM_DIAGNOSTICS=off` → 404 `diagnostics_disabled`
- [ ] T039 [US4] Implement `backend/src/tactistream/api/routes_diagnostics.py` (+ `Settings.diagnostics: bool = True`, per-session sample access on `MatchSession`, `viewer_id` assigned per WS connection in `api/ws.py`); run T038 → green
- [ ] T040 [P] [US4] Write failing `backend/tests/unit/eval/test_load.py` (uvicorn-served app with scripted agents on a free port): `run_load(base_url, viewers=3, seed=42, duration_s=10)` in a short real-time run returns `LoadResult` with 3 viewers' samples, fast-overlay n ≥ 3 × events delivered, narrative samples including the injected timeout's fallback, `browser_display None`; JSON written to the given path
- [ ] T041 [US4] Implement `backend/src/tactistream/eval/load.py` (`run_load`, WS RTT measurement via ping/pong, client host + region from `--client-region`) and CLI `load`; run T040 → green
- [ ] T042 [P] [US4] Write failing `backend/tests/unit/eval/test_consistency.py`: `run_consistency(runs=5)` returns `distinct_hashes == 1` and 5 hashes; with a deliberately broken dedupe (monkeypatched) returns `distinct_hashes > 1` and a non-null `first_difference` naming the metric id; permutations differ between runs but respect `max_displacement`
- [ ] T043 [US4] Implement `backend/src/tactistream/eval/consistency.py` and CLI `consistency`; run T042 → green
- [ ] T044 [P] [US4] Write `frontend/tests/perf/replay-fps.spec.ts` + script `perf:fps` in `frontend/package.json` (Playwright project `perf`, headed Chromium, viewport 1920×1080; open `${BASE_URL}/?seed=42` (or `/demo?seed=42` once 009 lands), start match, open Why on the hero moment, inject rAF delta recorder, replay 3×; assert `document.visibilityState === "visible"`; fail if `TACTISTREAM_DEMO_MACHINE` unset; write `eval/results/perf/fps-<machine-slug>.json` as `FpsResult`); exclude project `perf` from CI
- [ ] T045 [US4] (23 Oct) Run consistency (`--runs 20`), the deployed load test (`--viewers 10 --seed 42 --duration-s 120`) with one real browser open on the same match, and `npm run perf:fps` on the named demo machine; commit results under `eval/results/perf/` (SC-005, SC-006, SC-007)

**Checkpoint**: latency, consistency and UI gates have inputs.

---

## Phase 7: User Story 5 — Report, API and Evidence page (P2)

**Goal**: eight gates evaluated honestly and shown to judges.

**Independent Test**: fixture report served by API and rendered by `/evidence` (Vitest + Playwright).

### Report

- [ ] T046 [P] [US5] Write failing `backend/tests/unit/eval/test_gates.py`: `GATE_TABLE` measure/target/method strings equal the spec's release-gates table (parsed from `specs/008-evaluation-evidence/spec.md`); each rule in data-model.md "Gate evaluation rules" passes/fails at its boundary (e.g. fast p95 2000 → pass, 2001 → fail; n = 99 → `not_measured` with "sample too small (n=99)"); missing inputs → `not_measured` with reason; order is build-plan order
- [ ] T047 [P] [US5] Write failing `backend/tests/unit/eval/test_report_render.py`: `build_report` picks the latest complete held-out run per config and lists all run ids; sets `claim_narrowed` and adds the FR-030 limitation when three_agent shows no gain (non-overlapping Wilson rule) at higher tokens; always includes the synthetic and controlled-environment limitations; `render_markdown` contains the gates table with sample sizes, the "internal review" label, environment, and every limitation; snapshot test against `backend/tests/fixtures/results_md.snapshot`
- [ ] T048 [US5] Implement `backend/src/tactistream/eval/report.py` (`ReportInputs`, `GATE_TABLE`, `evaluate_gates`, `build_report`, `render_markdown` via `report_templates/results.md.j2`, `publish`) and CLI `report [--publish]`; run T046–T047 → green

### API

- [ ] T049 [P] [US5] Write failing `backend/tests/unit/test_routes_evaluation.py`: with `TACTISTREAM_EVAL_REPORT_PATH` → fixture report, `GET /api/evaluation/results` returns it with `Cache-Control: no-cache`; missing file → 404 `report_not_found`; invalid JSON/schema → 500 `report_invalid`
- [ ] T050 [US5] Implement `backend/src/tactistream/api/routes_evaluation.py` (+ `Settings.eval_report_path`) and register in `api/app.py`; ensure the root `Dockerfile` copies `eval/results/latest/` (007 T017) and sets the env path; run T049 → green

### Frontend

- [ ] T051 [P] [US5] Write failing `frontend/tests/unit/evidence/StatusChip.test.tsx` and `GatesTable.test.tsx`: chip renders text "Pass"/"Fail"/"Not measured" plus an icon with `aria-hidden`; table has a `<caption>`, 8 rows in order, measured value, sample size and method; `not_measured` rows show the reason and never the target in the measured column
- [ ] T052 [P] [US5] Write failing `frontend/tests/unit/evidence/EvidencePage.test.tsx` (mock `getEvaluationResults`): loading state; renders report id/date, "Synthetic data" badge, "Internal review" label, comparison table with 4 configs (support with interval, coverage, false explanation, abstention, p95 incl. fallbacks, tokens/story, cost or "not priced"), latency table with n and timeout rate, environment panel, fixtures list, limitations list; 404 → "Results not published yet" with repository link
- [ ] T053 [US5] Implement `frontend/src/api/evaluation.ts`, `frontend/src/components/evidence/{StatusChip,GatesTable,ComparisonTable,LatencyTable,EconomicsPanel,FixturesList,EnvironmentPanel,LimitationsList}.tsx`, `frontend/src/routes/EvidencePage.tsx`, and `frontend/src/routes/router.tsx` (add `react-router` v7 if no router exists; routes `/` and `/evidence`); run T051–T052 → green
- [ ] T054 [US5] Add an "Evidence" link to `frontend/src/components/TopBar.tsx` (keyboard reachable, `aria-current` on `/evidence`) and "Back to match" on the page preserving the session (store not reset); extend `frontend/tests/unit/TopBar.test.tsx` first
- [ ] T055 [US5] Write and pass `frontend/tests/e2e/evidence.spec.ts` (server with fixture report): open `/`, activate Evidence via keyboard, assert 8 gate rows, "Internal review", at least one limitation; deep-link `/evidence` loads directly (SPA fallback); Back to match returns

### Publish

- [ ] T056 [US5] (23 Oct) Run `tactistream-eval report --publish` with all real inputs; review `docs/results.md` for any target presented as a result; commit `eval/results/<report_id>/`, `eval/results/latest/report.json`, `docs/results.md`; push → deploy; verify deployed `/evidence` shows the same `report_id` (SC-008) and spot-check 5 numbers back to their `evidence_path` files (SC-009)

**Checkpoint**: roadmap exit for 008 met.

---

## Phase 8: Polish

- [ ] T057 [P] Add a "Results" section link from `README.md` to `docs/results.md` and `/evidence` (009 finalizes README wording)
- [ ] T058 [P] Run `specs/008-evaluation-evidence/quickstart.md` §1 and §6 (fixtures, consistency) on a fresh clone; fix gaps
- [ ] T059 If `comparison.claim_narrowed` is true, open an issue for 009 listing the exact multi-agent wording to narrow in `docs/agents.md`, README and the submission description
- [ ] T060 Update `specs/README.md` feature table row 008: mark exit condition met with date and link the published `report_id`; list any gate reported as `fail` or `not_measured`

---

## Dependencies & Execution Order

- Setup (T001–T003) → Foundational (T004–T008) → US1 (T009–T021) and US2 (T022–T030) in parallel → US3 (T031–T037; T037 needs T021 outputs) → US4 (T038–T045; T045 needs the deployed app from 007 and 005's replay) → US5 (T046–T055 can be coded in parallel with US1–US4 using the fixture report; T056 needs all results) → Polish.
- External: 002 `simulate` (T009), 003 ingest/metrics/moments/state hash (T009, T042), 004 baselines/workflow/checks/fixtures/`token_budget` (T014, T016, T026–T027), 005 Why Mode replay (T044), 007 deployed app + `LatencySample` + SPA fallback (T039, T045, T050, T055).

## Parallel Example

```text
21 Oct evening (code ahead):  T004–T008  ||  T046–T053 (report, API, page with fixture report)
22 Oct morning:               T009–T016 (freeze, runner)  ||  T022–T029 (fixtures)
22 Oct afternoon:             T017–T020 (scoring)  →  T021 (held-out runs)  ||  T031–T035 (review tool)
23 Oct:                       T037 (review labelling)  ||  T038–T045 (live measurements)  →  T056 (publish)
```

## Implementation Strategy

Priority under time pressure (stop rule: never fabricate; unmeasured gates show `not_measured`): failure fixtures (US2) → frozen
runs + automatic scores (US1) → report/API/page (US5) → load + consistency (US4) → blind review (US3, ≥ 100 claims or all available)
→ fps. Do not start 009's optional MP4 export unless every essential gate passes.
