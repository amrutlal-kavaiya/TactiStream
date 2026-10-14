# Agent Trace, Narrative Status & Fixtures Contract (v1)

## AgentTrace (proposed `contracts/schemas/agent_trace.schema.json`, change C1)

A public decision record of one run. It contains IDs, validated agent outputs, verdicts, tool calls, usage and
timing — **never** private model reasoning (no `reasoning`, `thought` or raw prompt fields exist).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://tactistream.dev/contracts/agent_trace.schema.json",
  "title": "AgentTrace",
  "type": "object",
  "required": ["schema_version", "trace_id", "match_id", "moment_id", "insight_id", "insight_version", "state_version",
               "as_of_session_ms", "runner", "outcome", "trigger_receipt_ms", "deadline_ms", "started_ms", "finished_ms",
               "steps", "claims", "usage"],
  "additionalProperties": false,
  "properties": {
    "schema_version": { "$ref": "common.schema.json#/$defs/SchemaVersion" },
    "trace_id": { "$ref": "common.schema.json#/$defs/TraceId" },
    "match_id": { "$ref": "common.schema.json#/$defs/MatchId" },
    "moment_id": { "$ref": "common.schema.json#/$defs/MomentId" },
    "insight_id": { "$ref": "common.schema.json#/$defs/InsightId" },
    "insight_version": { "type": "integer", "minimum": 1 },
    "state_version": { "type": "integer", "minimum": 0 },
    "as_of_session_ms": { "$ref": "common.schema.json#/$defs/Milliseconds" },
    "runner": { "enum": ["three_agent", "single_agent", "deterministic"] },
    "outcome": { "enum": ["released", "fallback", "abstained", "superseded", "cancelled"] },
    "fallback_reason": { "enum": ["timeout", "verifier_rejected", "output_check_failed", "model_error", "expired",
                                  "insufficient_tracking", "no_supported_claim"] },
    "fixture": { "enum": ["bad_claim", "model_timeout"] },
    "model_deployment": { "type": "string" },
    "trigger_receipt_ms": { "type": "integer", "minimum": 0 },
    "deadline_ms": { "type": "integer", "minimum": 0 },
    "started_ms": { "type": "integer", "minimum": 0 },
    "finished_ms": { "type": "integer", "minimum": 0 },
    "narrative_latency_ms": { "type": "integer", "minimum": 0, "description": "release broadcast − trigger receipt; absent if nothing was broadcast" },
    "steps": { "type": "array", "items": { "$ref": "#/$defs/TraceStep" } },
    "claims": { "type": "array", "items": { "$ref": "#/$defs/ClaimTraceEntry" } },
    "producer_output": { "$ref": "claim.schema.json#/$defs/ProducerOutput" },
    "check_failures": { "type": "array", "items": { "$ref": "#/$defs/CheckFailure" } },
    "released_claim_ids": { "type": "array", "items": { "$ref": "common.schema.json#/$defs/ClaimId" } },
    "usage": { "$ref": "#/$defs/Usage" }
  },
  "$defs": {
    "TraceStep": {
      "type": "object",
      "required": ["index", "role", "attempt", "started_ms", "latency_ms", "status", "input_ids", "tool_calls"],
      "additionalProperties": false,
      "properties": {
        "index": { "type": "integer", "minimum": 0 },
        "role": { "enum": ["gate", "analyst", "verifier_precheck", "verifier", "producer", "checks", "fallback", "single_agent", "deterministic"] },
        "attempt": { "type": "integer", "minimum": 1, "maximum": 2 },
        "prompt_version": { "type": "string", "pattern": "^[a-z_]+\\.v[0-9]+$" },
        "started_ms": { "type": "integer", "minimum": 0 },
        "latency_ms": { "type": "integer", "minimum": 0 },
        "budget_ms": { "type": "integer", "minimum": 0 },
        "status": { "enum": ["ok", "timeout", "model_error", "skipped", "failed"] },
        "error": { "type": "string", "maxLength": 200 },
        "injected_fault": { "enum": ["bad_claim", "model_timeout"] },
        "input_ids": { "type": "array", "items": { "type": "string" }, "description": "Moment, claim, evidence IDs given to the step" },
        "tool_calls": { "type": "array", "items": { "$ref": "#/$defs/ToolCallRecord" } },
        "analyst_output": { "$ref": "claim.schema.json#/$defs/AnalystOutput" },
        "verdicts": { "type": "array", "items": { "$ref": "claim.schema.json#/$defs/Verdict" } },
        "producer_output": { "$ref": "claim.schema.json#/$defs/ProducerOutput" },
        "check_failures": { "type": "array", "items": { "$ref": "#/$defs/CheckFailure" } },
        "usage": { "$ref": "#/$defs/Usage" }
      }
    },
    "ToolCallRecord": {
      "type": "object",
      "required": ["tool", "args", "status", "result_ids", "latency_ms"],
      "additionalProperties": false,
      "properties": {
        "tool": { "enum": ["get_match_snapshot", "get_event_window", "get_metric", "inspect_geometry", "build_recap_candidates"] },
        "args": { "type": "object" },
        "status": { "enum": ["ok", "error"] },
        "error_code": { "enum": ["future_evidence", "unknown_metric", "unknown_event", "invalid_window", "invalid_params", "insufficient_tracking"] },
        "result_ids": { "type": "array", "items": { "type": "string" } },
        "latency_ms": { "type": "integer", "minimum": 0 }
      }
    },
    "ClaimTraceEntry": {
      "type": "object",
      "required": ["claim", "attempt", "status"],
      "additionalProperties": false,
      "properties": {
        "claim": { "$ref": "claim.schema.json#/$defs/Claim" },
        "attempt": { "type": "integer", "minimum": 1, "maximum": 2 },
        "precheck": { "$ref": "claim.schema.json#/$defs/Verdict" },
        "model_verdict": { "$ref": "claim.schema.json#/$defs/Verdict" },
        "final": { "$ref": "claim.schema.json#/$defs/Verdict" },
        "status": { "enum": ["proposed", "approved", "rejected", "revised", "superseded", "unused"] },
        "superseded_by": { "$ref": "common.schema.json#/$defs/ClaimId" },
        "injected_fault": { "enum": ["bad_claim"] }
      }
    },
    "CheckFailure": {
      "type": "object",
      "required": ["code", "detail"],
      "additionalProperties": false,
      "properties": {
        "code": { "enum": ["unsupported_number", "unsupported_player", "unknown_evidence", "invalid_timing", "expired",
                           "unapproved_claim", "unrequested_annotation", "unresolvable_annotation", "future_evidence",
                           "title_mismatch", "unknown_template", "causal_overreach", "variant_inconsistent", "schema_invalid"] },
        "detail": { "type": "string", "maxLength": 200 },
        "mode": { "$ref": "common.schema.json#/$defs/ViewerMode" },
        "language": { "$ref": "common.schema.json#/$defs/Language" }
      }
    },
    "Usage": {
      "type": "object",
      "required": ["model_calls"],
      "additionalProperties": false,
      "properties": {
        "model_calls": { "type": "integer", "minimum": 0 },
        "tokens_in": { "type": ["integer", "null"], "minimum": 0 },
        "tokens_out": { "type": ["integer", "null"], "minimum": 0 }
      }
    }
  }
}
```

Invariants (model validators): `finished_ms ≥ started_ms`; `outcome = fallback` ⇒ `fallback_reason` present and not
`insufficient_tracking`; `outcome = released` ⇒ `fallback_reason` absent or `expired`; `outcome = abstained` ⇒
`fallback_reason = insufficient_tracking`; every claim in
`released_claim_ids` has `status = approved`; step indices contiguous from 0.

## REST

| Method & path | Request | 200 response | Errors |
|---|---|---|---|
| `GET /api/matches/{match_id}/traces/{trace_id}` | — | `AgentTrace` | 404 `match_not_found`, 404 `trace_not_found` (also while the run is still in progress) |
| `POST /api/matches/{match_id}/fixtures` | `{"inject": "bad_claim" \| "model_timeout"}` | `{"armed": "bad_claim", "applies_to": "next_moment"}` | 404 `fixtures_disabled` (when `TACTISTREAM_DEMO_FIXTURES=false`), 404 `match_not_found`, 422 `invalid_fixture` |
| `GET /healthz` (001, extended) | — | adds `"demo_fixtures": true \| false` | — |

Arming replaces any fixture already armed; the fixture is consumed by the next moment that passes the gate.

## WebSocket (`ws_message.schema.json`, existing types)

Per explained moment, in order (same `moment_id` and `trace_id` on every message):

```text
narrative_status{stage:"analysing"}  → narrative_status{stage:"verifying"}
[→ narrative_status{stage:"analysing"} → narrative_status{stage:"verifying"}]     (repair round)
→ narrative_status{stage:"producing"} → narrative_status{stage:"checking"}
→ narrative_status{stage:"released"}  → insight{InsightBundle}
   or, at any point: narrative_status{stage:"fallback", fallback_reason} → insight{fallback InsightBundle} (if a template exists)
   or, at the gate or after the Analyst: narrative_status{stage:"abstained", fallback_reason:"insufficient_tracking"} → insight{abstain InsightBundle}
