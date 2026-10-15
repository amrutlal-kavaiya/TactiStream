---
description: "Task list for 004 agent workflow"
---

# Tasks: Agent Workflow

**Input**: `specs/004-agent-workflow/` (spec, plan, research, data-model, contracts/agent-io.md, contracts/tools.md, contracts/trace.md, quickstart)

**Prerequisites**: 001 complete; 003 provides `MatchState.snapshot`, `MatchSnapshot`, `MetricEngine`, `detect_moments`,
`CandidateMoment` and the session moment hook; 002 provides the scenarios frozen in T008. Proposed contract changes
C1–C4 (plan.md) approved before T005.

**Tests**: REQUIRED (constitution V). Each implementation task is preceded by a test task that must fail first for the
stated reason. All agent tests use `ScriptedModelClient` + `FakeClock` (no network); live tests are `@pytest.mark.live`.

**Format**: `[ID] [P?] [Story] Description` — `[P]` = parallelizable (different files, no unmet dependency).

## Phase 1: Setup

- [x] T001 Create `backend/src/tactistream/agents/prompts/`, `backend/tests/fixtures/__init__.py`, `data/fixtures/agent_scripts/`; in `backend/pyproject.toml` include package data `tactistream/agents/prompts/*.md` and `tactistream/narrative/catalog/*.json` so they ship in the wheel/container
- [x] T002 [P] Extend `.env.example` (names and safe defaults only): `TACTISTREAM_DEMO_FIXTURES=false`, `TACTISTREAM_TRACE_DIR=`, `TACTISTREAM_AGENT_SCRIPTS=data/fixtures/agent_scripts/demo-blue-amber-001.json`, `TACTISTREAM_ANALYST_TIMEOUT_MS=3500`, `TACTISTREAM_VERIFIER_TIMEOUT_MS=2500`, `TACTISTREAM_PRODUCER_TIMEOUT_MS=1500`, `TACTISTREAM_RELEASE_RESERVE_MS=400`, `TACTISTREAM_REPAIR_MIN_REMAINING_MS=3000`, `TACTISTREAM_MIN_TRACKING_COVERAGE=0.8`, `TACTISTREAM_NARRATIVE_MIN_RANK=0.4`, `TACTISTREAM_NARRATIVE_MAX_CONCURRENCY=2`, `FOUNDRY_MODEL_DEPLOYMENT_FAST=` (optional)
- [x] T003 Write failing `backend/tests/unit/test_settings_agents.py`: defaults equal the T002 values (`narrative_deadline_ms == 8000`, `demo_fixtures is False`, `trace_dir is None`); env override `TACTISTREAM_DEMO_FIXTURES=true` → `True`; `TACTISTREAM_AGENTS=scripted` without an existing scripts file → `ValidationError` naming `TACTISTREAM_AGENT_SCRIPTS`; `analyst_timeout_ms < 800` → `ValidationError`
- [x] T004 Extend `backend/src/tactistream/settings.py` (`Settings`) with the T002 fields and validators; add `Settings.agent_budgets() -> AgentBudgets`. Run T003 → green

**Checkpoint**: `make test` green; settings documented in `.env.example`.

---

## Phase 2: Foundational (blocks all stories)

### Contracts (after C1–C4 approval)

- [x] T005 Write failing `backend/tests/contract/test_agent_contracts.py`: `contracts/examples/agent_trace.json` validates against `agent_trace.schema.json` and round-trips through `AgentTrace`; a `SlotValue` with `value`/`unit` validates; a packet with label `demo_fixture` validates; `NarrativeStatus{stage:"fallback", fallback_reason:"no_supported_claim"}` validates; negative: a `TraceStep` with an extra `reasoning` field is rejected by schema and model; `AgentTrace(outcome="fallback")` without `fallback_reason` is rejected by the model validator; `FeedEnvelope{kind:"agent_trace"}` parses its payload into `AgentTrace`
- [x] T006 Apply proposed changes C1–C4: add `contracts/schemas/agent_trace.schema.json` (contracts/trace.md), `contracts/examples/agent_trace.json` (bad-claim example, complete), `SlotValue.value`/`unit` in `contracts/schemas/claim.schema.json`, `demo_fixture` label in `insight_packet.schema.json`, `no_supported_claim` in `ws_message.schema.json`, `agent_trace` payload `$ref` in `feed_envelope.schema.json`, row in `contracts/README.md`; bump touched schemas' `schema_version` pattern docs to 1.1 per contracts README; update `contracts/examples/analyst_output.json` metric slots with `value`/`unit`; run `make contracts` to regenerate `frontend/src/contracts/generated.ts`
- [x] T007 Implement `backend/src/tactistream/contracts/trace.py` (`AgentTrace`, `TraceStep`, `ToolCallRecord`, `ClaimTraceEntry`, `TraceCheckFailure`, `Usage` with invariants from contracts/trace.md) and update `contracts/claim.py`, `contracts/insight.py`, `contracts/ws.py`, `contracts/envelope.py`; add the new pair to the 001 table in `backend/tests/contract/test_examples.py`. Run T005 → green

### Frozen fixtures

- [ ] T008 Freeze fixtures from 002 into `data/fixtures/hero_space_creation.jsonl`, `hero_missing_tracking.jsonl`, `press_turnover.jsonl`, `switch_escape.jsonl`, `run_no_channel.jsonl` (metadata + events + 10 Hz frames of the moment window ±1 s, as specified in data-model.md "Hero fixture"); record actual IDs and values in `backend/tests/fixtures/hero_ids.py` (`HERO_MOMENT_ID="mom-0045"`, `PASS_EVENT_ID="evt-0042"`, `SHOT_EVENT_ID="evt-0045"`, `FUTURE_EVENT_ID="evt-0046"`, `CHANNEL_METRIC_ID="metric-channel-0042"`, `CHANNEL_VALUE=3.4`, `PROGRESS_VALUE=13.1`, …); write `backend/tests/unit/test_hero_fixture.py` asserting every line validates as `FeedEnvelope`, `detect_moments` on the hero snapshot returns `HERO_MOMENT_ID` with pattern `space_creation` and coverage 1.0, `MetricEngine.compute("channel", …, PASS_EVENT_ID).value == CHANNEL_VALUE`, and the missing-tracking variant yields coverage < 0.8 with channel `unavailable/insufficient_tracking`
- [ ] T009 [P] Implement `backend/tests/fixtures/hero_world.py` (`load_world(name) -> World(state, snapshot_at(as_of), metrics, moments, metadata, evidence)`) and `backend/tests/fixtures/clock_driver.py` (`async run_with_clock(coro, clock: FakeClock, step_ms=50, limit_ms=20000)` advancing the 001 `FakeClock` until the coroutine finishes; raises if `limit_ms` exceeded), with a self-test in `backend/tests/unit/test_clock_driver.py` (a coroutine sleeping 7900 ms finishes at clock 7900–7950)

