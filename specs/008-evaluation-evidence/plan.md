# Implementation Plan: Evaluation Evidence

**Branch**: `008-evaluation-evidence` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-evaluation-evidence/spec.md`

## Summary

Turn every judge-challengeable claim into a measured, reproducible number. A `tactistream-eval` CLI freezes 30 held-out
scenarios (label-free, byte-identical) and runs four configurations — deterministic summary, single agent with the same tools,
three-agent workflow, and three-agent at the single agent's token budget — on identical inputs, recording claims, packets,
usage, latency and fallbacks. A blind local review tool collects supported/unsupported/unclear labels; a scorer computes
coverage, false explanations, abstention, check integrity, support (Wilson intervals), latency including fallbacks, economics
and recovery. A failure-fixture integration suite proves seven failure modes degrade usefully. Live measurements cover
10-viewer latency on the deployed app, 20-run replay consistency and replay fps on a named machine. `report.py` evaluates the
eight build-plan release gates into an `EvaluationReport`, served at `GET /api/evaluation/results`, rendered on `/evidence` and
in `docs/results.md`.

## Technical Context

**Language/Version**: Python 3.12 (backend + CLI), TypeScript 5 strict (Evidence page, perf script)

**Primary Dependencies**: typer, pydantic v2, PyYAML, numpy (percentiles/Wilson), websockets + httpx (load client), FastAPI
(review mini-app, reuses backend deps), Jinja2 (review page + markdown rendering); React 19, Playwright (perf + e2e)

**Storage**: files under `eval/` (committed JSON/JSONL/YAML); report baked into the container image; optional mirror to Blob
`artifacts/eval/` via `ArtifactStore`

**Testing**: pytest (unit, integration incl. failure fixtures, contract for report schema), Vitest + Testing Library (Evidence
page components), Playwright (evidence e2e, review page e2e, fps perf spec — perf excluded from CI)

**Target Platform**: builder workstation for runs/review; deployed Container App for load + evidence page; named demo machine for fps

**Project Type**: Web application + CLI tooling

**Performance Goals**: held-out run of one config ≤ 20 min with Foundry; scripted `make eval-smoke` ≤ 60 s in CI; evidence page
first render ≤ 1 s after API response

**Constraints**: labels never reach configs; no record excluded from statistics; targets are labelled as targets; results
labelled synthetic and internal review; perf capture only on the named machine

**Scale/Scope**: 30 held-out + ≥ 12 dev scenarios; ~45–60 moments per config; ≥ 100 reviewed claims; 10 viewers; 20 consistency runs; 3 fps runs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Evidence before narrative | PASS | Scorer re-runs deterministic checks on every released packet against the frozen snapshot; reviewers see resolved evidence with each claim |
| II Provenance | PASS | Frozen inputs keep `source.kind = synthetic`; labels and generation manifest isolated in `eval/labels/`; label-leak test; match ids rewritten to avoid family leakage |
| III Deterministic core, bounded agents | PASS | Configs consume the same frozen moments; fixed-token config tests whether structure (not budget) helps; failure fixtures assert fast path keeps flowing during model waits |
| IV Contract-first | PASS | `evaluation_report.schema.json` + Pydantic model + contract test; TS types generated for the Evidence page |
| V Test-first | PASS | Each module has failing tests first (scorer math on hand-computed fixtures, blinding, label isolation, gate evaluation, API, page) |
| VI Measure, don't claim | PASS | Sample sizes, hardware, network, every failure and every held-out run id are reported; fallbacks counted in latency; coverage beside support; "internal review" label; `not_measured` instead of targets |
| VII Scope discipline | PASS | Local review tool (no new hosted service); file-based results; no new Azure resources |

Post-design re-check: PASS. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-evaluation-evidence/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
└── contracts/
    └── evaluation-api.md        # REST, route, CLI and file formats
```

### Source Code (repository root)

```text
contracts/schemas/evaluation_report.schema.json        (new; proposed cross-cutting)
contracts/examples/evaluation_report.json               (new; fixture report used by tests and page)
eval/
├── scenarios/{heldout.yaml,dev.yaml}
├── configs/{deterministic,single_agent,three_agent,three_agent_fixed_tokens}.yaml · family_templates.yaml · pricing.yaml
├── frozen/ · labels/ · results/ · review/                (generated; committed)
backend/
├── pyproject.toml                                      + pyyaml, jinja2; script tactistream-eval = tactistream.eval.cli:app
├── src/tactistream/
│   ├── contracts/evaluation.py                          EvaluationReport, ReleaseGate, ConfigScores, LatencyStats, Rate, …
│   ├── eval/__init__.py
│   ├── eval/models.py                                   ScenarioSpec, ScenarioSet, FrozenScenario, FrozenMoment, ScenarioLabel, EvalConfig, OutputRecord, RunManifest, Review*
│   ├── eval/scenarios.py                                load_scenario_set(path) -> ScenarioSet
│   ├── eval/frozen.py                                   freeze_scenario, freeze_set, load_frozen
│   ├── eval/configs.py                                  load_config, set_token_budget
│   ├── eval/runner.py                                   run_config, ConfigRunner implementations
│   ├── eval/review.py                                   build_review_set, create_review_app, serve
│   ├── eval/review_templates/{index.html.j2,replay.html.j2}
│   ├── eval/score.py                                    score_run, wilson, cohen_kappa, latency_stats
│   ├── eval/load.py                                     run_load
│   ├── eval/consistency.py                              run_consistency
│   ├── eval/report.py                                   build_report, evaluate_gates, render_markdown
│   ├── eval/report_templates/results.md.j2
│   ├── eval/cli.py                                      typer app `tactistream-eval`
│   ├── api/routes_evaluation.py                         GET /api/evaluation/results
│   └── api/routes_diagnostics.py                        GET /api/diagnostics/latency
└── tests/
    ├── contract/test_evaluation_report.py
    ├── unit/eval/{test_scenarios,test_frozen,test_label_leak,test_configs,test_runner,test_score,test_stats,
    │              test_review_build,test_review_app,test_load,test_consistency,test_gates,test_report_render}.py
    ├── unit/{test_routes_evaluation,test_routes_diagnostics}.py
    ├── integration/test_failure_fixtures.py
    └── integration/test_eval_smoke.py
frontend/
├── src/api/evaluation.ts                                getEvaluationResults()
├── src/routes/router.tsx                                routes "/" and "/evidence" (adds router if none exists)
├── src/routes/EvidencePage.tsx
├── src/components/evidence/{GatesTable,ComparisonTable,LatencyTable,EconomicsPanel,FixturesList,EnvironmentPanel,LimitationsList,StatusChip}.tsx
├── src/components/TopBar.tsx                            + "Evidence" link
├── tests/unit/evidence/{EvidencePage.test.tsx,GatesTable.test.tsx,StatusChip.test.tsx}
├── tests/e2e/{evidence.spec.ts,review.spec.ts}
└── tests/perf/replay-fps.spec.ts                         (npm run perf:fps; excluded from CI)
docs/results.md                                          (generated by report.py)
Makefile                                                 + eval-smoke, eval-fixtures
```

