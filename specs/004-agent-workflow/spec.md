# Feature Specification: Agent Workflow — Analyst, Verifier, Producer with deterministic release checks

**Feature Branch**: `004-agent-workflow`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan, "Give three agents distinct authority" and "Treat reliability as part of the demonstration".
Roadmap exit condition (16–17 Oct): a supported card appears; an unsupported claim is visibly blocked; a timeout
produces a factual template; the trace view works. Builds on 001 (bus, state, fact card, checks, WS) and 003
(`MatchSnapshot`, `MetricEngine`, `detect_moments`, `CandidateMoment`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a supported tactical explanation for the hero moment (Priority: P1)

A viewer watches the demo match `demo-blue-amber-001`. Blue 9 makes a diagonal off-ball run, Amber 4 moves with
him, the passing channel widens, Blue 8 plays a forward pass to Blue 11 and Blue 11 shoots. A few seconds after the
shot, a small stage indicator on the card area reads "Analysing… → Verifying… → Producing… → Checking…", then one
calm card appears: title "Space opened before the shot", body "Blue 9's run helped create room for the pass.", with
an **Interpretation** label next to the **Synthetic** badge. Switching to Analyst mode shows the same claim with the
measured channel gain ("…the passing channel widened by 3.4 m…") and evidence chips; switching to Hindi preserves
every number and player identity. All visible text is rendered from reviewed catalog templates; the agents choose
claims, evidence and presentation, never the words or numbers.

**Why this priority**: The product's central promise ("see the move behind the moment") and the roadmap's first
exit condition. Proves real handoffs between three agents with distinct authority, ending in a checked render packet.

**Independent Test**: With `TACTISTREAM_AGENTS=scripted` (no network), run `backend/tests/unit/test_workflow.py::test_happy_path`
and `backend/tests/integration/test_narrative_flow.py`; both assert the WS stage sequence, the released `InsightBundle`
(4 variants, exact fan/en text), and that every variant passes `check_release`. The Playwright test
`frontend/tests/e2e/agents.spec.ts::hero card` asserts the card text and Interpretation label in the browser.

**Acceptance Scenarios**:

1. **Given** scripted agents and the hero fixture, **When** the shot `evt-0045` is ingested and moment `mom-0045` is
   detected, **Then** the server sends `narrative_status` stages `analysing`, `verifying`, `producing`, `checking`,
   `released` (in that order) followed by an `insight` message with `insight_id = ins-0045`, 4 variants, fan/en
   `claim_status = interpretation_supported`, `labels ⊇ ["synthetic","interpretation"]`, body "Blue 9's run helped create room for the pass.".
2. **Given** the released bundle, **When** the viewer switches Fan → Analyst → Hindi, **Then** the card swaps
   variants instantly (no new request, no model call) and the set of numbers (`3.4`, `13.1`) and player IDs is identical
   across the analyst/en and analyst/hi variants.
3. **Given** the released card, **When** the viewer opens evidence, **Then** every evidence ID on the card
   (`evt-0042`, `metric-channel-0042`, `metric-defender_follow-0042`, `metric-off_ball_run-0042`, …) resolves via
   `GET /api/matches/{match_id}/evidence/{id}`.
4. **Given** `TACTISTREAM_AGENTS=foundry` and valid Foundry credentials, **When** the live test
   `backend/tests/live/test_foundry_agents.py` runs the hero moment, **Then** the real Analyst, Verifier and Producer
   return schema-valid JSON, the result is `released` or a labelled `fallback`, and the trace records deployment name,
   tokens and per-step latency (`@pytest.mark.live`, excluded from CI).

---

### User Story 2 - Watch an unsupported claim get blocked and repaired (Priority: P1)

During the demo the presenter presses **Inject bad claim** (visible only when `TACTISTREAM_DEMO_FIXTURES=true`, and
labelled "Demo fixture"). On the next moment the Analyst's first proposal is replaced by a deliberately bad claim:
an interpretation template presented as a fact, a channel value of 5.3 m where the metric engine measured 3.4 m,
and a rationale saying the run "forced" the defender out. The Verifier's deterministic pre-checks flag
`template_kind_mismatch` and `value_mismatch`; its model judgement adds `unsupported_causality`; the verdict is
`revise`. Because more than 3 s remain, the Analyst gets one repair round and returns a corrected interpretation,
which the Verifier approves. The card that appears contains only the approved claim. The Agent trace panel shows the
**Blocked claim** with its reason codes and the revised claim that replaced it.

**Why this priority**: The roadmap exit condition "an unsupported claim is visibly blocked", the build plan's
"rejected claims, bounded recovery" judging evidence, and constitution I/III.

**Independent Test**: `test_workflow.py::test_revise_once` (scripted) asserts 5 model calls, stage sequence with two
`analysing`/`verifying` pairs, a ledger entry with final status `revised` → superseded by an approved claim, and a
released bundle whose `claim_ids` exclude the blocked claim. `agents.spec.ts::blocked claim` asserts the trace panel
text "Blocked claim" and reason labels.

**Acceptance Scenarios**:

1. **Given** the `bad_claim` fixture is armed, **When** the next moment runs, **Then** the trace contains a Verifier
   verdict for the injected claim with `decision = revise` and `reason_codes ⊇ ["template_kind_mismatch","value_mismatch"]`,
   the step is marked `injected_fault = "bad_claim"`, and the released packet's `claim_ids` do not include it.
2. **Given** an Analyst claim that cites `evt-0046` (after `as_of_session_ms`), **When** the Verifier runs,
   **Then** the claim is `reject`ed with `future_evidence`, it is not resubmitted in the repair round, and the trace shows it as blocked.
3. **Given** a claim needing revision but fewer than 3000 ms remain before the deadline, **When** verification ends,
   **Then** no repair round runs, the claim is treated as rejected, and the workflow either releases the remaining
   approved claims or falls back.
4. **Given** the Verifier model approves a claim that a deterministic pre-check marked `revise` or `reject`,
   **When** verdicts are combined, **Then** the stricter decision wins.

---

### User Story 3 - Get a useful factual card when the narrative cannot be trusted (Priority: P1)

If the model times out, errors, all claims are rejected, the Producer's plan fails the release checks, or the result
would arrive after its expiry, the viewer still sees a factual card rendered from validated events — e.g. "Blue 11
took a shot: on target." — labelled **Facts only**, within 8 s of the trigger event's server receipt. If the tracking
needed for a spatial explanation is missing, the card says "Insufficient tracking for this explanation." alongside
the factual sentence, and no model is called at all. The ordinary event rows and live metrics never wait for any of this.

**Why this priority**: Roadmap exit condition "timeout produces a factual template"; constitution I (insufficient
tracking) and III (8-second deadline, deterministic fallback); build plan failure fixtures (missing positions, model timeout, bad claim).

**Independent Test**: `test_workflow.py::test_fallbacks[...]` (parametrized, FakeClock) asserts each failure mode
yields `fallback` with the right `fallback_reason` and a bundle released at or before `trigger_receipt_ms + 8000`;
`test_workflow.py::test_abstain_missing_tracking` asserts zero model calls and an `abstained` status bundle.

**Acceptance Scenarios**:

1. **Given** the `model_timeout` fixture (the Analyst never answers), **When** the hero moment runs, **Then**
   `narrative_status{stage:"fallback", fallback_reason:"timeout"}` and an `insight` bundle with
   `claim_status = fallback_template`, `labels ⊇ ["synthetic","fallback"]` are broadcast no later than 8000 ms after
   the trigger's `server_receipt_ms`.
2. **Given** the missing-tracking fixture (Blue 9 and Amber 4 invisible for 40.0–43.0 s), **When** the space-creation
   moment is detected, **Then** zero model calls are made, `narrative_status{stage:"abstained", fallback_reason:"insufficient_tracking"}`
   is sent, and the bundle has `claim_status = insufficient_data`, `labels ⊇ ["partial_tracking"]`, and a body that
   contains both the factual sentence and "Insufficient tracking for this explanation.".
3. **Given** the Producer's plan includes a claim ID that was not approved, **When** release checks run,
   **Then** release is blocked with `CheckFailure(code="unapproved_claim")`, `fallback_reason = output_check_failed`,
   and the trace records the failure.
4. **Given** the model client is configured to delay 10 s, **When** further events arrive during the run,
   **Then** their `event`/`frame`/`metric` WS messages are broadcast without waiting for the workflow.

---

### User Story 4 - Inspect how the explanation was made (Priority: P2)

An analyst or judge opens the **Agent trace** tab in the Analyst drawer from any released, fallback or abstained
card. They see each step in order — Analyst (attempt 1), Verifier pre-checks, Verifier, Analyst (attempt 2, if any),
Producer, release checks, fallback — with its latency, token usage, tool calls (tool, arguments, returned evidence
IDs or errors such as `future_evidence`), the claims proposed with their templates and evidence chips, each verdict
with human-readable reason codes, the Producer's plan for Fan and Analyst, check results and any fallback reason.
The panel states that it shows decisions and evidence, not private model reasoning.

**Why this priority**: "Distinct agent decisions, evidence handoffs, rejected claims" is a judging dimension; the
trace is also the record used by evaluation (008) and Fabric (007).

**Independent Test**: `backend/tests/integration/test_traces_api.py` (GET returns a schema-valid `AgentTrace` for
released, fallback and abstained runs; 404 for unknown) and `frontend/tests/unit/AgentTrace.test.tsx` (renders
steps, blocked claim, verdict labels, fallback banner from a fixture trace).

**Acceptance Scenarios**:

1. **Given** any insight bundle with `trace_id = T`, **When** the client calls `GET /api/matches/{match_id}/traces/T`,
   **Then** it receives an `AgentTrace` whose `insight_id`, `moment_id`, `state_version` and `outcome` match the bundle.
2. **Given** a completed run, **When** the trace is finalized, **Then** one `FeedEnvelope{kind:"agent_trace", record_id:T}`
   is published on the `FeedBus` and the trace JSON is written to `TACTISTREAM_TRACE_DIR/{match_id}/{T}.json` when that directory is set.
3. **Given** the trace panel is open, **When** the viewer activates an evidence chip inside a step, **Then** the
   evidence view opens that record (same resolver as the card).

---

### User Story 5 - Many viewers, one validated narrative (Priority: P2)

Ten viewers watch the same match. Each moment triggers exactly one workflow run per `(moment_id, state_version)`;
every viewer, including late joiners and reconnecting browsers, receives the cached `InsightBundle` in its snapshot
or live stream. Changing mode, language or pinned player never triggers a model call. If a late event changes the
moment's state version, one new run produces `insight_version + 1` and the old version is revoked as `superseded`.

**Why this priority**: Build plan "Cache validated story variants … so each viewer does not trigger new model calls"
and the economics measure (008).

**Independent Test**: `backend/tests/integration/test_viewer_cache.py`: second viewer connects after release and
switches prefs → scripted client call count unchanged; duplicate trigger delivery → no second run.

**Acceptance Scenarios**:

1. **Given** a released bundle for `ins-0045` v1, **When** a second viewer connects, **Then** its `snapshot.insights`
   contains that bundle and the model client's call count does not change.
2. **Given** a run in progress for `(mom-0045, 512)`, **When** the same moment is re-detected with the same state version,
   **Then** no second run starts and both callers receive the same `WorkflowResult`.
3. **Given** `ins-0045` v1 is released, **When** the moment is re-detected with a higher state version, **Then** a new
   run releases v2 and an `insight_revoked{insight_id:"ins-0045", insight_version:1, reason:"superseded"}` is broadcast.

---

### User Story 6 - Compare against simpler configurations (Priority: P3)

The evaluation feature (008) runs the same frozen moments through three configurations — a deterministic summary,
a single agent with the same tools and templates, and the three-agent workflow — and compares support, coverage,
latency, tokens and recovery. This feature provides the two baselines and a common runner interface.

**Why this priority**: The build plan requires justifying multiple agents against simpler baselines; 008 depends on it,
but the live demo does not.

**Independent Test**: `backend/tests/unit/test_baselines.py`: all three runners accept the same `WorkflowContext`,
return `WorkflowResult`s whose bundles pass `check_release`, and report model calls (0 / 1 / ≥3).

**Acceptance Scenarios**:

1. **Given** the hero context, **When** `make_runner("deterministic").run(...)` executes, **Then** it makes zero model
   calls and releases a fact claim plus the rule-selected interpretation `interp.space_opened_by_run`.
2. **Given** the negative "run opens no channel" fixture, **When** the deterministic runner executes, **Then** it
   releases only the fact claim (`verified_fact`).
3. **Given** a scripted single-agent reply, **When** `make_runner("single_agent").run(...)` executes, **Then** it makes
   exactly one model call (role `single_agent`), skips the Verifier, and applies the same release checks.

### Edge Cases

- Analyst returns invalid JSON, more than 2 claims, or a schema-invalid object → `ModelError(kind="schema_invalid")` → fallback `model_error`; no extra retry outside the single repair round.
- Analyst uses a template ID not in the catalog, or a metric of a kind the template does not allow → `revise` with `template_kind_mismatch`.
- Analyst cites an evidence ID that does not exist in the snapshot (invented) → `reject` with `missing_evidence_id`; forgets to cite the metric used in a slot → `revise` with `missing_evidence_id`.
- Analyst names a player in a slot who appears in none of the cited evidence → `revise` with `missing_evidence_id`.
- Any tool call asking for data after `as_of_ms` returns `{"error":"future_evidence"}` with no partial data; the call and error are recorded in the trace.
- Tool payloads never include `match_id` (format `sim-{scenario}-{seed}` would leak the scenario label), generation manifest fields, scenario labels or outcomes after `as_of_ms`.
- Verifier model times out after pre-checks → fallback `timeout` (pre-checks alone never approve an interpretation).
- All claims rejected → fallback `verifier_rejected`; Analyst abstains with `no_supported_interpretation` and no claims → fallback `no_supported_claim`.
- Only fact claims approved (interpretation rejected) → released with `claim_status = verified_fact` and no Interpretation label.
- Producer requests an annotation not requested by an included approved claim, or one whose entity is invisible across the replay window → `unrequested_annotation` / `unresolvable_annotation` → fallback `output_check_failed`.
- Producer picks a title key not allowed by any included claim (e.g. `title.space_opened_before_shot` for a turnover claim) → `title_mismatch` → fallback.
- A rendered variant contains a causal-overreach term (en or hi lexicon) → `causal_overreach` → fallback (catalog lint makes this unreachable for reviewed templates; the check guards future edits).
- Release would occur after `expires_at_session_ms` → bundle still broadcast for timeline/replay; `narrative_status.fallback_reason = expired`; client display rules keep it off the live card.
- Late event produces a newer `state_version` for the moment while a run is in progress → the stale run's result is not broadcast (trace outcome `superseded`); the newer run proceeds.
- Playback reset during a run → run cancelled, trace outcome `cancelled`, nothing broadcast.
- Playback paused during a run → the wall-clock deadline keeps running; the bundle is released normally.
- Duplicate delivery of the trigger event → no second run (dedupe at ingest, plus cache key).
- More than 2 moments in flight → third waits on a per-match semaphore; its deadline still counts from its own trigger receipt, so it may fall back.
- Foundry throttling (HTTP 429) or transport error → `model_error` fallback; no retries inside the deadline.
- Token usage absent from a model response → recorded as `null`, never `0`.
- `POST /api/matches/{id}/fixtures` when `demo_fixtures=false` → 404 `fixtures_disabled`; an armed fixture applies to exactly one subsequent moment.
- Trigger event type without a fact template (e.g. `out_of_play`) → no fallback bundle; `narrative_status{stage:"fallback"}` only; event row remains.
- Fallback bundle itself fails `check_packet` (should be impossible) → nothing released; `narrative_status{stage:"fallback", fallback_reason:"output_check_failed"}`; error logged.

## Requirements *(mandatory)*

### Functional Requirements

**Agents and authority**

- **FR-001**: System MUST implement exactly three model-calling agents — Analyst, Verifier, Producer — with the authority in the build plan table; no other runtime component (except the single-agent evaluation baseline, FR-034) may call a model.
- **FR-002**: The Analyst MUST return an `AnalystOutput` (`claim.schema.json`) with at most 2 claims, each using a catalog `template_id` whose kind equals `claim.kind`, all template slots filled, `evidence_ids` covering every slot metric and the template's required evidence kinds, and MUST abstain (`abstain_reason = insufficient_tracking`) rather than propose a spatial interpretation when required tracking is absent.
- **FR-003**: Metric slot values in claims MUST be copied from tool output (`SlotValue.value`, `SlotValue.unit`); agents never compute, round or estimate numbers. User-facing text always uses the `MetricEngine` value, not the agent-supplied value.
- **FR-004**: The Verifier MUST run deterministic pre-checks before any model call and emit a pre-check `Verdict` per claim: evidence IDs exist in the as-of snapshot (`missing_evidence_id`), no evidence after `as_of_ms` (`future_evidence`), slot values equal the `MetricEngine` recomputation at the template precision (`value_mismatch`), units match metric and template (`unit_mismatch`), template exists and its kind and allowed metric kinds match (`template_kind_mismatch`), slot players appear in cited evidence (`missing_evidence_id`), required tracking available (`insufficient_tracking`). Decision mapping per data-model.md "Reason codes".
- **FR-005**: The Verifier model MUST judge only claims not rejected by pre-checks, for `unsupported_causality` and `counterevidence`, given recomputed evidence and a pattern-specific counterevidence pack; the final decision per claim MUST be the stricter of pre-check and model decisions (`reject` > `revise` > `approve`), with reason codes unioned.
- **FR-006**: System MUST allow at most one repair round: only if at least one final verdict is `revise` and at least `TACTISTREAM_REPAIR_MIN_REMAINING_MS` (default 3000) remain before the deadline. Repaired claims receive new claim IDs (`clm-{trigger_seq:04d}-{n}` continuing the sequence); approved claims are kept; rejected claims are never resubmitted. Without repair, `revise` counts as rejected.
- **FR-007**: The Producer MUST return a `ProducerOutput` with a `ModePlan` for `fan` and `analyst` using approved claim IDs only; it never writes prose.
- **FR-008**: Bundle assembly MUST be deterministic: for each mode × language (`fan|analyst` × `en|hi`) the packet `title` comes from `render_title` and `body` from concatenated `render_claim` outputs in plan order; `claim_status` is `interpretation_supported` if the mode plan includes an interpretation claim, else `verified_fact`; `labels` include `synthetic`, `interpretation` (if any interpretation), `partial_tracking` (if `tracking_coverage < 1`), `demo_fixture` (if a fixture was armed); `evidence_ids` is the ordered union of included claims' evidence; `render` timing per data-model.md "Bundle timing".

**Tools, context and checks**

- **FR-009**: `AgentTools` MUST expose `get_match_snapshot`, `get_event_window(start_ms, end_ms)`, `get_metric(metric_id)`, `inspect_geometry(kind, params, at_ms)` and `build_recap_candidates(prefs)` as read-only functions bound to one `MatchSnapshot` and `MetricEngine`, returning compact JSON with IDs (contracts/tools.md); any request beyond `as_of_ms` MUST return error `future_evidence`; payloads MUST NOT contain `match_id`, generation manifest fields, scenario labels or display names; every call is recorded as a `ToolCallRecord`.
- **FR-010**: `WorkflowContext` MUST carry the immutable snapshot, moment, `as_of_ms`, `state_version`, metric results, claim ledger, verdicts, `NarrativePrefs`, `trigger_receipt_ms`, `deadline_ms`, `trace_id`, `insight_id`, `insight_version`, armed fixture and dependencies; the ledger is append-only.
- **FR-011**: `check_release` MUST extend 001 `check_packet` and block release when: a packet claim ID is not approved (`unapproved_claim`); an annotation is not in requested ∩ approved for the mode's claims (`unrequested_annotation`) or does not resolve to a scene entity (`unresolvable_annotation`); a number, player name or evidence ID is not in evidence (`unsupported_number`, `unsupported_player`, `unknown_evidence`); evidence lies after `as_of_ms` (`future_evidence`); the title key is not allowed by included claims (`title_mismatch`); a template is unknown (`unknown_template`); a causal-overreach term appears (`causal_overreach`); numbers or player IDs differ across the four variants (`variant_inconsistent`); timing is invalid or expired (`invalid_timing`, `expired`); a packet fails its JSON Schema (`schema_invalid`).
- **FR-012**: The causal-overreach lexicon MUST cover at least en: `caused`, `causes`, `cause`, `forced`, `forces`, `because of`, `because`, `deliberately`, `deliberate`, `intended`, `intentionally`, `made him`, `made her`, `made them`, `so that`; hi: `के कारण`, `की वजह से`, `कारण बना`, `कारण बनी`, `मजबूर`, `जानबूझकर`, `इरादा`, `इरादे`, `इरादतन`; matched case-insensitively on word boundaries in every variant's title and body; a catalog lint test MUST prove no reviewed template contains a lexicon term.

**Deadline, fallback, abstention**

- **FR-013**: The narrative deadline MUST be `trigger_receipt_ms + TACTISTREAM_NARRATIVE_DEADLINE_MS` (default 8000) in the same clock domain used to stamp `server_receipt_ms`; each model call's timeout is `min(role_cap, remaining − reserve − Σ downstream minimums)` (plan.md "Budgets"); if a step's budget is below its minimum the step is not started and the run falls back with `timeout`; an outer guard guarantees a fallback bundle is broadcast by the deadline.
- **FR-014**: On timeout, model error, zero approved claims, no supported claim, release-check failure or expiry, the workflow MUST release the deterministic fallback bundle from `narrative/factual.py` (`build_fallback_bundle`): fact template chosen by trigger event type (data-model.md "Fallback templates"), `claim_status = fallback_template`, `labels ⊇ ["synthetic","fallback"]`, and send `narrative_status{stage:"fallback", fallback_reason}` with reasons `timeout | model_error | verifier_rejected | no_supported_claim | output_check_failed | expired`. The failed attempt is kept only in the trace.
- **FR-015**: Before any model call, a gate MUST abstain when the moment pattern is `space_creation`, `press_turnover` or `switch_escape` and `tracking_coverage < TACTISTREAM_MIN_TRACKING_COVERAGE` (default 0.8) or any moment metric is `unavailable` with `insufficient_tracking`; the workflow also abstains when the Analyst abstains with `insufficient_tracking` or every claim is rejected solely for `insufficient_tracking`. Abstention releases `build_abstain_bundle` (fact sentence + `status.insufficient_tracking`, `claim_status = insufficient_data`, `labels ⊇ ["synthetic","partial_tracking"]`) and sends `narrative_status{stage:"abstained", fallback_reason:"insufficient_tracking"}`.
- **FR-016**: The fast path (event → state → metrics → WS) MUST NOT await any workflow step; workflows run as background tasks with a per-match concurrency limit (`TACTISTREAM_NARRATIVE_MAX_CONCURRENCY`, default 2).

**Status, latency, trace, cache**

- **FR-017**: The server MUST broadcast `narrative_status` messages in order `analysing → verifying → [analysing → verifying] → producing → checking → released`, or end early with `fallback` / `abstained`; each carries `moment_id` and `trace_id`.
- **FR-018**: Narrative latency (`release_broadcast_ms − trigger_receipt_ms`) MUST be recorded for every explained moment in `LatencyRecorder` as kind `narrative` with attributes `outcome` (`released|fallback|abstained`) and `fallback_reason`; percentiles can be filtered by outcome and fallbacks are counted separately, never dropped.
- **FR-019**: Every run MUST produce an `AgentTrace` (contracts/trace.md) containing steps with role, attempt, prompt version, input IDs, tool calls and result IDs, output payload, verdicts, token usage, latency, error and fallback reason — and no private chain-of-thought; traces are stored per `trace_id`, served at `GET /api/matches/{match_id}/traces/{trace_id}`, written to `TACTISTREAM_TRACE_DIR` when set, published as `FeedEnvelope{kind:"agent_trace"}`, and mirrored as OpenTelemetry spans with token-usage attributes.
- **FR-020**: `NarrativeCache` MUST guarantee one workflow run per `(moment_id, state_version)` (concurrent callers share the result) and store bundles by `(match_id, insight_id, insight_version)`; WS snapshots and reconnects are served from the cache; viewer preference changes never cause model calls.
- **FR-021**: Moment insights MUST use `insight_id = ins-{trigger_sequence:04d}`; `insight_version` increments per release for the same ID (including versions previously used by 001 fact cards); when a newer version releases, the previous version is revoked with reason `superseded`; a run whose state version is no longer current when it finishes MUST NOT be broadcast.
- **FR-022**: Only newly detected moments with pattern in `space_creation | press_turnover | switch_escape | shot` and `rank_score ≥ TACTISTREAM_NARRATIVE_MIN_RANK` (default 0.4) are explained.

**Catalog and prompts**

- **FR-023**: The narrative catalog MUST add `fact.shot`, `fact.turnover`, `fact.switch`, `interp.space_opened_by_run`, `interp.defender_followed_runner`, `interp.pressure_preceded_turnover`, `interp.switch_escaped_pressure`, `status.insufficient_tracking` and the `title.*` keys in data-model.md, each declaring kind, slots (type, allowed metric kinds, unit, precision), required evidence kinds, `requires_tracking`, allowed title keys and eligible patterns in `narrative/catalog/spec.json`, with fan and analyst text in `en.json` and `hi.json`. Interpretations use "helped create", "coincided with", "preceded" — never intent or causation.
- **FR-024**: Agent instructions MUST live in versioned files `agents/prompts/{analyst,verifier,producer,single_agent}.md` with front matter `prompt_version`; the version used is recorded in every trace step.

**Model access and configuration**

- **FR-025**: All model calls MUST go through `ModelClient.complete_json(role, system, user, schema_ref, timeout_s) -> ModelResponse`; implementations: `FoundryModelClient` (Microsoft Agent Framework chat client against the Foundry deployment, `DefaultAzureCredential`, structured JSON output), `ScriptedModelClient` (keyed by `(role, moment_id, attempt)`), `TimeoutModelClient`, `FaultInjectingModelClient`. Responses are validated against the role's schema; invalid output is a model error.
- **FR-026**: `Settings.agents` MUST select `off` (001 behaviour: no moment narratives), `scripted` (offline demo using `TACTISTREAM_AGENT_SCRIPTS`) or `foundry`.
- **FR-027**: The workflow MUST be built from Microsoft Agent Framework workflow executors (Analyst → Verifier → conditional repair edge → Producer → Checks), with the plain-asyncio fallback in research.md R1 if the framework blocks progress for more than 2 hours.

**Demo fixtures**

- **FR-028**: When `TACTISTREAM_DEMO_FIXTURES=true`, `POST /api/matches/{match_id}/fixtures {"inject":"bad_claim"|"model_timeout"}` MUST arm the fixture for the next explained moment only; `bad_claim` replaces the Analyst's attempt-1 output with the deterministic mutation in data-model.md (scripted or real model alike); `model_timeout` makes every Analyst call hang until its timeout. Runs with a fixture are marked in the trace (`fixture`, `injected_fault`) and their packets carry the `demo_fixture` label. When disabled the endpoint returns 404 `fixtures_disabled`; `/healthz` reports `demo_fixtures`.

**Frontend**

- **FR-029**: The card area MUST show a narrative stage indicator (`aria-live="polite"`) for the active moment: "Analysing…", "Verifying…", "Producing…", "Checking…", then hide on release, show "Facts only — {reason}" on fallback and "Insufficient tracking for this explanation" on abstention (en/hi chrome strings).
- **FR-030**: `InsightCard` MUST show an **Interpretation** chip when `labels` include `interpretation`, **Facts only** for `fallback`, **Partial tracking** for `partial_tracking`, **Demo fixture** for `demo_fixture`, and an "How was this made?" control opening the Agent trace tab.
- **FR-031**: `AgentTrace` (in `AnalystDrawer`, tab "Agent trace") MUST render each step (role, attempt, latency, tokens, prompt version), tool calls with result IDs or error codes, claims with template ID, kind, evidence chips and verdict badge (Approved / Revise / Rejected) with reason labels, blocked claims under a "Blocked claim" heading with "revised as {claim_id}" links, Producer plans per mode, check failures, and a fallback/abstain banner; plus the note "Decisions and evidence only — private model reasoning is not recorded."
- **FR-032**: `FixtureControls` MUST render "Inject bad claim" and "Inject model timeout" buttons only when `/healthz` reports `demo_fixtures: true`, visibly labelled "Demo fixture".

**Testing and baselines**

- **FR-033**: All agent logic MUST be tested with `ScriptedModelClient` and `FakeClock` (no network); the live Foundry test is `@pytest.mark.live`. Every `CheckFailure` code and every fallback reason has a test that blocks release.
- **FR-034**: `agents/baselines.py` MUST provide a deterministic-summary runner (zero model calls; fact + rule-selected interpretation) and a single-agent runner (one model call producing analyst claims and both mode plans) that use the same tools, catalog, bundle assembly and `check_release`, behind `make_runner(kind)` for 008.

### Key Entities

- **CandidateMoment** (003, contract): the window to explain; `moment_id`, `pattern`, `trigger_event_id`, `window`, `metric_ids`, `tracking_coverage`, `state_version`.
- **MatchSnapshot** (003): immutable as-of view of match state used by tools; never mutated during a run.
- **WorkflowContext**: everything a run needs (FR-010); deadline and trace ID included.
- **Claim / AnalystOutput / Verdict / VerifierOutput / ModePlan / ProducerOutput** (contract `claim.schema.json`): typed handoffs between agents.
- **ClaimLedger / ClaimRecord**: append-only per-run record of every claim, its attempt, pre-check verdict, model verdict, final verdict, status (`approved|rejected|revised|superseded|unused`) and `superseded_by`.
- **InsightBundle / InsightPacket** (contract): the released render instruction set, 4 variants.
- **AgentTrace / TraceStep / ToolCallRecord** (proposed contract `agent_trace.schema.json`): public decision record of a run.
- **WorkflowResult**: outcome, bundle, fallback reason, ledger, producer output, check failures, trace, usage, latency.
- **TemplateSpec / Catalog**: narrative template metadata and text for en/hi.
- **NarrativeCache**: run de-duplication and bundle store.
- **FixtureArm**: per-match one-shot demo fixture state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In scripted mode the hero moment releases a supported card (fan/en body exactly "Blue 9's run helped create room for the pass.", `claim_status = interpretation_supported`) in 10/10 consecutive runs (`agents.spec.ts --repeat-each=10` for the browser, `test_happy_path` for the backend); in Foundry mode, 5 recorded live runs are reported in research.md with outcome, latency and tokens per run (the target is ≥ 4/5 released; whatever the result, it is reported).
- **SC-002**: With the `bad_claim` fixture armed, 10/10 scripted runs show a blocked claim (non-`approve` final verdict with reason codes) in the trace, and 0 released packets contain a blocked claim ID; the browser trace panel shows "Blocked claim".
- **SC-003**: 100% of timeout fixtures release a fallback bundle no later than 8000 ms after trigger receipt: 20 parametrized FakeClock cases (hangs placed in each step and attempt) plus 5 real-clock runs of the `model_timeout` fixture, each with measured latency recorded.
- **SC-004**: 0 released packets fail deterministic checks: an audit test re-runs `check_release` independently on every variant released while replaying the demo match and all fixtures in scripted mode and reports the count checked (expected > 0) and failures (expected 0).
- **SC-005**: A trace is retrievable (HTTP 200, schema-valid) for 100% of released, fallback and abstained insights in the audit run.
- **SC-006**: A second viewer, preference switches and duplicate triggers cause 0 additional model calls (asserted on the scripted client's call log).
- **SC-007**: Every `CheckFailure` code (14) and every fallback reason (6) plus abstention has at least one test proving release is blocked or degraded as specified (coverage table in tasks.md checkpoint).
- **SC-008**: The missing-tracking fixture yields an abstained status card with 0 model calls while the ordinary event rows for the same events remain in the UI.
- **SC-009**: With a model client delaying 10 s, the fast path still broadcasts each new event within 50 ms of ingest in the integration test (no awaiting of workflow tasks).
- **SC-010**: Narrative latency samples are recorded for 100% of explained moments in the audit run (samples == explained moments), split by outcome.
- **SC-011**: 0 tool responses in the audit run contain a timestamp after `as_of_ms`, a `match_id`, or any key from the deny-list (`scenario`, `label`, `manifest`, `intended`, `outcome_after`).

## Assumptions

- Feature 003 provides `MatchState.snapshot(as_of_ms) -> MatchSnapshot` (immutable), `MetricEngine.compute(kind, snapshot, anchor_event_id) -> MetricResult`, `detect_moments(snapshot, metrics) -> list[CandidateMoment]`, metrics geometry helpers, and calls a session hook for each newly detected moment. Names follow the registry; if 003 adjusts signatures, adapters live in `agents/tools.py` only.
- Feature 002 supplies the demo match `demo-blue-amber-001` (space-creation hero), press-turnover and switch-escape scenarios, the negative "run opens no channel" scenario and the missing-tracking fixture; 004 freezes small windows of them into `data/fixtures/` so agent tests never depend on simulator changes. Contract-example IDs (`mom-0045`, `evt-0042`, `metric-channel-0042`, 3.4 m) are used throughout; if the frozen fixture differs, `backend/tests/fixtures/hero_ids.py` is the single place to update.
- The Foundry deployment supports JSON-schema structured output; if it supports only JSON mode, the client requests JSON mode and relies on post-validation (same failure semantics).
- Hindi template text here is a reviewed-later draft; 006 performs terminology review. Numbers use Western Arabic digits in both languages.
- The judged deployment runs with `TACTISTREAM_DEMO_FIXTURES=true` so the demo can show the blocked-claim and timeout fixtures; every fixture effect is labelled in the UI.
- Proposed contract changes in plan.md "Proposed cross-cutting changes" (agent trace schema, `SlotValue.value/unit`, `demo_fixture` label, `no_supported_claim` fallback reason) are accepted before Phase 2 tasks T005–T007 run.
- One match per session, ≤ 10 viewers, ≤ 2 concurrent workflows per match (constitution VII).
