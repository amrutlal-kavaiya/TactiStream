# Data Model: 008 Evaluation Evidence

Python models live in `backend/src/tactistream/contracts/evaluation.py` (published report types) and
`backend/src/tactistream/eval/models.py` (internal evaluation records). All Pydantic v2, `extra="forbid"`, `frozen=True`.
The published report has a canonical schema `contracts/schemas/evaluation_report.schema.json` (proposed; created by T005).

## Scenario sets and frozen inputs (`eval/models.py`)

```python
class ScenarioSpec(BaseModel):
    scenario_id: str                       # ho-01..ho-30 | dv-01..
    scenario: ScenarioName                 # 002 family or negative or tracking_gap
    seed: int
    variant: Literal["A","B","C","D","E","F"]
    expect: Literal["positive","negative","missing_data"]

class ScenarioSet(BaseModel):
    split: Literal["dev","eval"]
    scenarios: list[ScenarioSpec]          # validator: split ranges (dev 1–9999 & A–C; eval ≥10000 & D–F), unique ids

class FrozenMoment(BaseModel):             # the ONLY thing configs receive
    moment: CandidateMoment
    snapshot: MatchSnapshot                # as of moment trigger; match_id = eval-{scenario_id}
    metrics: list[MetricResult]

class FrozenScenario(BaseModel):
    scenario_id: str
    match_id: str                          # eval-{scenario_id}
    metadata: MatchMetadata
    events: list[MatchEvent]
    frames: list[TrackingFrame]            # union of ±15 s windows around moments
    moments: list[FrozenMoment]
    input_sha256: str                      # of canonical JSON without this field

class ScenarioLabel(BaseModel):            # eval/labels/<set>.json — scorer only
    scenario_id: str
    scenario: ScenarioName
    variant: str
    expect: Literal["positive","negative","missing_data"]
    family: Literal["space_creation","press_turnover","switch_escape"] | None
    key_event_ids: list[str]               # from GenerationManifest, rewritten to frozen ids

class FreezeManifest(BaseModel):
    set: Literal["dev","heldout"]
    generator_version: str
    git_commit: str
    files: dict[str, str]                  # file name → sha256
```

## Configs and run outputs

```python
class EvalConfig(BaseModel):
    config_id: Literal["deterministic","single_agent","three_agent","three_agent_fixed_tokens"]
    kind: Literal["deterministic","single_agent","three_agent"]
    model: Literal["scripted","foundry"] = "foundry"
    deadline_ms: int = 8000
    token_budget: int | None = None
    token_budget_source_run: str | None = None
    temperature: float = 0.0
    repeats: int = 1

class AtomicClaim(BaseModel):
    claim_id: str
    kind: Literal["fact","interpretation"]
    template_id: str
    text_en_analyst: str
    evidence_ids: list[str]
    verifier_decision: Literal["approve","revise","reject"] | None
    released: bool

class Usage(BaseModel):
    model_calls: int
    input_tokens: int
    output_tokens: int
    by_agent: dict[str, dict[str, int]]    # agent → {calls, input_tokens, output_tokens}

class OutputRecord(BaseModel):
    run_id: str
    config_id: str
    scenario_id: str
    moment_id: str
    trace_id: str
    status: Literal["released","fallback","abstained"]
    fallback_reason: FallbackReason | None
    claim_status: ClaimStatus | None        # of released packets
    claims: list[AtomicClaim]
    packets: list[InsightPacket]           # released variants only
    check_failures: list[CheckFailure]     # from re-running checks at record time
    usage: Usage
    latency_ms: int                        # moment start → validated output or fallback (offline generation latency)
    deadline_ms: int
    injected_fixture: Literal["bad_claim","model_timeout"] | None

class RunManifest(BaseModel):
    run_id: str
    config: EvalConfig
    set: Literal["dev","heldout"]
    frozen_manifest_sha256: str
    git_commit: str
    model_deployment: str | None
    model_region: str | None
    started_at: datetime
    finished_at: datetime | None
    records: int
    errors: int
    degraded: bool                          # > 10% model_error
    complete: bool
```

