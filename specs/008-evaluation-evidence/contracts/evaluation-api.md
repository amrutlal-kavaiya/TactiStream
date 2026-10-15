# Evaluation Contracts (v1)

## REST

| Method & path | Request | 200 response | Errors |
|---|---|---|---|
| `GET /api/evaluation/results` | — | `EvaluationReport` (`contracts/schemas/evaluation_report.schema.json`), header `Cache-Control: no-cache` | 404 `{"error":"report_not_found","detail":"No evaluation report has been published"}`; 500 `{"error":"report_invalid"}` if the file fails schema validation (logged) |
| `GET /api/diagnostics/latency?match_id={id}` | — | `{"match_id": str, "viewers": int, "samples": LatencySample[]}` (all outcomes, ordered by `recorded_ms`) | 404 `match_not_found`; 404 `diagnostics_disabled` when `TACTISTREAM_DIAGNOSTICS=off` |

- Report path: `Settings.eval_report_path` (env `TACTISTREAM_EVAL_REPORT_PATH`, default `eval/results/latest/report.json`;
  container `/app/eval/results/latest/report.json`). The file is read per request (small) so a redeploy is not needed to
  refresh locally; in the container it changes only with a new image.
- Diagnostics expose only latency samples already sent to telemetry (no PII, no secrets). Enabled by default; the judging
  deployment keeps it on so judges can reproduce latency numbers.

## Frontend route

| Route | Component | Data |
|---|---|---|
| `/evidence` | `frontend/src/routes/EvidencePage.tsx` | `getEvaluationResults()` in `frontend/src/api/evaluation.ts` → `EvaluationReport` (generated TS type) |

Sections in order: header (report id, generated date, "Synthetic data" badge, review label) · Release gates · Agent comparison ·
Latency (deployed, offline generation) · Economics · Failure fixtures · Measured environment · Sample sizes · Limitations.
Status chips: text "Pass" / "Fail" / "Not measured" plus icon; colour is secondary.

## CLI — `tactistream-eval`

| Command | Purpose | Output |
|---|---|---|
| `freeze --set {heldout,dev}` | simulate + freeze inputs, split labels | `eval/frozen/<set>/*.json`, `MANIFEST.json`, `eval/labels/<set>.json` |
| `run --config <yaml> --set <set> [--model foundry\|scripted] [--inject-every N] [--limit K]` | run one config | `eval/results/<run_id>/{outputs.jsonl,run.json}` |
| `budget --from-run <run_id> --config eval/configs/three_agent_fixed_tokens.yaml` | set fixed token budget | config file updated |
| `score --run <run_id>… [--review <review_id>]` | score runs | `eval/results/<run_id>/scores.json` |
| `review build --runs <run_id>… --sample N --seed S` | build blinded review set | `eval/review/<review_id>/{items.json,key.json}` |
| `review serve --review <review_id> --reviewer <name> [--port 8765]` | local labelling UI on 127.0.0.1 | `labels.<reviewer>.jsonl` |
| `load --base-url URL [--viewers 10] [--seed 42] [--duration-s 120] [--no-fixture]` | live latency | `eval/results/perf/load-*.json` + samples jsonl |
| `consistency [--scenario space_creation] [--seed 42] [--runs 20] [--dup-rate 0.1] [--max-displacement 3]` | state hash repeatability | `eval/results/perf/consistency-*.json` |
| `report [--publish]` | build report, gates, markdown | `eval/results/<report_id>/report.json`, `latest/`, `docs/results.md` |

Exit codes: 0 success; 1 measurement completed but a precondition failed (e.g. incomplete run); 2 usage/config error. A failing
gate is **not** an error exit — it is a result.

## File formats

### `eval/scenarios/heldout.yaml`

```yaml
split: eval
scenarios:
  - { scenario_id: ho-01, scenario: space_creation, seed: 10001, variant: D, expect: positive }
  - { scenario_id: ho-19, scenario: run_no_channel, seed: 10101, variant: D, expect: negative }
  - { scenario_id: ho-28, scenario: tracking_gap,   seed: 10201, variant: D, expect: missing_data }
```

### `eval/configs/three_agent.yaml`

```yaml
config_id: three_agent
kind: three_agent
model: foundry
deadline_ms: 8000
token_budget: null
temperature: 0.0
repeats: 1
```

### `eval/configs/family_templates.yaml` (scorer only)

```yaml
space_creation: [interp.space_opened_by_run]
press_turnover: [interp.pressure_preceded_turnover]
switch_escape:  [interp.switch_escaped_pressure]
```

Template ids must match 004/006 catalog keys; the scorer test fails if any id is missing from `narrative/catalog/spec.json`
(004 keeps template metadata in `spec.json`; `en.json`/`hi.json` hold text only).

### `eval/configs/pricing.yaml`

```yaml
model: <deployed model name>
currency: USD
input_per_million: <number>
output_per_million: <number>
source_url: <Azure pricing page URL>
retrieved_on: 2026-10-22
note: list-price estimate; actual billing may differ
```

### `outputs.jsonl` — one `OutputRecord` per line (data-model.md). `labels.<reviewer>.jsonl` — one `ReviewLabel` per line.
