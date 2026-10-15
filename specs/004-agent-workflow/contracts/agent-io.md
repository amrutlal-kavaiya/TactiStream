# Agent I/O Contract (v1)

Outputs are the `claim.schema.json` `$defs` (with proposed C2 `SlotValue.value/unit`). Inputs are compact JSON built by
executors from `AgentTools` results (tools.md); they are internal (not in `/contracts`) but versioned by `input_version`
and asserted by unit tests. All examples use the hero moment `mom-0045`.

## ModelClient

```python
async def complete_json(role, system, user, schema_ref, timeout_s) -> ModelResponse(data, usage_in, usage_out, latency_ms)
```

| Role | schema_ref | Max output tokens (setting) | Called by |
|---|---|---|---|
| `analyst` | `AnalystOutput` | 600 (`TACTISTREAM_ANALYST_MAX_TOKENS`) | `run_analyst` |
| `verifier` | `VerifierOutput` | 400 | `run_verifier` |
| `producer` | `ProducerOutput` | 300 | `run_producer` |
| `single_agent` | `SingleAgentOutput` = `{"analyst": AnalystOutput, "producer": ProducerOutput}` | 900 | `SingleAgentRunner` (008 only) |

Failure semantics: `ModelTimeout` (budget exceeded) → fallback `timeout`; `ModelError(kind)` with kind
`invalid_json | schema_invalid | transport | throttled | script_missing` → fallback `model_error`. No retries.

## Analyst

**Input** (`user`, attempt 1):

```json
{
  "input_version": 1,
  "attempt": 1,
  "as_of_ms": 46500,
  "next_claim_ids": ["clm-0045-1", "clm-0045-2"],
  "moment": { "moment_id": "mom-0045", "pattern": "space_creation", "trigger_event_id": "evt-0045",
              "window": { "start_ms": 36000, "end_ms": 46500 },
              "involved_player_ids": ["blue-09", "blue-08", "blue-11", "amber-04"], "tracking_coverage": 1.0 },
  "snapshot": { "...": "get_match_snapshot() result" },
  "events": [ { "event_id": "evt-0042", "t_ms": 42300, "type": "pass", "team": "blue", "player": "blue-08",
                "recipient": "blue-11", "outcome": "complete", "start_m": [58.1, 32.4], "end_m": [71.2, 28.0] } ],
  "metrics": [ { "metric_id": "metric-channel-0042", "kind": "channel", "status": "ok", "value": 3.4, "unit": "m",
                 "components": { "clearance_before_m": 1.9, "clearance_at_pass_m": 5.3 },
                 "subject_ids": ["blue-08", "blue-11"], "window": { "start_ms": 38300, "end_ms": 42300 } } ],
  "geometry": [ { "kind": "positions", "at_ms": 42300, "frame_id": "frm-000423",
                  "positions": { "blue-09": [74.0, 40.2], "amber-04": [76.1, 37.5] } } ],
  "templates": [ { "template_id": "interp.space_opened_by_run", "kind": "interpretation",
                   "slots": { "runner": "player", "defender": "player", "channel_gain": "metric:channel(m,1)" },
                   "required_evidence_kinds": ["off_ball_run", "defender_follow", "channel"], "requires_tracking": true } ],
  "annotation_formats": ["highlight_{team}_{NN}", "path_{team}_{NN}", "pressure_ring_{team}_{NN}", "show_channel_{seq:04d}"]
}
```

Attempt 2 adds `"prior_claims": [Claim…]`, `"verdicts": [Verdict…]` (final verdicts), and `next_claim_ids` continuing
the sequence (`clm-0045-3`, …). Only claims with final decision `revise` may be resubmitted.

**Output**: `AnalystOutput` — see `contracts/examples/analyst_output.json`, with C2 values on metric slots:

```json
"channel_gain": { "kind": "metric", "metric_id": "metric-channel-0042", "value": 3.4, "unit": "m" }
```

Executor post-processing: validate schema → overwrite `claim_id`s with `ClaimLedger.next_claim_id()` in order →
append `ClaimRecord`s → (fixture) apply `mutate_to_bad_claim` on attempt 1 → record trace step.

## Verifier

**Input** (only claims not rejected by pre-checks):

```json
{
  "input_version": 1,
  "attempt": 1,
  "as_of_ms": 46500,
  "moment": { "moment_id": "mom-0045", "pattern": "space_creation", "trigger_event_id": "evt-0045" },
  "claims": [ { "claim": { "...": "Claim" },
                "precheck": { "claim_id": "clm-0045-2", "decision": "approve", "reason_codes": ["ok"] },
                "recomputed": [ { "metric_id": "metric-channel-0042", "status": "ok", "value": 3.4, "unit": "m" } ] } ],
  "counterevidence": [ { "metric_id": "metric-pressure-0042", "kind": "pressure", "status": "ok", "value": 22, "unit": "score_0_100" },
                       { "metric_id": "metric-receiver_separation-0042", "kind": "receiver_separation", "status": "ok", "value": 4.1, "unit": "m" } ],
  "allowed_reason_codes": ["ok", "unsupported_causality", "counterevidence"]
}
```