**Structure Decision**: Evaluation code lives in the registry's `eval/` package with a single CLI; published report types sit
in `contracts/` because they cross the API boundary; raw results are plain files under root `eval/` so every number is auditable
in the public repository.

## Key Design Notes

- **Runner abstraction**:
  ```python
  class ConfigRunner(Protocol):
      async def explain(self, fm: FrozenMoment, ctx: EvalContext) -> RunnerOutcome: ...
  def runner_for(cfg: EvalConfig, model: ModelClient) -> ConfigRunner: ...   # deterministic | single_agent | three_agent
  async def run_config(cfg: EvalConfig, set_name: str, *, frozen_dir: Path, out_dir: Path,
                       model: ModelClient, inject_every: int | None = None, limit: int | None = None) -> RunManifest: ...
  ```
  `EvalContext` builds 004's `WorkflowContext` from the frozen snapshot: evidence index from frozen events/metrics, as-of = moment
  trigger time, `deadline_ms`, `token_budget`, history store = `InMemoryHistoryStore` built from frozen events (007). Each record is
  appended and flushed immediately (crash-safe); a resumed run skips moments already in `outputs.jsonl`.
- **Freezing**: `freeze_scenario(spec) -> tuple[FrozenScenario, ScenarioLabel]`; `freeze_set(set_path, out_dir, labels_path) -> FreezeManifest`.
  Uses 002 `simulate`, 003 ingest + `MetricEngine` + `detect_moments`, then `remap_match_id(records, f"eval-{scenario_id}")`.
- **Scoring**: `score_run(run_dir, labels, review: ReviewData | None, pricing: Pricing | None) -> ConfigScores`;
  `wilson(k, n) -> tuple[float, float]`; `cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float | None`;
  `latency_stats(samples: Sequence[LatencyPoint]) -> LatencyStats` (nearest-rank, all outcomes, released-only separately).
- **Review app**: `create_review_app(review_dir: Path, reviewer: str, seed: int) -> FastAPI` with `GET /` (page), `GET /items/next`,
  `POST /labels`, `GET /items/{item_id}/replay`; served with uvicorn on `127.0.0.1`. HTML is server-rendered Jinja2 + ~100 lines of
  vanilla JS (keyboard shortcuts, canvas replay). A test asserts no config id or family string appears in any served response.
- **Load**: `async run_load(base_url: str, *, viewers: int = 10, seed: int = 42, duration_s: int = 120, inject_timeout: bool = True) -> LoadResult`.
  Creates one session, opens N websockets, sends `play` once, acks per message, at T/2 posts `model_timeout`, at end fetches
  `/api/diagnostics/latency`, splits samples by `viewer_id` (browser viewer = ids not opened by the tool).
- **Consistency**: `run_consistency(scenario="space_creation", seed=42, runs=20, dup_rate=0.1, max_displacement=3) -> ConsistencyResult`
  using 003 ingest with its reorder buffer; permutation RNG seeded by `seed*1000 + run`.
- **Gates**: `evaluate_gates(inputs: ReportInputs) -> list[ReleaseGate]`, constants `GATE_TABLE` holding verbatim measure/target/method
  strings from the build plan (test compares against the spec table text).
- **Report**: `build_report(inputs: ReportInputs) -> EvaluationReport`; `render_markdown(report) -> str`; `publish(report, repo_root)` writes
  `eval/results/<report_id>/report.json`, `eval/results/latest/report.json`, `docs/results.md`.
- **API**: `routes_evaluation.py` reads `settings.eval_report_path`, validates with `schema_registry.validate("evaluation_report", obj)`.
  `routes_diagnostics.py` reads `MatchSession.latency.samples(match_id)`.
- **Evidence page**: fetch on mount; sections as in contracts/evaluation-api.md; tables are semantic `<table>` with `<caption>`; status chip
  text + icon; numbers formatted with units; "Not measured" shows reason.
- **SPA routing**: if no router exists yet (005/006), add `react-router` v7 `createBrowserRouter` in `routes/router.tsx` with `/` → existing
  App shell and `/evidence` → `EvidencePage`; server SPA fallback comes from 007 (T016).

## Complexity Tracking

No violations.
