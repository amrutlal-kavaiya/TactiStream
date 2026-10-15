# Research & Decisions: 004 Agent Workflow

Each decision lists what was chosen, why, and what was rejected. Items marked **Record** are filled by tasks with
observed values — they are measurements, not open design questions.

## R1. Orchestration runtime

- **Decision**: Build `explain_moment` as a Microsoft Agent Framework workflow: four executors (Analyst, Verifier,
  Producer, Checks) wired with the framework's workflow builder, a conditional edge Verifier → Analyst for the single
  repair round and Verifier → Producer otherwise. Executors are thin wrappers over pure step functions
  (`run_analyst`, `run_verifier`, `run_producer`, `check_release`) so tests exercise the steps directly and through the graph.
  Class names follow the version pinned in 001 R5; T037 records them below.
- **Rationale**: The build plan names Agent Framework for typed handoffs and bounded retries, and its workflow
  observability emits spans we can enrich. Keeping logic in plain functions limits framework coupling.
- **Fallback (stop rule)**: if the workflow API blocks progress for > 2 h, implement the same graph as a plain
  `asyncio` state machine in `workflow.py` behind the same `explain_moment` signature, keep `FoundryModelClient` on the
  Agent Framework chat client (or the 001 R5 OpenAI-SDK fallback), and remove "Agent Framework workflows" from docs (constitution VI).
- **Alternatives rejected**: Foundry managed agents (server-side threads add latency and hide tool timing from our
  trace); Agent Framework checkpoints (runs finish in < 8 s; nothing to resume); a group-chat/magentic pattern
  (unbounded turns violate the one-repair rule).
- **Record** (T037): workflow builder class `____`; executor base class `____`; `agent-framework` version `____`.

## R2. How agents use tools

- **Decision**: Executor-built **evidence packs**. Each executor calls `AgentTools` according to a pattern recipe
  (data-model.md) and sends the compact results to the model in one structured request. The model chooses which
  evidence to cite and which claims to make; it does not call tools itself. Every tool call is a `ToolCallRecord` in the trace.
- **Rationale**: Three sequential calls already consume most of 8 s; a model-driven function-calling loop adds one or
  more round trips per agent and makes timing unpredictable. Packs are deterministic, so scripted tests are exact and
  the as-of guarantee is enforced in one place. Packs stay small (≤ 8 KB for the hero moment, asserted in tests).
- **Alternatives rejected**: model-driven function calling through Agent Framework tools (latency, nondeterminism;
  may be revisited post-MVP using the same `AgentTools` methods); exposing tools via MCP (build plan: protocol decoration
  alone is not a product advantage — deferred).

## R3. Structured output and schema references

- **Decision**: `schema_ref` is one of `AnalystOutput`, `VerifierOutput`, `ProducerOutput` (resolved from
  `claim.schema.json#/$defs/...` with `$ref`s inlined by 001 `schema_registry`) or `SingleAgentOutput` (internal,
  `{"analyst": AnalystOutput, "producer": ProducerOutput}`). `FoundryModelClient` requests JSON-schema structured output;
  if the deployment rejects it, JSON mode plus post-validation. Every response is validated again on receipt; invalid
  output raises `ModelError("schema_invalid")`. Temperature 0 when the deployment supports it.
- **Rationale**: Same contract for model, scripted client and tests; one failure semantics.
- **Alternatives rejected**: parsing free text (fragile); retrying on invalid JSON (consumes the deadline; the single
  repair round is reserved for evidence problems).

## R4. User-facing text comes only from templates

- **Decision**: Claims reference catalog `template_id`s with typed slots; the Producer outputs `ModePlan`s (title key,
  claim order, annotations, priority, panel). `assemble_bundle` renders all four variants with `render_claim` /
  `render_title`. The model never writes visible text.
- **Rationale**: Guarantees identical numbers and identities across Fan/Analyst and en/hi (build plan essential), makes
  output checks exact, and removes translation risk (roadmap stop rule for Hindi).