**Output**: `VerifierOutput` with one `Verdict` per input claim. Missing verdict for a claim → treated as `revise`
with `unsupported_causality` and note "no verdict returned". Reason codes outside `allowed_reason_codes` → `schema_invalid`.

## Producer

**Input**:

```json
{
  "input_version": 1,
  "moment": { "moment_id": "mom-0045", "pattern": "space_creation", "trigger_event_type": "shot" },
  "approved": [
    { "claim_id": "clm-0045-1", "kind": "fact", "template_id": "fact.forward_pass",
      "title_keys": ["title.forward_pass"], "requested_annotations": [],
      "preview": { "fan_en": "Blue 8 played a forward pass to Blue 11 (13.1 m forward).",
                   "analyst_en": "Blue 8 played a forward pass to Blue 11 (13.1 m forward). Progress along attack axis: 13.1 m (evt-0042)." } },
    { "claim_id": "clm-0045-2", "kind": "interpretation", "template_id": "interp.space_opened_by_run",
      "title_keys": ["title.space_opened_before_shot", "title.space_opened_before_pass"],
      "requested_annotations": ["highlight_blue_09", "path_amber_04", "show_channel_0042"],
      "preview": { "fan_en": "Blue 9's run helped create room for the pass.",
                   "analyst_en": "Amber 4 shifted toward Blue 9 while the passing channel widened by 3.4 m. The next forward pass used that space." } }
  ],
  "rules": { "max_claims_per_mode": 2, "panels": ["lower_third", "side_panel"], "priority_range": [1, 3] }
}
```

Previews are rendered by code so the Producer can judge readability; it cannot alter them.

**Output** (`ProducerOutput`):

```json
{
  "moment_id": "mom-0045",
  "fan":     { "title_template_id": "title.space_opened_before_shot", "claim_ids": ["clm-0045-2"],
               "annotations": ["highlight_blue_09", "path_amber_04", "show_channel_0042"], "priority": 2, "panel": "lower_third" },
  "analyst": { "title_template_id": "title.space_opened_before_shot", "claim_ids": ["clm-0045-2", "clm-0045-1"],
               "annotations": ["highlight_blue_09", "path_amber_04", "show_channel_0042"], "priority": 2, "panel": "side_panel" }
}
```

Resulting hero variants (assembled by code):

| Variant | title | body |
|---|---|---|
| fan/en | Space opened before the shot | Blue 9's run helped create room for the pass. |
| analyst/en | Space opened before the shot | Amber 4 shifted toward Blue 9 while the passing channel widened by 3.4 m. The next forward pass used that space. Blue 8 played a forward pass to Blue 11 (13.1 m forward). Progress along attack axis: 13.1 m (evt-0042). |
| fan/hi | शॉट से पहले जगह बनी | ब्लू 9 की दौड़ ने पास के लिए जगह बनाने में मदद की। |
| analyst/hi | शॉट से पहले जगह बनी | एम्बर 4 ब्लू 9 की ओर खिसके, और पासिंग चैनल 3.4 मी चौड़ा हुआ। … (13.1 …) |

## Scripted replies (`data/fixtures/agent_scripts/*.json`)

```json
{
  "script_version": 1,
  "deployment": "scripted",
  "replies": [
    { "role": "analyst",  "moment_id": "mom-0045", "attempt": 1, "delay_ms": 1400, "usage": { "in": 1900, "out": 260 }, "data": { "...": "AnalystOutput" } },
    { "role": "verifier", "moment_id": "mom-0045", "attempt": 1, "delay_ms": 900,  "usage": { "in": 1300, "out": 120 }, "data": { "...": "VerifierOutput" } },
    { "role": "analyst",  "moment_id": "mom-0045", "attempt": 2, "delay_ms": 1100, "usage": { "in": 2100, "out": 180 }, "data": { "...": "corrected AnalystOutput" } },
    { "role": "verifier", "moment_id": "mom-0045", "attempt": 2, "delay_ms": 700,  "usage": { "in": 1200, "out": 90 },  "data": { "...": "VerifierOutput" } },
    { "role": "producer", "moment_id": "mom-0045", "attempt": 1, "delay_ms": 600,  "usage": { "in": 900,  "out": 110 }, "data": { "...": "ProducerOutput" } },
    { "role": "analyst",  "moment_id": "mom-0061", "attempt": 1, "error": "invalid_json" }
  ]
}
```

`ScriptedReply = data | error ("timeout" sleeps past any budget; other kinds raise ModelError)`; `delay_ms` is slept on
the injected clock; `usage` omitted → `None`. Verifier attempt-1 replies list verdicts for whatever claims the script
expects; tests that mutate claims (bad_claim) still use the same scripted Verifier reply, and deterministic pre-checks
supply the decisive verdicts.