### Narrative catalog and rendering

- [ ] T010 [P] Write failing `backend/tests/unit/test_catalog.py`: `load_catalog()` loads `spec.json`, `en.json`, `hi.json`; key sets of the three files are identical; every claim/status template has `fan` and `analyst` text in both languages; every `{slot}` placeholder in text exists in the spec slots (or is a derived slot) and vice versa; every `title_keys` entry exists with kind `title`; every interpretation has `requires_tracking=true` and ≥ 1 required evidence kind; every pattern in `space_creation|press_turnover|switch_escape|shot` has ≥ 1 fact and (except shot) ≥ 1 interpretation template; lint: no en/hi text contains a `CAUSAL_LEXICON` term (imported from `agents/checks.py`); hi text contains no Devanagari digits (`०-९`)
- [ ] T011 [P] Implement `backend/src/tactistream/narrative/templates.py` (`SlotSpec`, `TemplateSpec`, `Catalog`, cached `load_catalog()`) and write `narrative/catalog/spec.json`, convert `narrative/catalog/en.json` and `hi.json` to text-only with every key and text in data-model.md "Template table" (keeping 001 `fact.forward_pass`, `title.forward_pass`, `label.*`); define `CAUSAL_LEXICON` in `backend/src/tactistream/agents/checks.py` (spec FR-012). Run T010 → green
- [ ] T012 Write failing `backend/tests/unit/test_render_interp.py` using the hero world: `render_claim("interp.space_opened_by_run", slots, "fan", "en").text == "Blue 9's run helped create room for the pass."`; analyst/en == "Amber 4 shifted toward Blue 9 while the passing channel widened by 3.4 m. The next forward pass used that space."; fan/hi contains "ब्लू 9"; analyst/hi contains "3.4" and "एम्बर 4"; with `SlotValue.value=5.3` the rendered value is still `3.4` (engine value wins); metric slot pointing to an `unavailable` metric → `TemplateError`; `fact.shot` fan/en == "Blue 11 took a shot: on target." and analyst/en ends with "(evt-0045)."; `status.insufficient_tracking` fan/en == "Insufficient tracking for this explanation."; `RenderedText.numbers` identical across the four variants of every hero claim; `render_title("title.space_opened_before_shot", …)` en/hi strings per data-model.md
- [ ] T013 Extend `backend/src/tactistream/narrative/render.py` to use `Catalog` specs (slot types, precision, derived `outcome` slot, `event_time` rendering, metric values from a `metric_lookup: Callable[[str], MetricResult]` argument added as keyword-only with the 001 call sites updated). Run T012 and 001 `test_render.py` → green

### Model client

- [x] T014 [P] Write failing `backend/tests/unit/test_model_client.py`: `ScriptedModelClient` returns the reply for `("analyst","mom-0045",1)` with `usage_in=1900`; unknown key → `ModelError(kind="script_missing")`; `delay_ms=1400` completes only after `FakeClock.advance(1400)` and `latency_ms == 1400`; `error:"invalid_json"` → `ModelError("invalid_json")`; reply data violating `AnalystOutput` (3 claims) → `ModelError("schema_invalid")`; `usage` omitted → `usage_in is None`; `calls` records `(role, moment_id, attempt, timeout_s)`; `TimeoutModelClient(inner, clock)` with `timeout_s=1.0` over a 5000 ms reply raises `ModelTimeout` at clock +1000 and cancels the inner call; scripted lookup reads `moment_id`/`attempt` from the user JSON (`moment.moment_id`, `attempt`)
- [x] T015 [P] Implement `backend/src/tactistream/agents/model_client.py`: `Role`, `SchemaRef`, `ModelResponse`, `ModelError`, `ModelTimeout`, `ModelClient` protocol, `ScriptedModelClient` (+ `load_script(path)`), `TimeoutModelClient`, `validate_role_output(schema_ref, data)` using 001 `schema_registry` (and the internal `SingleAgentOutput` Pydantic schema). Run T014 → green

### Tools

- [ ] T016 [P] Write failing `backend/tests/unit/test_agent_tools.py` (hero world, `as_of=46500`): `get_match_snapshot()` has `as_of_ms`, 22 players with no `display_name`, `recent_event_ids[-1] == "evt-0045"`; `get_event_window(36000, 46500)` returns events ordered by seq with `evt-0042` fields per contracts/tools.md; `get_event_window(36000, 47000)` → `{"error":"future_evidence"}` with no `events` key; span 20000 → `invalid_window`; `get_metric("metric-channel-0042")` value 3.4 unit m and registers the ID in `EvidenceIndex`; `get_metric("metric-channel-0046")` → `future_evidence`; `get_metric("metric-xg-0042")` → `unknown_metric`; `inspect_geometry("positions", {"player_ids":["blue-09"]}, 42300)` returns frame `frm-000423`; `at_ms=47000` → `future_evidence`; missing-tracking world `distance(blue-09, amber-04)` at 41000 → `insufficient_tracking`; every call appends one `ToolCallRecord` with `result_ids`; leakage audit: recursively no key in the deny-list (`match_id`, `scenario`, `label`, `manifest`, `intended`, `outcome_after`, `seed`) and no `t_ms`/`at_ms`/`end_ms` > 46500 in any ok response; `json.dumps(analyst_pack)` ≤ 8192 bytes
- [ ] T017 [P] Implement `backend/src/tactistream/agents/tools.py` (`AgentTools`, `GeometryKind`, `ToolCallRecord` sink, `metric_result()`, pattern recipes `analyst_pack(ctx)` / `counterevidence_pack(ctx)` per data-model.md "Evidence-pack recipes"; geometry via 003 `metrics/geometry`). Run T016 → green

