# Data Model: 004 Agent Workflow

Canonical shapes live in `/contracts/schemas` (`claim.schema.json`, `insight_packet.schema.json`,
`ws_message.schema.json`, proposed `agent_trace.schema.json`). This file lists runtime types, the narrative catalog
format, decision tables and state transitions introduced by 004.

## Contract model changes (`backend/src/tactistream/contracts/`)

| Module | Change | Proposed schema change |
|---|---|---|
| `claim.py` | `SlotValue.value: float \| None`, `SlotValue.unit: MetricUnit \| None` (only for `kind="metric"`) | C2 |
| `insight.py` | `InsightLabel` gains `demo_fixture` | C3 |
| `ws.py` | `FallbackReason` gains `no_supported_claim` | C4 |
| `trace.py` (new) | `AgentTrace`, `TraceStep`, `ToolCallRecord`, `ClaimTraceEntry`, `StepUsage` | C1 |
| `envelope.py` | `agent_trace` payload parsed into `AgentTrace` | C1 |

All models keep `ConfigDict(extra="forbid", frozen=True)`.

## Runtime types

```python
# agents/context.py
FixtureKind = Literal["bad_claim", "model_timeout"]
FallbackReason = Literal["timeout", "model_error", "verifier_rejected", "no_supported_claim",
                         "output_check_failed", "expired", "insufficient_tracking"]
NarrativeStage = Literal["analysing", "verifying", "producing", "checking", "released", "fallback", "abstained"]
ClaimStatus = Literal["proposed", "approved", "rejected", "revised", "superseded", "unused"]

@dataclass(frozen=True)
class NarrativePrefs:
    pinned_player_id: str | None = None      # used only by build_recap_candidates (006); never by the moment workflow

@dataclass
class ClaimRecord:
    claim: Claim
    attempt: Literal[1, 2]
    precheck: Verdict | None = None
    model_verdict: Verdict | None = None
    final: Verdict | None = None
    status: ClaimStatus = "proposed"
    superseded_by: str | None = None          # claim_id of the attempt-2 claim that replaced it
    injected_fault: FixtureKind | None = None

class ClaimLedger:                            # append-only; one per run
    def next_claim_id(self) -> str: ...      # clm-{trigger_seq:04d}-{n}, n = 1, 2, 3, …
    def add(self, record: ClaimRecord) -> None: ...
    def set_verdicts(self, claim_id: str, pre: Verdict, model: Verdict | None, final: Verdict) -> None: ...
    def approved(self) -> list[Claim]: ...
    def needing_revision(self) -> list[ClaimRecord]: ...
    def records(self) -> Sequence[ClaimRecord]: ...

@dataclass(frozen=True)
class AgentBudgets:
    caps_ms: Mapping[Role, int]               # analyst 3500, verifier 2500, producer 1500
    min_ms: Mapping[Role, int]                # analyst 800, verifier 600, producer 600
    reserve_ms: int = 400
    token_budget: int | None = None           # 008 fixed-token config: stop before a call that would exceed it
    repair_min_remaining_ms: int = 3000

@dataclass(frozen=True)
class WorkflowDeps:
    client: ModelClient | None                # None for the deterministic runner
    tools: AgentTools
    catalog: Catalog
    metadata: MatchMetadata
    evidence: EvidenceIndex
    clock: Clock
    session_clock_ms: Callable[[], int]       # replayer session clock, for packet timing
    budgets: AgentBudgets
    min_tracking_coverage: float              # 0.8
    on_stage: Callable[[NarrativeStage], Awaitable[None]]
    recorder: TraceRecorder
    prompts: PromptSet                        # loaded prompt files with versions

# agents/workflow.py
@dataclass(frozen=True)
class Usage:
    model_calls: int
    tokens_in: int | None                     # None if any call lacked usage
    tokens_out: int | None

@dataclass(frozen=True)
class WorkflowResult:
    outcome: Literal["released", "fallback", "abstained", "superseded", "cancelled"]
    bundle: InsightBundle | None
    fallback_reason: FallbackReason | None
    claims: tuple[ClaimRecord, ...]
    producer_output: ProducerOutput | None
    check_failures: tuple[CheckFailure, ...]
    trace: AgentTrace
    usage: Usage
    latency_ms: int                           # result ready − trigger_receipt_ms
    runner: RunnerKind

# agents/checks.py (001 type, codes extended)
CheckCode = Literal["unsupported_number", "unsupported_player", "unknown_evidence", "invalid_timing", "expired",
                    "unapproved_claim", "unrequested_annotation", "unresolvable_annotation", "future_evidence",
                    "title_mismatch", "unknown_template", "causal_overreach", "variant_inconsistent", "schema_invalid"]
@dataclass(frozen=True)
class CheckFailure:
    code: CheckCode
    detail: str
    variant: tuple[ViewerMode, Language] | None = None

# agents/service.py
class FixtureArm:
    def arm(self, kind: FixtureKind) -> None: ...                   # replaces any armed fixture
    def consume(self, moment_id: str) -> FixtureKind | None: ...    # one-shot; remembers moment_id → kind for the run
    def armed(self) -> FixtureKind | None: ...
```