- **Alternatives rejected**: Producer-written prose checked afterwards (cannot guarantee number preservation in Hindi;
  check false negatives); model translation (unreviewed terminology).

## R5. Verifier composition

- **Decision**: Deterministic pre-checks first (existence, as-of, value, unit, template kind, slot players in evidence,
  tracking); claims rejected by pre-checks are not sent to the model. The model judges only `unsupported_causality`
  and `counterevidence` with a pattern-specific counterevidence pack. Final decision = stricter of the two. If the
  Verifier model fails or times out, the run falls back (pre-checks alone never approve an interpretation).
- **Rationale**: Build plan: "Treating plausible prose or model confidence as proof" is prohibited; code can check
  references exactly, the model adds judgement where code cannot.
- **Alternatives rejected**: model-only verification (could approve changed values); code-only verification
  (cannot weigh counterevidence; would make the Verifier agent nominal).

## R6. Reason codes → decisions (pre-checks)

- **Decision**: `future_evidence`, `insufficient_tracking`, and `missing_evidence_id` for an ID absent from the
  snapshot → `reject`. `value_mismatch`, `unit_mismatch`, `template_kind_mismatch`, and `missing_evidence_id` for an
  existing-but-uncited required ID or a slot player not in cited evidence → `revise`. The model may return any decision
  with codes `ok`, `unsupported_causality`, `counterevidence`.
- **Rationale**: Invented or future evidence is not fixable by rewording; misreported values and wrong template kinds
  are correctable within one repair round.

## R7. Deadline budgeting

- **Decision**: Per-step budget `min(cap, remaining − reserve − Σ downstream minimums)`, caps 3500/2500/1500 ms,
  minimums 800/600/600 ms, reserve 400 ms, repair only with ≥ 3000 ms remaining; outer guard at `deadline − reserve`.
- **Rationale**: Guarantees the fallback is broadcast inside 8 s even if every call hangs; reserves time downstream so a
  slow Analyst cannot starve the Producer silently.
- **Risk**: if measured Foundry latency p50 > 1.2 s, the repair round will rarely fit. Mitigation (measure first):
  use a smaller/faster deployment for Verifier and Producer via `FOUNDRY_MODEL_DEPLOYMENT_FAST` (optional, same client).
- **Record** (T073): per-role latency p50/p95 over 5 live hero runs: Analyst `____`, Verifier `____`, Producer `____`; tokens in/out per role `____`.

## R8. Agent-asserted slot values (requires contract change C2)

- **Decision**: Add optional `value` and `unit` to `SlotValue`. The Analyst copies them from tool output; the Verifier
  compares them to `MetricEngine.compute(...)` rounded to the template slot precision. Renderers ignore them and always
  use the engine value.
- **Rationale**: Gives the Verifier a concrete "changed values" check (build plan) and makes the bad-claim fixture
  realistic; still impossible for an agent value to reach the screen.
- **Alternatives rejected**: checking numbers in `rationale` (not user-facing, unstructured); no value assertion
  (verifier could never detect misreading).

## R9. Causal-overreach lexicon

- **Decision**: Fixed en + hi lexicon (spec FR-012) matched case-insensitively at word boundaries on every variant
  title/body by `check_release`, plus a catalog lint test. Lexicon terms in `rationale` are not blocked (rationale is
  not user-facing) but the Verifier prompt instructs flagging them as `unsupported_causality`.
- **Rationale**: Templates are reviewed, so the runtime check is a guard against future catalog edits and derived slots.
- **Alternatives rejected**: model-based tone classification (nondeterministic, slow).

## R10. Trace content and storage