### Context, ledger, trace, latency

- [ ] T018 [P] Write failing `backend/tests/unit/test_context.py`: `ClaimLedger.next_claim_id()` yields `clm-0045-1`, `clm-0045-2`, then `clm-0045-3` after a repair; records cannot be removed (no API) and `set_verdicts` on an unknown ID raises; `combine_verdicts(approve, reject).decision == "reject"`, `(revise, approve) → revise`, reason codes unioned without `ok`; `ctx.deadline_ms == trigger_receipt_ms + 8000`; `budget_ms("analyst")` at t=0 == 3500, at remaining 3000 == `min(3500, 3000-400-600-600) == 1400`, and returns < `min_ms` when remaining 2000 (caller must skip)
- [ ] T019 [P] Implement `backend/src/tactistream/agents/context.py` (`WorkflowContext`, `WorkflowDeps`, `AgentBudgets`, `ClaimLedger`, `ClaimRecord`, `NarrativePrefs`, `FixtureKind`, `FallbackReason`, `NarrativeStage`) and `combine_verdicts` in `backend/src/tactistream/agents/verifier.py`. Run T018 → green
- [ ] T020 [P] Write failing `backend/tests/unit/test_trace.py`: `TraceRecorder` assigns contiguous step indices, attaches tool calls to the open step, `finalize()` returns an `AgentTrace` that validates against `agent_trace.schema.json`; serialized JSON contains no key `reasoning`, `thought`, `prompt` or `system`; `usage.tokens_in` is `null` if any step usage is `null`; `TraceStore.put/get` by `(match_id, trace_id)`; with `trace_dir=tmp_path` the file `tmp_path/demo-blue-amber-001/{trace_id}.json` equals the model dump; `trace_envelope(trace, published_ms)` → `FeedEnvelope(kind="agent_trace", record_id=trace_id)`
- [ ] T021 [P] Implement `backend/src/tactistream/agents/trace.py` (`TraceRecorder`, `TraceStore`, `trace_envelope`, OTel span per step with `gen_ai.*` and `tactistream.*` attributes; `new_trace_id()` from the current span context or `uuid4().hex`, injectable for tests). Run T020 → green
- [ ] T022 [P] Write failing `backend/tests/unit/test_latency_filters.py`: record `narrative` samples 1000..10000 with `outcome` released for odd and fallback for even → `percentile("narrative", 95, outcome="released")` uses only released samples; `count("narrative", outcome="fallback") == 5`; unfiltered `percentile` includes all; 001 `test_latency.py` still passes
- [ ] T023 [P] Extend `backend/src/tactistream/telemetry/latency.py` (`LatencyRecorder.percentile(kind, p, **where)`, `count(kind, **where)`; OTel attributes include `outcome`, `fallback_reason`). Run T022 → green

**Checkpoint**: contracts, fixtures, catalog, model client, tools, context, trace, latency all green. No agent behaviour yet.

---

## Phase 3: User Story 1 — Supported explanation for the hero moment (P1) 🎯 MVP

**Goal**: hero moment → Analyst → Verifier → Producer → checks → released bundle over WS with stage updates.

**Independent Test**: `pytest backend/tests/unit/test_workflow.py::test_happy_path backend/tests/integration/test_narrative_flow.py` and `npx playwright test agents.spec.ts -g "hero card"`.