One `FixtureArm` per `MatchSession`. Fixture-affected bundles are cached only under that session's `match_id`, so
an armed fixture never changes what other sessions see.

## Narrative catalog format

`narrative/catalog/spec.json` holds language-independent metadata; `en.json` and `hi.json` hold text only. A test
asserts both language files contain exactly the keys of `spec.json`, with `fan` and `analyst` text for claim/status
templates and a single `text` for titles and phrases.

```json
{
  "catalog_version": "1.1",
  "templates": {
    "interp.space_opened_by_run": {
      "kind": "interpretation",
      "slots": {
        "runner":       { "type": "player" },
        "defender":     { "type": "player" },
        "channel_gain": { "type": "metric", "metric_kinds": ["channel"], "unit": "m", "precision": 1 }
      },
      "required_evidence_kinds": ["off_ball_run", "defender_follow", "channel"],
      "requires_tracking": true,
      "title_keys": ["title.space_opened_before_shot", "title.space_opened_before_pass"],
      "patterns": ["space_creation"]
    },
    "title.space_opened_before_shot": { "kind": "title" },
    "outcome.on_target": { "kind": "phrase" }
  }
}
```

```json
{ "interp.space_opened_by_run": {
    "fan": "{runner}'s run helped create room for the pass.",
    "analyst": "{defender} shifted toward {runner} while the passing channel widened by {channel_gain} m. The next forward pass used that space." },
  "title.space_opened_before_shot": { "text": "Space opened before the shot" },
  "outcome.on_target": { "text": "on target" } }
```

Slot rendering: `player` → metadata display name in the language (`Blue 9` / `ब्लू 9`); `team` → team display name;
`metric` → `MetricEngine` value formatted at `precision` with Western digits (agent `SlotValue.value` ignored);
`event_time` → renders the event ID (`evt-0045`) in analyst text and is not rendered in fan text. **Derived slots**
(`{outcome}`) are filled from the event bound to an `event_time` slot via `outcome.{event.outcome}` phrases.

### Template table (en final; hi drafts reviewed in 006)

| Key | Kind | Slots (type → metric kind, unit, precision) | Required evidence kinds | Tracking | Titles | Patterns |
|---|---|---|---|---|---|---|
| `fact.forward_pass` (001) | fact | passer, receiver (player); progress (metric → forward_progress, m, 1) | forward_progress | no | title.forward_pass | space_creation, shot, generic |
| `fact.shot` | fact | shooter (player); shot (event_time) | — | no | title.shot | shot, space_creation |
| `fact.turnover` | fact | winner (player); loser_team (team); event (event_time) | — | no | title.turnover | press_turnover |
| `fact.switch` | fact | passer, receiver (player); event (event_time) | — | no | title.switch | switch_escape |
| `interp.space_opened_by_run` | interpretation | runner, defender (player); channel_gain (metric → channel, m, 1) | off_ball_run, defender_follow, channel | yes | title.space_opened_before_shot, title.space_opened_before_pass | space_creation |
| `interp.defender_followed_runner` | interpretation | runner, defender (player); follow (metric → defender_follow, cosine, 2) | off_ball_run, defender_follow | yes | title.runner_tracked | space_creation |
| `interp.pressure_preceded_turnover` | interpretation | carrier, winner (player); pressure (metric → pressure, score_0_100, 0) | pressure | yes | title.pressure_before_turnover | press_turnover |
| `interp.switch_escaped_pressure` | interpretation | passer, receiver (player); pressure_before, pressure_after (metric → pressure, score_0_100, 0) | pressure | yes | title.switch_escape | switch_escape |
| `status.insufficient_tracking` | status | — | — | — | — | all |