## Review

```python
class ReviewItem(BaseModel):               # served to reviewers
    item_id: str                           # rv-{sha1(run_id|claim_id)[:10]}
    claim_text: str
    claim_kind_label: Literal["Fact","Interpretation"]
    evidence: list[ResolvedEvidence]       # id, kind, key fields (type, players, coords, clocks, value+unit)
    replay: ReplayWindow                   # frames subset for 2D view, start_ms, end_ms, highlighted player ids

class ReviewKeyEntry(BaseModel):           # key.json — never served
    item_id: str; run_id: str; config_id: str; scenario_id: str; claim_id: str

class ReviewLabel(BaseModel):
    item_id: str
    label: Literal["supported","unsupported","unclear"]
    note: str | None
    reviewer: str
    labeled_at: datetime

class AgreementStats(BaseModel):
    shared_items: int
    raw_agreement: float
    cohen_kappa: float | None
    disagreements: list[str]               # item ids
```

## Scores and measurements (`contracts/evaluation.py`)

```python
class Rate(BaseModel):
    numerator: int
    denominator: int
    value: float | None                    # None when denominator == 0
    ci95: tuple[float, float] | None       # Wilson

class LatencyStats(BaseModel):
    n: int
    p50_ms: int | None; p95_ms: int | None; max_ms: int | None
    released_n: int; released_p95_ms: int | None
    fallback_n: int; timeout_n: int
    timeout_rate: Rate

class Economics(BaseModel):
    per_match: dict[str, float]            # model_calls, input_tokens, output_tokens, compute_s, cost_usd?, eh_envelopes, eh_bytes, blob_bytes
    per_validated_story: dict[str, float]
    validated_stories: int
    price_source: str | None               # URL + retrieval date; None → "not priced"
    notes: list[str]

class ConfigScores(BaseModel):
    config_id: str
    run_id: str
    scenarios: int; moments: int
    released: int; fallback: int; abstained: int
    useful_coverage: Rate                  # positives
    useful_coverage_reviewed: Rate | None
    false_explanation: Rate                # negatives
    abstention_correctness: Rate           # missing_data
    check_pass: Rate                       # released packets passing deterministic checks
    support: Rate | None                   # supported / all reviewed (unclear counted)
    support_excl_unclear: Rate | None
    label_counts: dict[str, int]           # supported, unsupported, unclear
    latency: LatencyStats                  # offline generation latency
    recovery: Rate | None                  # injected records
    economics: Economics

class LoadResult(BaseModel):
    base_url: str; viewers: int; seed: int; duration_s: int
    client_host: str; client_region: str; ws_rtt_median_ms: int
    fast_overlay: LatencyStats
    narrative: LatencyStats
    browser_display: LatencyStats | None   # real browser viewer, if present
    samples_path: str

class ConsistencyResult(BaseModel):
    scenario: str; seed: int; runs: int; dup_rate: float; max_displacement: int
    distinct_hashes: int
    hashes: list[str]
    first_difference: str | None

class FpsRun(BaseModel):
    median_fps: float; p5_fps: float; long_frames: int; duration_ms: int

class FpsResult(BaseModel):
    machine: str; cpu: str; gpu: str; ram: str; os: str
    browser: str; browser_version: str; viewport: str; device_pixel_ratio: float
    runs: list[FpsRun]

class FixtureResult(BaseModel):
    fixture: Literal["missing_positions","late_events","duplicated_events","model_timeout","bad_claim","reconnect","history_unavailable"]
    expected: str
    passed: bool
    junit_case: str

class ReleaseGate(BaseModel):
    gate_id: Literal["fast_overlay_latency","narrative_latency","reference_numeric_integrity","tactical_support",
                     "ui_responsiveness","replay_consistency","failure_handling","economics"]
    measure: str                           # verbatim build-plan wording
    target: str                            # verbatim build-plan wording
    method: str                            # verbatim build-plan wording
    status: Literal["pass","fail","not_measured"]
    measured: str | None                   # e.g. "p95 1.4 s (n=812); timeout rate 3/41"
    sample_size: int | None
    evidence_path: str | None
    reason: str | None                     # required when not_measured

class MeasuredEnvironment(BaseModel):
    app_url: str; app_region: str; container: str          # "1 replica, 1 vCPU / 2 GiB"
    model_deployment: str; model: str; model_region: str
    demo_machine: str | None
    network: str                                            # e.g. "home fibre, Bengaluru → eastus2, median RTT 230 ms"
    measured_on: list[date]

class Comparison(BaseModel):
    configs: list[ConfigScores]
    fixed_token_note: str | None
    claim_narrowed: bool
    summary: str                            # one paragraph generated from numbers, no adjectives beyond the numbers

class EvaluationReport(BaseModel):
    schema_version: Literal["1.0"]
    report_id: str                          # rep-{UTC yyyymmddTHHMMSS}
    generated_at: datetime
    git_commit: str
    data_source: Literal["synthetic"]
    review_label: Literal["internal_review","expert_review"]
    reviewers: int
    review_agreement: AgreementStats | None
    datasets: dict[str, dict[str, int | str]]   # heldout/dev: scenario counts by expect, seeds range, variants
    heldout_runs: dict[str, list[str]]          # config → all held-out run ids (disclosure)
    gates: list[ReleaseGate]                    # exactly 8, build-plan order
    comparison: Comparison
    live: dict[str, LoadResult | ConsistencyResult | FpsResult | None]   # load, consistency, fps
    failure_fixtures: list[FixtureResult]
    environment: MeasuredEnvironment
    limitations: list[str]
```