- [ ] T024 [P] [US1] Write failing `backend/tests/unit/test_analyst.py`: `build_analyst_input(ctx, attempt=1)` matches the shape in contracts/agent-io.md (keys `input_version, attempt, as_of_ms, next_claim_ids, moment, snapshot, events, metrics, geometry, templates, annotation_formats`), lists only templates whose `patterns` include `space_creation`, and contains no display names; `run_analyst` with the scripted hero reply appends 2 `ClaimRecord`s with IDs `clm-0045-1/2` even if the reply used other IDs; records one trace step with `prompt_version == "analyst.v1"`, `budget_ms == 3500`, tool calls from the pack; a reply with `abstained=true, abstain_reason="insufficient_tracking"` returns it unchanged with no ledger entries; prompt front matter missing `prompt_version` → `PromptError` at load
- [ ] T025 [US1] Implement `backend/src/tactistream/agents/analyst.py` (`build_analyst_input`, `run_analyst`, `PromptSet.load()` reading `agents/prompts/*.md` front matter) and write `backend/src/tactistream/agents/prompts/analyst.md` (analyst.v1, text from contracts/agent-io.md). Run T024 → green
- [ ] T026 [P] [US1] Write failing `backend/tests/unit/test_verifier_prechecks.py`, one test per row of data-model.md "Reason codes" using hero claims mutated in-test: cited `evt-9999` → reject `missing_evidence_id`; slot metric not in `evidence_ids` → revise `missing_evidence_id`; interp claim missing a `defender_follow` metric in evidence → revise `missing_evidence_id`; slot player `blue-07` not in any cited evidence → revise `missing_evidence_id`; cited `evt-0046` → reject `future_evidence`; `channel_gain.value=5.3` → revise `value_mismatch`; `value=3.44` (rounds to 3.4) → approve; `value` missing → revise `value_mismatch`; `unit="ratio"` → revise `unit_mismatch`; `kind="fact"` on `interp.*` → revise `template_kind_mismatch`; unknown template `interp.run_forced_defender` → revise `template_kind_mismatch`; `channel_gain` pointing at `metric-pressure-0042` → revise `template_kind_mismatch`; missing-tracking world interp claim → reject `insufficient_tracking`; valid hero claims → approve `["ok"]`; multiple problems → stricter decision with all codes
- [ ] T027 [US1] Implement `precheck_claims(claims, ctx) -> list[Verdict]` in `backend/src/tactistream/agents/verifier.py` (uses `AgentTools.metric_result` for recomputation and `Catalog` specs; records a `verifier_precheck` trace step). Run T026 → green
- [ ] T028 [P] [US1] Write failing `backend/tests/unit/test_verifier.py`: claims rejected by pre-checks are absent from the model input; input includes `recomputed` and the space_creation `counterevidence` metrics (`metric-pressure-0042`, `metric-receiver_separation-0042`); model `approve` + pre-check `revise` → final `revise`; model `reject` `counterevidence` + pre-check approve → final `reject`; model omits a verdict for a claim → final `revise` with `unsupported_causality`; model uses reason code `value_mismatch` → `ModelError("schema_invalid")`; when every claim was rejected by pre-checks no model call is made; `ModelTimeout` propagates
- [ ] T029 [US1] Implement `build_verifier_input`, `run_verifier` in `backend/src/tactistream/agents/verifier.py` and write `agents/prompts/verifier.md` (verifier.v1). Run T028 → green
- [ ] T030 [P] [US1] Write failing `backend/tests/unit/test_producer.py`: `build_producer_input` includes only approved claims with `title_keys`, `requested_annotations` and code-rendered `preview.fan_en`/`analyst_en`; `run_producer` with the scripted hero reply returns `ProducerOutput`; `assemble_bundle(plan, ctx, release_session_ms=47000)` returns 4 variants with `insight_id="ins-0045"`, fan/en title "Space opened before the shot" and body "Blue 9's run helped create room for the pass.", analyst/en body equal to the table in contracts/agent-io.md, fan `claim_status="interpretation_supported"`, labels `["synthetic","interpretation"]`, `evidence_ids` = ordered union of included claims, `render.show_from_ms=47000`, `show_until_ms=53000`, `expires_at_session_ms=76500`, `replay_window={36000,46500}`, annotations/priority/panel from the plan, `trace_id` from ctx; a plan with only a fact claim → `claim_status="verified_fact"` and no `interpretation` label; with `ctx.fixture="bad_claim"` labels include `demo_fixture`
- [ ] T031 [US1] Implement `backend/src/tactistream/agents/producer.py` (`build_producer_input`, `run_producer`, `assemble_bundle`) and `agents/prompts/producer.md` (producer.v1). Run T030 → green
- [ ] T032 [P] [US1] Write failing `backend/tests/unit/test_annotations.py`: hero `highlight_blue_09` → `ResolvedAnnotation(kind="highlight", player_id="blue-09")` with ≥ 1 frame id in the window; `path_amber_04` → ≥ 2 frames with amber-04 visible; `show_channel_0042` → `metric_id="metric-channel-0042"`; `show_channel_0099` (no such ok metric) → `None`; missing-tracking world `path_blue_09` limited to the gap-only window 40000–43000 → `None`; `pressure_ring_amber_06` for a player never visible in window → `None`; malformed ID → `None`
- [ ] T033 [US1] Implement `backend/src/tactistream/moments/annotation_ids.py` (`ParsedAnnotation`, `parse_annotation_id`, `annotation_id_for`, `AnnotationIdError` — exact behaviour in 005 T009) and `backend/src/tactistream/moments/annotations.py` (`ResolvedAnnotation`, `resolve_annotation`, parsing via `annotation_ids`). These are the single annotation resolver shared with 005's `moments/scene.py`. Run T032 → green
- [ ] T034 [P] [US1] Write failing `backend/tests/unit/test_checks_release.py`, one blocking test per code on top of a valid hero bundle (valid bundle → `[]`): `unapproved_claim` (plan/packet includes `clm-0045-9`), `unrequested_annotation` (`highlight_blue_08` not requested), `unresolvable_annotation` (requested but entity invisible), `unsupported_number` (body edited to "3.9 m"), `unsupported_player` ("Blue 7" injected), `unknown_evidence` (`metric-channel-0099`), `future_evidence` (`evt-0046` in `evidence_ids`), `title_mismatch` (`title.turnover`), `unknown_template` (claim template removed from catalog), `causal_overreach` (en body containing "forced"; hi body containing "के कारण"; "Because" capitalised also caught; "becausewise" not matched), `variant_inconsistent` (hi body number differs), `invalid_timing` (`show_until <= show_from`), `expired` (`now_session_ms > expires_at`), `schema_invalid` (body 401 chars); each failure carries `mode`/`language` where variant-specific; 001 `test_checks.py` still passes
- [ ] T035 [US1] Extend `backend/src/tactistream/agents/checks.py` with `check_release(bundle, plan, ctx, now_session_ms)` (calls `check_packet` per variant, then the new checks) and the new `CheckFailure` codes. Run T034 → green
- [ ] T036 [US1] Write failing `backend/tests/unit/test_workflow.py::test_happy_path` (hero world, scripted client, `run_with_clock`): `explain_moment` returns `outcome="released"`; `on_stage` calls == `["analysing","verifying","producing","checking","released"]`; scripted `calls` roles == `[analyst, verifier, producer]`; `usage.model_calls == 3`, tokens summed from script; trace steps roles == `[gate, analyst, verifier_precheck, verifier, producer, checks]`; `check_release(result.bundle, …) == []`; `result.latency_ms` == scripted delays sum + 0 deterministic time (FakeClock)
- [ ] T037 [US1] Implement `backend/src/tactistream/agents/workflow.py`: step functions wrapped as Agent Framework executors, `build_workflow()` with the conditional repair edge (repair branch stubbed to "no repair" until T046), outer deadline guard, `explain_moment`, `WorkflowResult`, `Usage`, `build_context`; record the framework class names in `specs/004-agent-workflow/research.md` R1. If the workflow API blocks > 2 h, apply research R1 fallback. Run T036 → green
- [ ] T038 [US1] Write failing `backend/tests/integration/test_narrative_flow.py` (httpx ASGI + FakeClock + scripted agents, session replaying `hero_space_creation.jsonl`): WS receives `moment` for `mom-0045`, then `narrative_status` stages in FR-017 order each with the same `trace_id`, then `insight` with 4 variants and fan/en body "Blue 9's run helped create room for the pass."; every evidence ID in the bundle resolves via `GET /api/matches/{id}/evidence/{evidence_id}` (200); a `narrative` latency sample with `outcome="released"` is recorded; with the scripted Analyst delayed 10 s, the `event` message for `evt-0046` is broadcast within 50 ms (FakeClock) of its ingest while the workflow is pending (SC-009)
- [ ] T039 [US1] Implement `backend/src/tactistream/agents/service.py` (`NarrativeService`: FR-022 gate on pattern/rank, abstention gate stub, per-match semaphore, `build_context` with `trigger_receipt_ms` from the stored trigger event, stage broadcasts via `WsHub`, latency recording, trace store/publish, `NarrativeCache` stub = dict until T065) and `make_model_client(settings, clock, arm)` in `agents/model_client.py`; wire `api/session.py` (`MatchSession.on_moment` → `narrative.submit`; reset → `cancel_all`) and `api/app.py` (construct service when `settings.agents != "off"`); author `data/fixtures/agent_scripts/demo-blue-amber-001.json` with hero replies (attempt 1 and 2) plus press_turnover and switch_escape moments. Run T038 → green
- [ ] T040 [US1] Implement `FoundryModelClient` in `backend/src/tactistream/agents/model_client.py` (Agent Framework chat client for the Foundry project endpoint + deployment, `DefaultAzureCredential`, JSON-schema response format with JSON-mode fallback, temperature 0 when supported, usage extraction, 429 → `ModelError("throttled")`), unit-tested with an injected fake chat client in `backend/tests/unit/test_model_client.py::test_foundry_*` (request carries the schema; usage mapped; transport error → `ModelError("transport")`); add `backend/tests/live/test_foundry_agents.py` (`@pytest.mark.live`): hero moment with the real deployment returns `released` or `fallback`, trace has `model_deployment`, per-step latency and non-null tokens; prints a one-line summary
- [ ] T041 [P] [US1] Write failing `frontend/tests/unit/InsightCard.labels.test.tsx`: packet with labels `["synthetic","interpretation"]` shows "Interpretation" chip; `fallback` → "Facts only"; `partial_tracking` → "Partial tracking"; `demo_fixture` → "Demo fixture"; "How was this made?" button calls `onOpenTrace(trace_id)`; hi chrome strings used when language is hi
- [ ] T042 [US1] Write failing `frontend/tests/unit/NarrativeStageIndicator.test.tsx` and `frontend/tests/unit/matchStore.narrative.test.ts` (store keeps latest stage per `moment_id` from `narrative_status`; indicator shows "Analysing…"/"Verifying…"/"Producing…"/"Checking…", hides on `released`, region has `aria-live="polite"`), then implement `frontend/src/components/NarrativeStageIndicator.tsx`, extend `frontend/src/components/InsightCard.tsx`, `frontend/src/store/matchStore.ts` (narrative slice) and `frontend/src/i18n/{en,hi}.ts`. Run T041–T042 → green