## Prompt design (`agents/prompts/*.md`)

File layout: YAML front matter (`prompt_id`, `prompt_version`, `schema_ref`) + body. At call time
`system = body + "\n\n## Output contract\n" + JSON Schema(schema_ref) + "\n\n## Templates\n" + eligible templates JSON`
and `user = json.dumps(input, separators=(",", ":"))`. Changing a body bumps `prompt_version` (`analyst.v2`, …);
the version is recorded in every trace step and in 008 results.

### `analyst.md` (analyst.v1)

> You are the Analyst in TactiStream, which explains moments in a synthetic football match between fictional teams Blue and Amber.
> Use only the provided as-of snapshot and registered evidence tools. Separate observed facts from interpretation. Every factual claim needs event or metric IDs. Choose at most two useful claims. If the required positions are absent, abstain from the spatial explanation.
>
> Rules:
> 1. Use only `template_id`s listed under Templates. A claim's `kind` must equal the template's kind.
> 2. Fill every slot of the template. Player slots use player IDs that appear in the evidence you cite. Metric slots use metric IDs from `metrics` whose status is `ok`, and copy `value` and `unit` exactly as given. Never compute, round, estimate or invent a number.
> 3. `evidence_ids` must include every metric used in a slot, at least one metric of each `required_evidence_kinds` entry, and the events you rely on. Never cite an ID that is not in the input. Never cite anything later than `as_of_ms`.
> 4. Prefer one fact (what happened) and at most one interpretation (what it contributed to). Interpretations describe contribution or timing, never intent or causation.
> 5. `uncertainty`: `low` for facts; `medium` for interpretations whose required metrics are all ok; otherwise do not propose the interpretation.
> 6. `requested_annotations`: only `highlight_`, `path_` or `pressure_ring_` IDs for players in your slots, and `show_channel_{seq}` for a channel metric you cite.
> 7. `rationale`: one public sentence (≤ 280 characters) naming the evidence. No speculation about intent; avoid words such as "caused", "forced", "because", "deliberately".
> 8. If tracking is insufficient for every eligible interpretation, return only fact claims. If no claim is supported, return `abstained: true` with `abstain_reason`.
> 9. On attempt 2 you receive `prior_claims` and `verdicts`. Resubmit corrected versions only of claims whose decision is `revise`, addressing every reason code. Do not resubmit rejected claims. Use IDs from `next_claim_ids`.
>
> Return one JSON object matching the output contract and nothing else.

### `verifier.md` (verifier.v1)

> You are the Verifier in TactiStream.
> Check every claim against referenced evidence and available counterevidence. Reject absent IDs, future evidence, changed values, and causal certainty unsupported by the data. Return approve, revise, or reject with short reasons. Do not introduce replacement measurements.
>
> Deterministic checks have already verified IDs, timing, values, units and template fit; their results are in `precheck`. Judge only:
> - `unsupported_causality`: the interpretation, its `uncertainty`, or its `rationale` claims more than the evidence shows (for example intent, or that one movement alone produced an outcome).
> - `counterevidence`: a metric in `counterevidence` contradicts the interpretation (for example the receiver was under high pressure, or separation fell).
>
> Decide `approve` when the evidence supports the claim as worded by its template, `revise` when a corrected claim could be supported, `reject` when it cannot. When unsure between approve and revise, choose revise. Use only `allowed_reason_codes`. `note` ≤ 200 characters, citing IDs. Never add claims, IDs or numbers.
>
> Return one JSON object matching the output contract and nothing else.

### `producer.md` (producer.v1)

> You are the Producer in TactiStream.
> Use only approved claims. Fan mode uses plain language; Analyst mode exposes metrics and evidence. Preserve identities, numbers, units and uncertainty across languages. Output the fixed overlay schema and respect its timing budget.
>
> You do not write text: every sentence is rendered from reviewed templates in English and Hindi (see `preview`). For each mode choose:
> - `claim_ids`: 1–2 approved IDs in display order. Fan: one claim, preferring an interpretation when approved. Analyst: the interpretation first (if any), then the supporting fact.
> - `title_template_id`: one of the `title_keys` of the claims you include, best matching the moment.
> - `annotations`: a subset of the `requested_annotations` of the claims you include (Fan: at most 3).
> - `priority`: 1 (most important) to 3; use 2 for an interpretation that explains a shot or turnover, 3 for a routine fact.
> - `panel`: `lower_third` for Fan; `side_panel` for Analyst unless the body is a single sentence.
>
> Return one JSON object matching the output contract and nothing else.

### `single_agent.md` (single_agent.v1, 008 baseline)

> Concatenation of the Analyst rules (1–8) and the Producer rules, with the instruction: "First choose claims as the
> Analyst, then plan both modes as the Producer using only those claims. There is no separate verification step."
> Output contract: `SingleAgentOutput`.