| Key | en fan | en analyst | hi fan (draft) | hi analyst (draft) |
|---|---|---|---|---|
| `fact.shot` | "{shooter} took a shot: {outcome}." | "{shooter} took a shot: {outcome} ({shot})." | "{shooter} ने शॉट लिया: {outcome}।" | "{shooter} ने शॉट लिया: {outcome} ({shot})।" |
| `fact.turnover` | "{winner} won the ball from {loser_team}." | "{winner} won possession from {loser_team} ({event})." | "{winner} ने {loser_team} से गेंद जीती।" | "{winner} ने {loser_team} से कब्ज़ा जीता ({event})।" |
| `fact.switch` | "{passer} switched play to {receiver}." | "{passer} switched play to {receiver} ({event})." | "{passer} ने खेल {receiver} की ओर स्विच किया।" | "{passer} ने खेल {receiver} की ओर स्विच किया ({event})।" |
| `interp.space_opened_by_run` | "{runner}'s run helped create room for the pass." | "{defender} shifted toward {runner} while the passing channel widened by {channel_gain} m. The next forward pass used that space." | "{runner} की दौड़ ने पास के लिए जगह बनाने में मदद की।" | "{defender} {runner} की ओर खिसके, और पासिंग चैनल {channel_gain} मी चौड़ा हुआ। अगले फ़ॉरवर्ड पास ने उसी जगह का इस्तेमाल किया।" |
| `interp.defender_followed_runner` | "{defender} moved with {runner}'s run." | "{defender}'s movement matched {runner}'s run (direction similarity {follow})." | "{defender} {runner} की दौड़ के साथ चले।" | "{defender} की चाल {runner} की दौड़ से मेल खाती रही (दिशा समानता {follow})।" |
| `interp.pressure_preceded_turnover` | "Pressure on {carrier} preceded the turnover." | "Pressure on {carrier} reached a proxy score of {pressure} just before {winner} won the ball." | "गेंद छिनने से पहले {carrier} पर दबाव था।" | "{winner} के गेंद जीतने से ठीक पहले {carrier} पर दबाव का प्रॉक्सी स्कोर {pressure} था।" |
| `interp.switch_escaped_pressure` | "{passer}'s switch coincided with play moving away from pressure." | "Pressure proxy fell from {pressure_before} on {passer} to {pressure_after} on {receiver} after the switch." | "{passer} के स्विच के साथ खेल दबाव से दूर गया।" | "स्विच के बाद दबाव प्रॉक्सी {passer} पर {pressure_before} से घटकर {receiver} पर {pressure_after} रहा।" |
| `status.insufficient_tracking` | "Insufficient tracking for this explanation." | same | "इस व्याख्या के लिए पर्याप्त ट्रैकिंग नहीं है।" | same |

Title keys (en / hi draft): `title.forward_pass` "Forward pass" / "फ़ॉरवर्ड पास" (001) · `title.shot` "Shot" / "शॉट" ·
`title.turnover` "Ball won" / "गेंद जीती" · `title.switch` "Switch of play" / "खेल का स्विच" ·
`title.space_opened_before_shot` "Space opened before the shot" / "शॉट से पहले जगह बनी" ·
`title.space_opened_before_pass` "Space opened before the pass" / "पास से पहले जगह बनी" ·
`title.runner_tracked` "Defender went with the run" / "डिफ़ेंडर दौड़ के साथ गया" ·
`title.pressure_before_turnover` "Pressure before the turnover" / "टर्नओवर से पहले दबाव" ·
`title.switch_escape` "Switch away from pressure" / "दबाव से दूर स्विच".
Outcome phrases: `outcome.on_target` "on target" / "लक्ष्य पर", `outcome.off_target` "off target" / "लक्ष्य से बाहर",
`outcome.blocked` "blocked" / "रोका गया", `outcome.goal` "goal" / "गोल".