**Checkpoint**: hero card released end to end in scripted mode; live Foundry test runnable; UI shows stages and Interpretation label.

---

## Phase 4: User Story 2 — Unsupported claim blocked and repaired (P1)

**Goal**: one repair round; bad-claim fixture; blocked claim visible.

**Independent Test**: `pytest backend/tests/unit/test_workflow.py -k "revise or future or no_repair"` and `backend/tests/integration/test_fixtures_api.py`.

- [ ] T043 [P] [US2] Write failing `test_workflow.py::test_revise_once`: scripted Analyst attempt 1 returns the hero interp claim with `channel_gain.value=5.3`; pre-check → revise `value_mismatch`; Analyst attempt 2 (scripted corrected claim) → approve; outcome `released`; stages `[analysing, verifying, analysing, verifying, producing, checking, released]`; 5 model calls; ledger: `clm-0045-2` status `revised`, `superseded_by="clm-0045-3"`; `clm-0045-3` approved; bundle `claim_ids` exclude `clm-0045-2`; attempt-2 Analyst input contains `prior_claims` and `verdicts` for `clm-0045-2` and `next_claim_ids == ["clm-0045-3", "clm-0045-4"]`
- [ ] T044 [P] [US2] Write failing `test_workflow.py::test_no_repair_when_short_on_time`: scripted Analyst delay 3000 ms and Verifier delay 2300 ms (remaining 2700 < 3000) with one revise and one approved fact → no attempt-2 call; revise claim final status `rejected`; outcome `released` with `claim_status="verified_fact"`; variant with zero approved claims → `fallback`/`verifier_rejected`
- [ ] T045 [P] [US2] Write failing `test_workflow.py::test_future_evidence_rejected`: Analyst cites `evt-0046` in a `fact.shot` claim → pre-check reject `future_evidence`; claim not in Verifier model input; not resubmitted in repair (attempt-2 input lists it with decision `reject`); trace claim status `rejected`; plus `test_agent_tools.py` already proves the tool refuses `evt-0046`
- [ ] T046 [US2] Implement the repair edge in `backend/src/tactistream/agents/workflow.py` and attempt-2 input in `agents/analyst.py` (prior claims, final verdicts, continuing `next_claim_ids`; only `revise` claims re-verified; approved kept; unrepaired `revise` → `rejected`). Run T043–T045 → green
- [ ] T047 [P] [US2] Write failing `backend/tests/unit/test_fault_injection.py`: `mutate_to_bad_claim(hero_output, metrics)` is deterministic and yields `kind="fact"`, `uncertainty="low"`, `channel_gain.value == 5.3`, rationale containing "forced"; output without an interpretation gets a constructed `interp.space_opened_by_run`; `FaultInjectingModelClient` with arm `bad_claim` mutates only `(analyst, attempt 1)` and marks the response `injected_fault`; arm `model_timeout` makes every analyst call hang so `TimeoutModelClient` raises `ModelTimeout` at the budget; non-analyst roles untouched; `FixtureArm.consume` returns the kind once, then `None`
- [ ] T048 [US2] Implement `FaultInjectingModelClient`, `mutate_to_bad_claim` in `backend/src/tactistream/agents/model_client.py` and `FixtureArm` in `agents/service.py`; workflow records `fixture` and step/claim `injected_fault` in the trace. Run T047 → green
- [ ] T049 [P] [US2] Write failing `backend/tests/integration/test_fixtures_api.py`: with `demo_fixtures=false` `POST /api/matches/{id}/fixtures {"inject":"bad_claim"}` → 404 `fixtures_disabled`; enabled → 200 `{"armed":"bad_claim","applies_to":"next_moment"}`; `{"inject":"nope"}` → 422 `invalid_fixture`; `/healthz` reports `demo_fixtures`; after arming and replaying the hero, the trace has `fixture="bad_claim"`, a `revised` claim with `reason_codes ⊇ ["template_kind_mismatch","value_mismatch"]`, the bundle has label `demo_fixture` and no blocked claim ID; a second moment afterwards runs without a fixture
- [ ] T050 [US2] Implement `backend/src/tactistream/api/routes_fixtures.py`, register in `api/app.py`, add `demo_fixtures` to `/healthz`. Run T049 → green
- [ ] T051 [P] [US2] Write failing `frontend/tests/unit/FixtureControls.test.tsx` (hidden when health `demo_fixtures=false`; buttons "Inject bad claim"/"Inject model timeout" call `injectFixture`; "Demo fixture" label visible; shows "Armed: bad claim" after success), then implement `frontend/src/components/FixtureControls.tsx` and `injectFixture`, `getHealth` in `frontend/src/api/client.ts`. Run → green

