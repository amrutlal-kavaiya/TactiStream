# Replay API & SceneAnnotations Contract (v1)

Owner: 005. Canonical schema to be added as `contracts/schemas/scene_annotations.schema.json` (draft 2020-12,
`$defs`: `SceneAnnotations`, `ReplayResponse`, `ReplayUnavailable`) with examples
`contracts/examples/{scene_annotations,replay_response,replay_unavailable}.json`. Pydantic models live in
`backend/src/tactistream/contracts/scene.py`; TS types are generated into `frontend/src/contracts/generated.ts`.

## Endpoint

`GET /api/matches/{match_id}/replay/{moment_id}`

| Status | Body | When |
|---|---|---|
| 200 | `ReplayResponse` | moment known as of the current session clock and tracking sufficient |
| 404 | `{"error":"match_not_found"}` / `{"error":"moment_not_found"}` | unknown match, or moment not (yet) detected |
| 409 | `ReplayUnavailable` | `tracking_coverage < 0.6`, or a required spatial metric is `unavailable/insufficient_tracking` |

Headers: `Content-Encoding: gzip` when the client accepts it and the body ≥ 1 KB. `Cache-Control: no-store` (the
server caches; clients cache per `moment_id` + `scene.state_version` in the store).

### ReplayResponse

```json
{
  "moment": { "...": "CandidateMoment (candidate_moment.schema.json)" },
  "frames": [ { "...": "TrackingFrame, ordered by session_clock_ms, window-inclusive" } ],
  "events": [ { "...": "MatchEvent, ordered by sequence" } ],
  "scene": { "...": "SceneAnnotations" }
}
```

### ReplayUnavailable (409)

```json
{
  "error": "insufficient_tracking",
  "detail": "Tracking coverage 0.42 is below 0.6 for mom-0061",
  "moment": { "...": "CandidateMoment" },
  "events": [ { "...": "MatchEvent" } ]
}
```

## SceneAnnotations

```json
{
  "schema_version": "1.0",
  "match_id": "demo-blue-amber-001",
  "moment_id": "mom-0045",
  "state_version": 512,
  "window": { "start_ms": 36000, "end_ms": 46500 },
  "frame_interval_ms": 100,
  "annotation_source": "insight",
  "tracking_coverage": 1.0,
  "partial_tracking": false,
  "annotations": [
    {
      "annotation_id": "highlight_blue_09",
      "kind": "highlight",
      "player_id": "blue-09",
      "team_id": "blue",
      "evidence_ids": ["metric-off_ball_run-0042"]
    },
    {
      "annotation_id": "path_amber_04",
      "kind": "path",
      "player_id": "amber-04",
      "team_id": "amber",
      "segments": [
        [
          { "t_ms": 36000, "frame_id": "frm-000360", "pos_m": [61.2, 30.1] },
          { "t_ms": 36100, "frame_id": "frm-000361", "pos_m": [61.3, 30.0] }
        ]
      ],
      "evidence_ids": ["metric-defender_follow-0042"]
    },
    {
      "annotation_id": "show_channel_0042",
      "kind": "channel",
      "metric_id": "metric-channel-0042",
      "anchor_event_id": "evt-0042",
      "passer_id": "blue-08",
      "receiver_id": "blue-11",
      "unit": "m",
      "keyframes": [
        {
          "phase": "before",
          "t_ms": 38300,
          "frame_id": "frm-000383",
          "passer_pos_m": [55.0, 33.1],
          "receiver_pos_m": [69.4, 29.0],
          "clearance_m": 1.9,
          "nearest_defender_id": "amber-04",
          "nearest_defender_pos_m": [62.1, 32.9],
          "closest_point_m": [61.6, 31.2]
        },
        {
          "phase": "at_pass",
          "t_ms": 42300,
          "frame_id": "frm-000423",
          "passer_pos_m": [58.1, 32.4],
          "receiver_pos_m": [71.2, 28.0],
          "clearance_m": 5.3,
          "nearest_defender_id": "amber-04",
          "nearest_defender_pos_m": [63.0, 35.8],
          "closest_point_m": [61.9, 30.9]
        }
      ],
      "evidence_ids": ["metric-channel-0042", "evt-0042", "frm-000383", "frm-000423"]
    }
  ],
  "unresolved": [
    { "annotation_id": "pressure_ring_blue_08", "reason": "metric_missing" }
  ]
}
```

Coordinates above are illustrative; real values come from 002 seed 42 and are frozen in
`backend/tests/golden/scene_space_creation_42.json`.

### Field rules

