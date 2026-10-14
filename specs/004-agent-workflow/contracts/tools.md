# Agent Tools Contract (v1) — `backend/src/tactistream/agents/tools.py`

Read-only, typed functions bound to **one** immutable `MatchSnapshot` (as-of view from `MatchState.snapshot(as_of_ms)`)
and the `MetricEngine`. Executors call them to build evidence packs (research R2); models never call them directly.
The same methods back the baselines (008) and could later be exposed through MCP without changing semantics.

## General rules

- `as_of_ms = moment.window.end_ms`. Any argument referring to time `> as_of_ms`, or any record whose time is
  `> as_of_ms` (event `session_clock_ms`, frame `session_clock_ms`, metric `window.end_ms`, metric anchor event time),
  returns `{"error": "future_evidence", "detail": "..."}` with **no partial data**.
- Payloads are compact JSON: IDs, enums, rounded numbers (coordinates 1 dp; metric values exactly as `MetricResult.value`).
  Never included: `match_id`, display names, `source.seed`, generation manifest fields, scenario labels, any record after
  `as_of_ms`. Deny-list keys asserted by tests: `match_id`, `scenario`, `label`, `manifest`, `intended`, `outcome_after`, `seed`.
- Every call appends a `ToolCallRecord{tool, args, status: "ok"|"error", result_ids, error_code?, latency_ms}` to the
  run's trace via the injected sink. `result_ids` = every event/frame/metric/moment ID in the response.
- Metrics computed through `get_metric` are registered in the session `EvidenceIndex` (time = `window.end_ms`) so the
  evidence drawer can open any ID an agent cites.
- Errors (returned, never raised to the model input builder): `future_evidence`, `unknown_metric`, `unknown_event`,
  `invalid_window` (end < start or span > 15000 ms), `invalid_params`, `insufficient_tracking` (geometry only).

## Role access

| Tool | Analyst pack | Verifier pack | Producer pack | Baselines |
|---|---|---|---|---|
| `get_match_snapshot` | ✓ | ✓ | ✓ (pattern/trigger only) | ✓ |
| `get_event_window` | ✓ | ✓ | — | ✓ |
| `get_metric` | ✓ | ✓ (recompute + counterevidence) | — | ✓ |
| `inspect_geometry` | ✓ | ✓ (optional) | — | ✓ |
| `build_recap_candidates` | — | — | ✓ (006 recap ordering; unused for single moments) | — |

## `get_match_snapshot() -> dict`

```json
{
  "as_of_ms": 46500,
  "state_version": 512,
  "period": 1,
  "teams": [ { "team_id": "blue", "attack_direction": 1 }, { "team_id": "amber", "attack_direction": -1 } ],
  "players": [ { "player_id": "blue-09", "team_id": "blue", "role": "FW" } ],
  "recent_event_ids": ["evt-0038", "evt-0039", "evt-0040", "evt-0041", "evt-0042", "evt-0043", "evt-0044", "evt-0045"],
  "tracking": { "coverage_in_window": 1.0,
                "gaps": [ { "player_id": "amber-04", "start_ms": 40000, "end_ms": 43000 } ] }
}
```

`players` lists the 22 player IDs with team and role (no names). `recent_event_ids` = last 12 events ≤ `as_of_ms`.
`tracking.gaps` lists invisible intervals ≥ 300 ms for involved players within the moment window.

## `get_event_window(start_ms: int, end_ms: int) -> dict`

```json
{ "start_ms": 36000, "end_ms": 46500,
  "events": [ { "event_id": "evt-0042", "seq": 42, "t_ms": 42300, "type": "pass", "team": "blue", "player": "blue-08",
                "recipient": "blue-11", "outcome": "complete", "start_m": [58.1, 32.4], "end_m": [71.2, 28.0], "duration_ms": 900 } ] }
```

Ordered by `seq`. `end_ms > as_of_ms` → `future_evidence`. Span > 15000 ms → `invalid_window`.

## `get_metric(metric_id: str) -> dict`

Parses `metric-{kind}-{anchor_seq:04d}`, resolves anchor `evt-{anchor_seq:04d}` in the snapshot, calls
`MetricEngine.compute(kind, snapshot, anchor_event_id)`.

```json
{ "metric_id": "metric-channel-0042", "kind": "channel", "definition_version": "channel.v1", "status": "ok",
  "value": 3.4, "unit": "m", "components": { "clearance_before_m": 1.9, "clearance_at_pass_m": 5.3 },
  "subject_ids": ["blue-08", "blue-11"], "window": { "start_ms": 38300, "end_ms": 42300 },
  "input_event_ids": ["evt-0042"], "input_frame_range": ["frm-000383", "frm-000423"], "input_frame_count": 41,
  "limitation_key": "limitation.channel" }
```

Unavailable: `{"metric_id": …, "kind": …, "status": "unavailable", "unavailable_reason": "insufficient_tracking", …}`
(no `value`). Unknown kind → `unknown_metric`; anchor event missing → `unknown_event`; anchor or window after
`as_of_ms` → `future_evidence`. `metric_result(metric_id) -> MetricResult` is the typed equivalent used by pre-checks.

## `inspect_geometry(kind, params, at_ms) -> dict`

Resolves the latest frame with `session_clock_ms ≤ at_ms`; `at_ms > as_of_ms` → `future_evidence`. Geometry
arithmetic is delegated to 003 `metrics/geometry`. Numbers returned here are **not** citable in claim text (only
metric slots render numbers); the `frame_id` may be cited as evidence.

| kind | params | result |
|---|---|---|
| `positions` | `{"player_ids": [..≤ 8]}` | `{"frame_id", "at_ms", "positions": {pid: [x, y] \| null}}` (`null` = invisible) |
| `distance` | `{"a": pid, "b": pid}` | `{"frame_id", "at_ms", "status": "ok", "distance_m": 6.2}` or `status: "unavailable"` |
| `nearest_opponents` | `{"player_id": pid, "n": 1..3}` | `{"frame_id", "at_ms", "opponents": [{"player_id", "distance_m"}]}` (visible only) |
| `lane_clearance` | `{"passer": pid, "receiver": pid}` | `{"frame_id", "at_ms", "status", "clearance_m"}` |

Subject player invisible → `{"error": "insufficient_tracking"}`; unknown kind or bad params → `invalid_params`.

## `build_recap_candidates(prefs: NarrativePrefs) -> dict`

```json
{ "candidates": [ { "moment_id": "mom-0045", "pattern": "space_creation", "window": { "start_ms": 36000, "end_ms": 46500 },
                    "rank_score": 0.82, "pinned_involvement": "off_ball", "insight_id": "ins-0045", "insight_version": 1 } ] }
```

Moments detected at or before `as_of_ms`, ordered by `rank_score` with a +0.2 boost when the pinned player is in
`involved_player_ids` (`pinned_involvement`: `direct` if actor/recipient of the trigger or a window pass, `off_ball` if
only a metric subject, `none`); max 8. 006 may replace the ranking function behind this method; the payload shape is stable.