**Checkpoint**: bad-claim fixture blocks and repairs in scripted mode and via API.

---

## Phase 5: User Story 3 — Fallback and abstention (P1)

**Goal**: every failure mode degrades to a labelled factual card within 8 s; missing tracking abstains with zero model calls.

**Independent Test**: `pytest backend/tests/unit/test_fallback_bundle.py backend/tests/unit/test_workflow.py -k "fallback or abstain"`.

- [ ] T052 [P] [US3] Write failing `backend/tests/unit/test_fallback_bundle.py`: `build_fallback_bundle(ctx, "timeout", release_session_ms=47000)` for the hero (shot trigger) → 4 variants, fan/en body "Blue 11 took a shot: on target.", title "Shot", `claim_status="fallback_template"`, labels `["synthetic","fallback"]`, `claim_ids=[]`, `evidence_ids=["evt-0045"]`, priority 3, `lower_third`, no annotations, passes `check_packet`; pass trigger → `fact.forward_pass` with `metric-forward_progress-NNNN` evidence; switch_escape pass → `fact.switch`; interception → `fact.turnover` ("Amber 6 won the ball from Blue."); `out_of_play` trigger → `None`; `build_abstain_bundle` for the missing-tracking hero → body "Blue 11 took a shot: on target. Insufficient tracking for this explanation.", `claim_status="insufficient_data"`, labels `["synthetic","partial_tracking"]`, evidence includes the unavailable channel metric ID; hi variants contain the same numbers
- [ ] T053 [US3] Implement `build_fallback_bundle` and `build_abstain_bundle` in `backend/src/tactistream/narrative/factual.py` (table in data-model.md "Fallback templates"; reuse 001 `build_fact_bundle` internals). Run T052 → green
- [ ] T054 [P] [US3] Write failing parametrized `test_workflow.py::test_fallbacks` (FakeClock, hero; ≥ 20 cases for SC-003) — each asserts outcome, `fallback_reason`, last stage, a released fallback bundle, `released_at ≤ trigger_receipt_ms + 8000`, a trace step with the failing status, and a latency sample `outcome="fallback"`: Analyst hang attempt 1 (`timeout`); Analyst hang via `model_timeout` fixture; Verifier hang attempt 1 and attempt 2; Producer hang; Analyst delay 3400 + Verifier delay 2400 + Producer hang (deadline edge); hangs at offsets 0/1000/2000/3000/4000/5000/6000/7000 ms via a slow pre-step; Analyst `invalid_json` (`model_error`); Verifier `script_missing` (`model_error`); all claims rejected (`verifier_rejected`); Analyst `abstained` with `no_supported_interpretation` (`no_supported_claim`); Producer plan with `clm-0045-9` (`output_check_failed`, trace `check_failures` contains `unapproved_claim`); Producer annotation not requested (`output_check_failed`); session clock beyond expiry at release (`expired`, bundle still broadcast)
- [ ] T055 [P] [US3] Write failing `test_workflow.py::test_abstain_missing_tracking` (missing-tracking world: zero scripted calls; stages `["abstained"]`; outcome `abstained`; trace steps `[gate]`; abstain bundle) and `test_abstain_by_analyst` (coverage ok but Analyst returns `abstained/insufficient_tracking` → outcome `abstained`, 1 model call) and `test_shot_not_gated` (low coverage shot moment still calls the Analyst)
- [ ] T056 [US3] Implement fallback, abstention gate, deadline guard and expiry handling in `backend/src/tactistream/agents/workflow.py` and `agents/service.py` (gate per FR-015; budget skip → `timeout`; outer guard; fallback bundle broadcast + `narrative_status`; latency samples for every outcome). Run T054–T055 → green
- [ ] T057 [US3] Extend `backend/tests/integration/test_narrative_flow.py` with `test_model_timeout_fixture_over_ws` (arm `model_timeout`, replay hero: WS `narrative_status{stage:"fallback", fallback_reason:"timeout"}` then fallback `insight` within 8000 ms FakeClock of trigger receipt) and `test_missing_tracking_over_ws` (abstained status + bundle; `event` messages for the same events present); fix wiring until green
- [ ] T058 [P] [US3] Extend `frontend/tests/unit/NarrativeStageIndicator.test.tsx` (fallback shows "Facts only — model timed out" / reason labels for all 6 reasons; abstained shows "Insufficient tracking for this explanation"; hi strings) and implement in `NarrativeStageIndicator.tsx` and `frontend/src/i18n/{en,hi}.ts`. Run → green