then, if a previous version exists: insight_revoked{insight_id, insight_version: previous, reason:"superseded"}
```

`expired`: the bundle is broadcast and `narrative_status.stage` is `released` or `fallback` with
`fallback_reason: "expired"`; clients keep it off the live card per 001 display rules.

## Bus

On finalize, `FeedEnvelope{schema_version:"1.0", kind:"agent_trace", match_id, record_id: trace_id, published_ms, payload: AgentTrace}`
is published on the session `FeedBus` (Fabric consumer group routes it to an `agent_traces` table in 007).

## Example: bad-claim fixture (abridged)

```json
{
  "schema_version": "1.0", "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "match_id": "demo-blue-amber-001",
  "moment_id": "mom-0045", "insight_id": "ins-0045", "insight_version": 1, "state_version": 512, "as_of_session_ms": 46500,
  "runner": "three_agent", "outcome": "released", "fixture": "bad_claim", "model_deployment": "scripted",
  "trigger_receipt_ms": 1760422600000, "deadline_ms": 1760422608000, "started_ms": 1760422600020, "finished_ms": 1760422605910,
  "narrative_latency_ms": 5930,
  "steps": [
    { "index": 0, "role": "gate", "attempt": 1, "started_ms": 1760422600020, "latency_ms": 2, "status": "ok", "input_ids": ["mom-0045"], "tool_calls": [] },
    { "index": 1, "role": "analyst", "attempt": 1, "prompt_version": "analyst.v1", "started_ms": 1760422600030, "latency_ms": 1420,
      "budget_ms": 3500, "status": "ok", "injected_fault": "bad_claim",
      "input_ids": ["mom-0045", "evt-0042", "evt-0045", "metric-channel-0042", "metric-defender_follow-0042", "metric-off_ball_run-0042"],
      "tool_calls": [ { "tool": "get_metric", "args": { "metric_id": "metric-channel-0042" }, "status": "ok", "result_ids": ["metric-channel-0042"], "latency_ms": 3 } ],
      "usage": { "model_calls": 1, "tokens_in": 1900, "tokens_out": 260 } },
    { "index": 2, "role": "verifier_precheck", "attempt": 1, "started_ms": 1760422601455, "latency_ms": 4, "status": "ok",
      "input_ids": ["clm-0045-1", "clm-0045-2"], "tool_calls": [],
      "verdicts": [ { "claim_id": "clm-0045-1", "decision": "approve", "reason_codes": ["ok"] },
                    { "claim_id": "clm-0045-2", "decision": "revise", "reason_codes": ["template_kind_mismatch", "value_mismatch"],
                      "note": "interp template marked fact; channel_gain 5.3 ≠ engine 3.4" } ] },
    { "index": 3, "role": "verifier", "attempt": 1, "prompt_version": "verifier.v1", "latency_ms": 910, "status": "ok", "started_ms": 1760422601460,
      "input_ids": ["clm-0045-1", "clm-0045-2", "metric-pressure-0042", "metric-receiver_separation-0042"], "tool_calls": [],
      "verdicts": [ { "claim_id": "clm-0045-1", "decision": "approve", "reason_codes": ["ok"] },
                    { "claim_id": "clm-0045-2", "decision": "revise", "reason_codes": ["unsupported_causality"], "note": "rationale asserts the run forced the defender" } ] },
    { "index": 4, "role": "analyst", "attempt": 2, "prompt_version": "analyst.v1", "latency_ms": 1100, "status": "ok", "started_ms": 1760422602380, "input_ids": ["clm-0045-2"], "tool_calls": [] },
    { "index": 5, "role": "verifier_precheck", "attempt": 2, "latency_ms": 3, "status": "ok", "started_ms": 1760422603490, "input_ids": ["clm-0045-3"], "tool_calls": [] },
    { "index": 6, "role": "verifier", "attempt": 2, "prompt_version": "verifier.v1", "latency_ms": 700, "status": "ok", "started_ms": 1760422603495, "input_ids": ["clm-0045-3"], "tool_calls": [] },
    { "index": 7, "role": "producer", "attempt": 1, "prompt_version": "producer.v1", "latency_ms": 600, "status": "ok", "started_ms": 1760422604200, "input_ids": ["clm-0045-1", "clm-0045-3"], "tool_calls": [] },
    { "index": 8, "role": "checks", "attempt": 1, "latency_ms": 6, "status": "ok", "started_ms": 1760422604805, "input_ids": ["ins-0045"], "tool_calls": [], "check_failures": [] }
  ],
  "claims": [
    { "claim": { "claim_id": "clm-0045-1", "kind": "fact", "template_id": "fact.forward_pass", "...": "…" }, "attempt": 1, "status": "approved" },
    { "claim": { "claim_id": "clm-0045-2", "kind": "fact", "template_id": "interp.space_opened_by_run", "...": "…" }, "attempt": 1,
      "status": "revised", "superseded_by": "clm-0045-3", "injected_fault": "bad_claim",
      "final": { "claim_id": "clm-0045-2", "decision": "revise", "reason_codes": ["template_kind_mismatch", "value_mismatch", "unsupported_causality"] } },
    { "claim": { "claim_id": "clm-0045-3", "kind": "interpretation", "template_id": "interp.space_opened_by_run", "...": "…" }, "attempt": 2, "status": "approved" }
  ],
  "released_claim_ids": ["clm-0045-3", "clm-0045-1"],
  "usage": { "model_calls": 5, "tokens_in": 7400, "tokens_out": 760 }
}
```

## UI rendering rules (`AgentTrace.tsx`)

- Steps in `index` order; role labels: Gate, Analyst, Verifier — deterministic checks, Verifier, Producer, Release checks, Fallback.
- Claim status badges: `approved` → "Approved", `rejected` → "Rejected", `revised` → "Revise → {superseded_by}",
  `unused` → "Approved (not shown)". `rejected` and `revised` claims appear under a **Blocked claim** heading.
- Reason-code labels (en): `missing_evidence_id` "Evidence missing", `future_evidence` "Uses future evidence",
  `value_mismatch` "Value differs from measurement", `unit_mismatch` "Unit mismatch", `unsupported_causality`
  "Claims more than the data shows", `counterevidence` "Contradicted by evidence", `insufficient_tracking`
  "Insufficient tracking", `template_kind_mismatch` "Wrong claim type".
- `injected_fault` / `fixture` → "Demo fixture" chip. Footer: "Decisions and evidence only — private model reasoning is not recorded."