## Gate evaluation rules (`eval/report.py::evaluate_gates`)

| gate_id | pass when | Source |
|---|---|---|
| `fast_overlay_latency` | `load.fast_overlay.p95_ms ≤ 2000` and n ≥ 100 | LoadResult |
| `narrative_latency` | `load.narrative.p95_ms ≤ 8000` (all outcomes) and n ≥ 20; timeout rate always shown | LoadResult |
| `reference_numeric_integrity` | `check_pass.value == 1.0` for every config with released packets | ConfigScores |
| `tactical_support` | `three_agent.support.value ≥ 0.95` with ≥ 1 reviewed claim; sample size and κ shown | ConfigScores + review |
| `ui_responsiveness` | median of per-run `median_fps ≥ 30` across ≥ 3 runs | FpsResult |
| `replay_consistency` | `distinct_hashes == 1` with runs ≥ 20 | ConsistencyResult |
| `failure_handling` | all 7 fixtures passed | FixtureResult (JUnit) |
| `economics` | per-match and per-validated-story tokens and calls present for every model config, plus EH/Blob usage | ConfigScores + 007 |

Insufficient sample (below the n thresholds) → `not_measured` with reason "sample too small (n=…)", never `pass`.

## File layout

```text
eval/
├── scenarios/{heldout.yaml,dev.yaml}
├── configs/{deterministic,single_agent,three_agent,three_agent_fixed_tokens}.yaml · family_templates.yaml · pricing.yaml
├── frozen/{heldout,dev}/<scenario_id>.json + MANIFEST.json      (committed)
├── labels/{heldout,dev}.json                                    (committed; scorer only)
├── results/<run_id>/{outputs.jsonl,run.json,scores.json}        (committed)
├── results/perf/{load-*.json,consistency-*.json,fps-*.json,latency-samples-*.jsonl}
├── results/fixtures-junit.xml
├── results/<report_id>/report.json · results/latest/report.json
└── review/<review_id>/{items.json,key.json,labels.<reviewer>.jsonl}
```