**Checkpoint**: every failure mode degrades within the deadline. SC-007 coverage table:

| Code / reason | Test |
|---|---|
| 14 `CheckFailure` codes | `test_checks_release.py` (one test each) |
| `timeout`, `model_error`, `verifier_rejected`, `no_supported_claim`, `output_check_failed`, `expired` | `test_workflow.py::test_fallbacks` |
| abstention (`insufficient_tracking`) | `test_workflow.py::test_abstain_*` |

---

## Phase 6: User Story 4 — Inspect the trace (P2)

**Goal**: trace API, bus envelope and the Agent trace panel.

**Independent Test**: `pytest backend/tests/integration/test_traces_api.py` and `npx vitest AgentTrace`.

- [ ] T059 [P] [US4] Write failing `backend/tests/integration/test_traces_api.py`: after hero release `GET /api/matches/{id}/traces/{trace_id}` → 200, validates against `agent_trace.schema.json`, `insight_id/moment_id/state_version/outcome` match the bundle; same for a fallback run and an abstained run; unknown trace → 404 `trace_not_found`; unknown match → 404 `match_not_found`; the InMemoryBus `fabric` consumer group receives exactly one `agent_trace` envelope per finished run with `record_id == trace_id`; with `TACTISTREAM_TRACE_DIR=tmp_path` the file exists
- [ ] T060 [US4] Implement `backend/src/tactistream/api/routes_traces.py` and register in `api/app.py`; ensure `NarrativeService` publishes `trace_envelope` on finalize. Run T059 → green
- [ ] T061 [P] [US4] Write failing `frontend/tests/unit/AgentTrace.test.tsx` using `contracts/examples/agent_trace.json`: renders 9 steps in order with role labels and latency; tool call row shows `get_metric` and result chip `metric-channel-0042`; "Blocked claim" section lists `clm-0045-2` with labels "Wrong claim type", "Value differs from measurement", "Claims more than the data shows" and link "Revise → clm-0045-3"; approved claims show "Approved"; Producer plans for Fan and Analyst listed; "Demo fixture" chip; footer note text; a fallback trace shows banner "Facts only — model timed out"; activating an evidence chip calls `onOpenEvidence(id)`; loading and 404 ("Trace unavailable") states
- [ ] T062 [US4] Implement `frontend/src/components/AgentTrace.tsx`, `frontend/src/components/AnalystDrawer.tsx` (tabs "Evidence" — hosts the 001 `EvidenceDrawer` content — and "Agent trace"; labelled dialog, focus returns on close), `getTrace` in `frontend/src/api/client.ts`, trace cache in `matchStore.ts`, reason/role labels in `i18n/{en,hi}.ts`; wire `InsightCard` "How was this made?" to open the drawer on the trace tab. Run T061 → green
- [ ] T063 [US4] Write `frontend/tests/e2e/agents.spec.ts` (webServer env `TACTISTREAM_AGENTS=scripted`, `TACTISTREAM_DEMO_FIXTURES=true`): "hero card" — Start → stage indicator text appears → card "Blue 9's run helped create room for the pass." with "Interpretation" chip; switch to Analyst → text contains "3.4 m"; switch to Hindi → contains "3.4"; open trace → steps Analyst, Verifier, Producer visible. "blocked claim" — Reset, Inject bad claim, Play → trace shows "Blocked claim" and "Value differs from measurement"; card text has no "5.3". "timeout fallback" — Reset, Inject model timeout, Play → card "Blue 11 took a shot: on target." with "Facts only" within 10 s of the shot. Run `--repeat-each=10` for SC-001/SC-002

**Checkpoint**: roadmap exit condition met (supported card, blocked claim visible, timeout fallback, trace view).

---

## Phase 7: User Story 5 — Shared cached narratives (P2)

**Goal**: one run per `(moment_id, state_version)`; viewers never trigger model calls; superseded versions revoked.

**Independent Test**: `pytest backend/tests/unit/test_cache.py backend/tests/integration/test_viewer_cache.py`.

- [ ] T064 [P] [US5] Write failing `backend/tests/unit/test_cache.py`: two concurrent `run_once(("mom-0045",512), run)` calls execute `run` once and return the same object; a failing run propagates to both and a later call re-runs; `("mom-0045",513)` runs again; `put_bundle`/`get_bundle` by `(match_id, insight_id, version)`; `next_insight_version` returns 1, then 2 after `put_bundle(v1)`, and accounts for a 001 fact card already stored as `ins-0042` v1; `latest_bundles` returns only the highest version per insight
- [ ] T065 [US5] Implement `backend/src/tactistream/agents/cache.py` (`NarrativeCache`) and replace the T039 stub in `agents/service.py`; WS snapshot `insights` come from `cache.latest_bundles(match_id)` merged with 001 fact cards. Run T064 → green
- [ ] T066 [P] [US5] Write failing `backend/tests/integration/test_viewer_cache.py`: after hero release a second WS client connects → snapshot contains `ins-0045` v1; it sends `prefs` (analyst/hi, pinned blue-09) → scripted `calls` length unchanged (SC-006); duplicate trigger envelope → no new run; re-detection of `mom-0045` with a higher state version → new run, `insight` v2, then `insight_revoked{insight_id:"ins-0045", insight_version:1, reason:"superseded"}`; a run whose moment state version advanced before completion is not broadcast (trace outcome `superseded`); session reset during a run → nothing broadcast, trace outcome `cancelled`
- [ ] T067 [US5] Implement superseded/stale/cancel handling in `backend/src/tactistream/agents/service.py` (current state version per moment, revocation broadcast after the new version, task cancellation on reset). Run T066 → green