Wording rule (lint-tested): interpretation text uses "helped create", "coincided with", "preceded", "moved with",
"matched" — never the causal-overreach lexicon (spec FR-012).

## Evidence-pack recipes (`agents/tools.py`)

`A` = anchor events in the moment window; "last pass" = last completed pass in the window at or before `as_of_ms`.

| Pattern | Analyst pack metrics (besides `moment.metric_ids`) | Analyst geometry | Verifier counterevidence |
|---|---|---|---|
| space_creation | forward_progress@each pass in window; receiver_separation@last pass; pressure@last pass | `positions` of involved players at window start and at last pass | pressure@last pass (receiver crowded?), receiver_separation@last pass (separation fell?) |
| press_turnover | pressure@ the 2 events before the turnover | `nearest_opponents(carrier, 3)` at the frame before the turnover | pressure@ the event 3 before the turnover (pressure already high earlier?) |
| switch_escape | pressure@switch pass; pressure@ first receiver event; forward_progress@switch pass | `nearest_opponents(receiver, 3)` at receipt | pressure@ second receiver event if ≤ as_of (closed down immediately?) |
| shot | forward_progress@each pass in window; pressure@shot | `positions` of shooter and nearest 3 opponents at shot | — |

Every pack also includes `get_match_snapshot()` and `get_event_window(window.start_ms, as_of_ms)`.

## Reason codes → pre-check decisions (`agents/verifier.py`)

| Code | Trigger | Decision |
|---|---|---|
| `missing_evidence_id` | a cited ID does not exist in the as-of snapshot / cannot be computed | reject |
| `missing_evidence_id` | a slot metric or a required evidence kind is not cited; a slot player appears in none of the cited evidence; a requested annotation refers to a player/metric not in the claim | revise |
| `future_evidence` | any cited event/frame time or metric `window.end_ms` > `as_of_ms` | reject |
| `value_mismatch` | `round(SlotValue.value, p) != round(engine.value, p)` or `SlotValue.value` missing on a metric slot | revise |
| `unit_mismatch` | `SlotValue.unit` ≠ metric unit or ≠ template slot unit | revise |
| `template_kind_mismatch` | unknown template; `claim.kind` ≠ template kind; slot names ≠ template slots; slot type wrong; metric kind not allowed | revise |
| `insufficient_tracking` | template `requires_tracking` and (`tracking_coverage < 0.8` or a slot/required metric `unavailable`) | reject |
| `ok` | none of the above | approve (pending model judgement) |

Combination: `severity = {approve: 0, revise: 1, reject: 2}`; `final.decision = max(pre, model)`; `final.reason_codes`
= union without `ok` unless both are `ok`; `final.note` = model note if present else pre-check detail.

## Fallback templates (`narrative/factual.py`)

| Trigger event / pattern | Template | Notes |
|---|---|---|
| pass with `outcome=complete`, pattern ≠ switch_escape | `fact.forward_pass` + `title.forward_pass` | uses forward_progress@trigger (computed via MetricEngine) |
| pass, pattern = switch_escape | `fact.switch` + `title.switch` | |
| shot | `fact.shot` + `title.shot` | outcome phrase from event |
| interception / tackle(won) / ball_recovery | `fact.turnover` + `title.turnover` | `loser_team` = other team |
| anything else | none | only `narrative_status{stage:"fallback"}` |

Fallback bundle: `claim_ids = []`, `evidence_ids = [trigger_event_id] (+ forward_progress metric if used)`,
`claim_status = fallback_template`, `labels = ["synthetic","fallback"] (+ "demo_fixture")`, `panel = lower_third`,
`priority = 3`, `annotations = []`. Abstain bundle: same fact sentence, then `status.insufficient_tracking`;
title = fact title; `claim_status = insufficient_data`; `labels = ["synthetic","partial_tracking"]`;
`evidence_ids = [trigger_event_id] + unavailable moment metric IDs`.