| Field | Rule |
|---|---|
| `state_version` | `moment.state_version` the scene was built from |
| `window` | `replay_window(moment, first_frame_ms)`: `end = moment.window.end_ms`; `start = clamp(moment.window.start_ms, end − 12000, end − 8000)`; `start = max(start, first_frame_ms)` |
| `annotation_source` | `insight` (union of all variants' `render.annotations` of the latest released, non-revoked bundle) or `default` |
| `tracking_coverage` | copied from the moment (0–1) |
| `partial_tracking` | any invisible player/ball in any window frame, or any consecutive-frame gap > 150 ms |
| `annotations[]` | sorted by `annotation_id`; every `pos_m` is copied from a frame or computed geometry on frame positions; numbers from metrics are copied, never recomputed for display |
| `evidence_ids` | IDs the drawer can resolve for this annotation |
| `unresolved[].reason` | `unknown_player` · `player_not_visible` · `metric_missing` · `metric_unavailable` · `outside_window` · `inconsistent_geometry` |

### Annotation kinds

| Kind | ID | Resolution (deterministic) |
|---|---|---|
| `highlight` | `highlight_{team}_{NN}` | player `{team}-{NN}`; must exist in metadata (`unknown_player`) and be visible in ≥ 1 window frame (`player_not_visible`). Client ring follows the interpolated player position. `evidence_ids`: ok metrics in `moment.metric_ids` whose `subject_ids` contain the player. |
| `path` | `path_{team}_{NN}` | polyline of that player's visible positions in window frames, split into a new segment at each invisible frame or gap > 150 ms; segments with < 2 points dropped; no visible points → `player_not_visible`. |
| `channel` | `show_channel_{seq:04d}` | metric `metric-channel-{seq}` (`metric_missing` if absent from the evidence index; `metric_unavailable` if not `ok`). Keyframes at `inputs.frame_ids[0]` (`before`) and `[1]` (`at_pass`); `passer_id`, `receiver_id` = `subject_ids[0..1]`; endpoints = their positions in those frames; `clearance_m` = `components.clearance_before_m` / `clearance_at_pass_m` copied; nearest defender = visible opponent minimising point-to-segment distance (ties → lowest player ID); `closest_point_m` = projection on the segment. If `round(recomputed_distance, 1)` differs from `clearance_m` by > 0.05 → `inconsistent_geometry`. Frames outside the window → `outside_window`. |
| `pressure_ring` | `pressure_ring_{team}_{NN}` | carrier `{team}-{NN}`; metric = the `ok` `pressure` metric in `moment.metric_ids` with `subject_ids[0] == carrier` and the latest `window.end_ms` (`metric_missing` otherwise). Anchor frame = last `inputs.frame_ids` entry; `center_m` = carrier position there; `defender_ids` = up to three nearest visible opponents; `radius_m` = round(max distance, 1); `score` = metric value; client shows it for `[t_ms − 1500, t_ms + 1500]` ∩ window. |

Pressure-ring object: `{annotation_id, kind, carrier_id, team_id, metric_id, t_ms, frame_id, center_m, radius_m,
defender_ids, score, unit: "score_0_100", evidence_ids}`.

### Default annotations (no released insight)

`default_annotations(moment, metrics) -> list[AnnotationId]`, used only when no released bundle exists:

| Pattern | Defaults |
|---|---|
| `space_creation` | `highlight_` runner (`off_ball_run.subject_ids[0]`), `path_` defender (`defender_follow` subject on the opposing team), `show_channel_{seq}` of the moment's channel metric |
| `press_turnover` | `pressure_ring_` carrier of the moment's latest pressure metric, `highlight_` actor of the first `tackle`/`interception`/`ball_recovery` in the window, `path_` nearest presser at the anchor frame |
| `switch_escape` | `pressure_ring_` passer of the switch pass, `highlight_` and `path_` its recipient |
| `shot`, `generic` | `highlight_` actor of the trigger event |

Missing ingredients simply drop the corresponding default (no unresolved entry for defaults).

## Evidence presentation extension (001 endpoint, additive)

`GET /api/matches/{match_id}/evidence/{evidence_id}?language=en|hi` (default `en`). For `kind = "metric"` the 200 body
adds:

```json
"presentation": {
  "language": "en",
  "title": "Passing-channel clearance",
  "definition": "Shortest distance from any visible opponent to the straight line between passer and receiver, measured at two times.",
  "limitation": "Supports interpretation; does not prove intent.",
  "unit_label": "m"
}
```

Rendered from catalog keys `metric_title.{kind}`, `metric_def.{kind}`, `limitation_key` and `unit.{unit}`. Event and
frame bodies are unchanged.