**Checkpoint**: 10-viewer scenario costs one run per moment.

---

## Phase 8: User Story 6 — Baselines for evaluation (P3)

**Goal**: deterministic and single-agent runners behind `make_runner` for 008.

**Independent Test**: `pytest backend/tests/unit/test_baselines.py`.

- [ ] T068 [P] [US6] Write failing `backend/tests/unit/test_baselines.py`: `make_runner("deterministic")` on the hero → 0 model calls, outcome `released`, claims `fact.shot`/`fact.forward_pass` + `interp.space_opened_by_run` chosen by `INTERPRETATION_RULES` (channel ≥ 1.0 m and defender_follow ≥ 0.5), bundle passes `check_release`, trace `runner="deterministic"`; on `run_no_channel` → only fact claim, `claim_status="verified_fact"`; on the missing-tracking world → `abstained`; `make_runner("single_agent")` with a scripted `single_agent` reply → exactly 1 model call, no `verifier` steps, same `assemble_bundle` + `check_release`; a single-agent reply citing `evt-0046` is caught by `check_release` (`future_evidence`) and yields fallback `output_check_failed` (there is no Verifier to reject it earlier); a single-agent reply with `channel_gain.value=5.3` is released with the engine value 3.4 in text and the mismatch recorded in `WorkflowResult.claims` for 008 scoring; `make_runner("three_agent")` equals `explain_moment`; all three return `WorkflowResult` with `usage` and `latency_ms`; token budget: with `AgentBudgets.token_budget=1200` and scripted usage of 700 tokens per call, the three-agent runner falls back with `fallback_reason="timeout"` before the call that would exceed the budget (recorded in the trace as `budget_exhausted`), and `token_budget=None` imposes no limit (008 fixed-token comparison)
- [ ] T069 [US6] Implement `backend/src/tactistream/agents/baselines.py` (`DeterministicRunner`, `SingleAgentRunner`, `INTERPRETATION_RULES` per pattern), `make_runner` in `agents/workflow.py`, and `agents/prompts/single_agent.md` (single_agent.v1). Run T068 → green Enforce `AgentBudgets.token_budget` in `agents/context.py` (`tokens_remaining()`), checked before every model call by all runners.

**Checkpoint**: 008 can run all three configurations on frozen moments via `build_context` + `make_runner`.

---

## Phase 9: Polish & Cross-Cutting

- [ ] T070 Write `backend/tests/integration/test_release_audit.py` (scripted, FakeClock): replay the hero, press_turnover, switch_escape, run_no_channel and missing-tracking fixtures, plus the hero with each fixture armed; collect every broadcast bundle and assert: `check_release` re-run independently returns `[]` for every released variant and the count checked is > 0 (SC-004); `GET /traces/{id}` 200 and schema-valid for every bundle (SC-005); `count("narrative") == number of explained moments`, split by outcome (SC-010); all recorded `ToolCallRecord` responses pass the leakage audit (SC-011); print a summary table
- [ ] T071 [P] Write `docs/agents.md`: three agent roles and authority, evidence-pack recipes, prompt versions, reason-code table, release checks, causal lexicon, budgets and fallback table, abstention threshold (0.8, tunable prototype), scripted vs Foundry modes (scripted = recorded decisions, not a live model), demo fixtures and their labels, trace fields and the "no private reasoning" rule, measured results placeholder linked to research.md R7
- [ ] T072 [P] Run `specs/004-agent-workflow/quickstart.md` offline section on a fresh clone and fix gaps
- [ ] T073 Run `uv run pytest -m live backend/tests/live/test_foundry_agents.py` 5 times against the real deployment; record outcome, per-role latency p50/p95, tokens in/out per role and deployment/region in `specs/004-agent-workflow/research.md` R7 and the SC-001 live line (report whatever the result is)
- [ ] T074 Update `specs/README.md` feature table: mark 004 exit condition met with date, and add the registry entries from plan.md change C6

---

## Dependencies & Execution Order

- Setup (T001–T004) → Foundational (T005–T023) → US1 (T024–T042) → US2 (T043–T051) and US3 (T052–T058) can proceed in parallel after T037/T039 → US4 (T059–T063; T063 needs US2/US3 UI pieces) → US5 (T064–T067) → US6 (T068–T069, needs only US1) → Polish (T070–T074).
- Within Foundational: T005 → T006 → T007; T008 → T009; T010 → T011 → T012 → T013; T014 → T015; T016 → T017 (needs T009); T018 → T019; T020 → T021; T022 → T023. Groups run in parallel.
- Within US1: T024/T026/T028/T030/T032/T034 tests can be written in parallel; implementations T025 → T027 → T029 → T031 → T033 → T035 → T036/T037 → T038/T039; T040 any time after T015; frontend T041–T042 after T006 (generated types).
- T046 depends on T037; T048 on T015; T050 on T039; T056 on T053; T062 on T006; T065 replaces the T039 stub.
- External: 003 interfaces before T008; 002 scenarios before T008. If 003 slips, T010–T015 and T018–T023 can still proceed.

## Parallel Example

```text
Day 16, morning:   T005–T007 (contracts)  ||  T010–T013 (catalog/render)  ||  T014–T015 (model client)  ||  T040 Foundry client
Day 16, afternoon: T016–T023 (tools, context, trace, latency)  ||  T024/T026/T028/T030/T032/T034 (US1 tests)
Day 17, morning:   T025–T039 (US1 implementation)  ||  T041–T042 (frontend)
Day 17, afternoon: T043–T058 (repair, fixtures, fallback)  →  T059–T063 (trace + e2e)  →  T064–T069 if time; else move US5/US6 to day 18 morning
```

## Implementation Strategy

MVP = Phase 1–3 (supported hero card). Then US2 and US3 together (the exit condition requires both), then US4 (trace
view, also required by the exit condition). US5 and US6 may slip to the morning of 18 Oct without blocking 005, but must
land before 006 (caching) and 008 (baselines). Stop and validate at each checkpoint.