- **Decision**: `AgentTrace` stores inputs as IDs (not full packs), tool calls with arguments and result IDs, validated
  outputs, verdicts, usage, latency, prompt versions, errors and fallback reason. No `reasoning`/`thought` fields exist;
  `rationale` and verdict `note` are length-limited public notes. In-memory `TraceStore` per session, optional JSON file
  per trace, `agent_trace` bus envelope for Fabric (007), OTel spans with GenAI semantic-convention attributes
  (`gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`) plus `tactistream.role`,
  `tactistream.attempt`, `tactistream.moment_id`.
- **Rationale**: Build plan: "Log decisions and tool results, not private model reasoning".
- **Alternatives rejected**: storing full prompts (size, and they contain no extra decision information beyond IDs + prompt version).

## R11. Caching and versioning

- **Decision**: `NarrativeCache.run_once((moment_id, state_version))` shares one `asyncio.Future`; bundles keyed by
  `(match_id, insight_id, insight_version)`; `next_insight_version` considers every version already released for the ID
  (including 001 fact cards). Stale runs (moment's current state version moved on) are not broadcast.
- **Rationale**: Build plan economics (cache by match, insight version, audience, language — all four variants are in one bundle).

## R12. Fault injection

- **Decision**: `FaultInjectingModelClient` wraps the real or scripted client. `bad_claim` applies
  `mutate_to_bad_claim` to the Analyst attempt-1 response (deterministic: first interpretation claim → kind `fact`,
  metric slot value replaced by the metric's largest component, uncertainty `low`, causal rationale); attempt 2 is never
  mutated. `model_timeout` sleeps forever on the injected clock for every Analyst call. Armed per match via
  `FixtureArm`, consumed by exactly one moment; marked in trace and packet labels.
- **Rationale**: Same fixture works with Foundry and scripted mode; the real Verifier and real repair are exercised.
- **Alternatives rejected**: special prompts asking the model to misbehave (unreliable, and it would blur what the model did).

## R13. Abstention gate thresholds

- **Decision**: Gate before any model call when pattern ∈ {space_creation, press_turnover, switch_escape} and
  `tracking_coverage < 0.8` or any moment metric `unavailable/insufficient_tracking`. Shot moments are never gated
  (facts need no tracking).
- **Rationale**: Saves model cost, deterministic, and matches constitution I ("Insufficient tracking for this explanation").
  0.8 is a tunable prototype parameter, documented in `docs/agents.md`.

## R14. Baselines

- **Decision**: Deterministic runner: fact template for the trigger + interpretation from `INTERPRETATION_RULES`
  (per pattern, fixed thresholds on metric values, e.g. space_creation: `channel ≥ 1.0 m` and `defender_follow ≥ 0.5`);
  single-agent runner: one model call (`prompts/single_agent.md`, `SingleAgentOutput`), no Verifier, straight into
  `assemble_bundle` and `check_release`; `precheck_claims` runs in audit-only mode (verdicts stored in `ClaimRecord.precheck`
  for 008 scoring, never used for gating). Both return `WorkflowResult` with usage so 008 can compare support,
  coverage, latency, tokens and recovery on frozen inputs.
- **Rationale**: Build plan requires comparing three configurations on the same inputs; sharing tools/templates/checks
  isolates the effect of agent structure.

## R15. Scenario-label leakage

- **Decision**: Tool payloads omit `match_id` (simulator IDs `sim-{scenario}-{seed}` encode the scenario), display
  names, generation manifest and provenance seeds; moment `pattern` is allowed (it is a deterministic detector output,
  not ground truth). Audit test SC-011 scans all tool responses.
- **Rationale**: Constitution II: scenario labels and intended explanations never reach agents.

## R16. Scripted mode for an offline demo

- **Decision**: `TACTISTREAM_AGENTS=scripted` loads `data/fixtures/agent_scripts/demo-blue-amber-001.json` with replies
  (and simulated delays/usage) for the demo moments, including attempt-2 replies used by the `bad_claim` repair.
  Missing keys fall back honestly. Docs state that scripted mode replays recorded decisions and is not a live model.
- **Rationale**: Judges and CI can run the full experience without Azure; Playwright tests are deterministic.
