# API & WebSocket Delta (003)

Extends `specs/001-walking-skeleton/contracts/{rest-api,ws-protocol}.md` and `specs/002-synthetic-simulator/contracts/api-delta.md`.

## `GET /api/matches/{match_id}/snapshot?as_of_ms=<int>`

- `as_of_ms` optional; default = current session clock; values above the current session clock are clamped to it.
- 200 body validates against `ws_message.schema.json#/$defs/Snapshot`:
  - `session_clock_ms` = effective as-of;
  - `events` = events with `session_clock_ms ≤ as_of` (ascending sequence);
  - `latest_frame` = last frame with `session_clock_ms ≤ as_of` or `null`;
  - `moments` = `rank(detect_moments(state.snapshot(as_of), engine))`;
  - `insights` = `InsightLedger.released(as_of)`;
  - `state_version` = snapshot state version; `playback` = current playback.
- Errors: 404 `match_not_found`; 422 `invalid_as_of` (negative / non-integer).

Example: `GET /api/matches/demo-blue-amber-001/snapshot?as_of_ms=12000` → events `evt-0001…evt-0006`, `moments: []`
(the shot at ≈12.3 s is not yet in the snapshot).

## `GET /api/matches/{match_id}/evidence/{evidence_id}` (001, behaviour clarified)

- `metric-…` IDs now include every metric referenced by a broadcast moment (latest result per ID after revisions).
- `frm-…` IDs referenced by metric `inputs.frame_ids` resolve (via the state's frame store, as-of the session clock).

## WebSocket server messages used from 003

| type | When | Payload |
|---|---|---|
| `metric` | before each `moment` (new or revised), one per `metric_ids` entry; also 001's `forward_progress` | `MetricResult` |
| `moment` | moment new or revised (same `moment_id`, higher `state_version`) | `CandidateMoment` |
| `insight_revoked` | insight attached to a revised/removed moment, or whose evidence changed | `{"insight_id", "insight_version", "reason": "late_event_revision"}` |
| `snapshot` | on connect/resume (001), after seek (002), and after a moment is removed | `Snapshot` incl. `moments` |
| `error` | ingest gap released | `{"error": "sequence_gap", "detail": "missing 11-11"}` |

Ordering guarantee per change: all `insight_revoked` for the change → all `metric` → `moment`.

Client rules added:

- Upsert moments by `moment_id`; ignore a `moment` whose `state_version` is lower than the stored one.
- On `insight_revoked`, never show that (insight_id, version) again; hide it if active.
- Late events arrive as ordinary `event` messages; clients keep the event list sorted by `sequence`, not by arrival.