## Bundle timing (`assemble_bundle`, fallback and abstain builders)

- `as_of_session_ms = moment.window.end_ms`; `state_version = ctx.state_version`.
- `render.show_from_ms = max(moment.window.end_ms, release_session_ms)`; `show_until_ms = show_from_ms + 6000`.
- `expires_at_session_ms = as_of_session_ms + 30000`; `render.replay_window = moment.window`.
- `render.priority`, `panel`, `annotations` from the mode's `ModePlan` (fallback/abstain: 3, `lower_third`, `[]`).

## Bad-claim mutation (`mutate_to_bad_claim`)

Deterministic, applied to the Analyst attempt-1 output only:

1. Pick the first interpretation claim; if none, build `interp.space_opened_by_run` (or the first eligible interpretation
   template for the pattern) using the moment's first two involved players and its first eligible metric.
2. Set `kind = "fact"` (→ `template_kind_mismatch`), `uncertainty = "low"`.
3. Replace the metric slot's `value` with the largest value in the metric's `components` (hero: `clearance_at_pass_m`
   5.3 instead of 3.4 → `value_mismatch`); if no components, `value × 1.5` rounded to precision.
4. Set `rationale = "{runner}'s run forced {defender} out of the channel."` using player IDs (Verifier model is expected
   to add `unsupported_causality`).
5. Mark `ClaimRecord.injected_fault = "bad_claim"`.

## State transitions

```text
Run:     queued --gate fails--> abstained
         queued --> analysing(1) --> verifying(1)
         verifying(1) --any revise ∧ remaining ≥ 3000 ms--> analysing(2) --> verifying(2) --> producing
         verifying(n) --≥1 approved--> producing --> checking --pass--> released
         verifying(n) --0 approved--> fallback(verifier_rejected) | abstained (all rejected for insufficient_tracking)
         analysing(n) --abstain insufficient_tracking--> abstained
         analysing(1) --abstain other / no claims--> fallback(no_supported_claim)
         checking --fail--> fallback(output_check_failed)
         any step --ModelTimeout | budget < min | outer guard--> fallback(timeout)
         any step --ModelError--> fallback(model_error)
         released/fallback with show_from > expires --> same outcome, fallback_reason = expired (bundle kept for timeline)
         any --session reset--> cancelled (nothing broadcast)
         before broadcast --moment state_version advanced--> superseded (nothing broadcast)

Claim:   proposed --pre+model verdict--> approved | rejected | revise
         revise --repair round--> revised (superseded_by = new claim) ; revise --no repair--> rejected
         approved --not in any ModePlan--> unused
UI "Blocked claim" = status ∈ {rejected, revised}.
```

## Hero fixture (`data/fixtures/hero_space_creation.jsonl`)

Frozen from the 002 demo match `demo-blue-amber-001` (seed 42), window 36.0–47.0 s: metadata (contract example
roster), events `evt-0038`…`evt-0046`, 10 Hz frames `frm-000360`…`frm-000470`. Key facts (asserted by
`test_hero_fixture`, constants in `backend/tests/fixtures/hero_ids.py`): Blue 9 diagonal run 38.3–42.3 s; Amber 4
moves with him; `evt-0042` complete forward pass blue-08 → blue-11 (forward_progress 13.1 m); `evt-0045` shot by
blue-11 on target; moment `mom-0045` (space_creation, window 36000–46500, coverage 1.0); `metric-channel-0042` = 3.4 m
(components 1.9 → 5.3); `metric-defender_follow-0042` and `metric-off_ball_run-0042` status ok; `evt-0046` at > 46500 ms
(used by the future-evidence test). `hero_missing_tracking.jsonl` is identical except blue-09 and amber-04 have
`visible=false` in frames 40.0–43.0 s (coverage < 0.8; channel and defender_follow `unavailable`).
