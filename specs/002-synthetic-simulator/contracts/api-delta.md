# API Delta (002) — sessions, scenarios, playback control

Extends `specs/001-walking-skeleton/contracts/rest-api.md`. Errors keep the `{"error": code, "detail": text}` shape.

## `GET /api/scenarios` (new)

200:

```json
[
  {"scenario": "demo_match", "display_name": "Demo match (scripted, ~4.5 min)", "variants": ["A", "B", "C"], "default_seed": 42, "duration_ms": 278300},
  {"scenario": "space_creation", "display_name": "Space creation (scripted)", "variants": ["A", "B", "C"], "default_seed": 42, "duration_ms": 14100},
  {"scenario": "tracking_gap", "display_name": "Missing tracking (fixture)", "variants": ["A", "B", "C"], "default_seed": 42, "duration_ms": 14100},
  {"scenario": "skeleton", "display_name": "Skeleton fixture", "variants": ["A"], "default_seed": 42, "duration_ms": 5900}
]
```

Order: `demo_match`, `space_creation`, `press_turnover`, `switch_escape`, `run_no_channel`, `press_no_turnover`,
`switch_closed`, `tracking_gap`, `skeleton`. `duration_ms` is for the default seed and variant A (illustrative values above).
Only dev variants are listed.

## `POST /api/sessions` (extended)

Request: `{"scenario": "skeleton"}` or `{"scenario": "space_creation", "seed": 42, "variant": "A"}` (`seed` default 42,
`variant` default `"A"`).

200:

```json
{"session_id": "s-3f9c1a2b", "match_id": "demo-blue-amber-001", "ws_path": "/ws/matches/demo-blue-amber-001",
 "scenario": "space_creation", "seed": 42, "variant": "A", "duration_ms": 14100, "shared": false}
```

`shared = true` when an existing session for the same (scenario, seed, variant) was returned.

| Status | `error` | When |
|---|---|---|
| 422 | `invalid_scenario` | unknown scenario |
| 422 | `invalid_seed` | seed outside 1–9999, or seed ≠ 42 for `skeleton` |
| 422 | `invalid_variant` | variant not in A–F, or ≠ A for `skeleton` |
| 422 | `eval_split_not_served` | seed ≥ 10000 or variant D–F |
| 429 | `too_many_sessions` | 8 sessions exist and every one has a connected viewer |

## `POST /api/matches/{match_id}/control` (extended)

| Body | Effect |
|---|---|
| `{"action": "play" \| "pause" \| "reset"}` | unchanged (001) |
| `{"action": "speed", "speed": 0.5 \| 1.0 \| 2.0}` | `FeedReplayer.set_speed`; clock continuous |
| `{"action": "seek", "to_ms": 12000}` | `MatchSession.seek` → burst apply → one `snapshot` broadcast |

200: `{"playback": {"state": "paused", "speed": 2.0, "seed": 42}, "session_clock_ms": 12000}`.
422 `invalid_action` for unknown action, speed not in the set, negative or non-integer `to_ms`. `to_ms` beyond the feed end
clamps to the end and returns `state: "ended"`.

## WebSocket (`/ws/matches/{match_id}`)

No new message types. After `seek`, every client receives one `snapshot` (`seq` = head) — clients already replace local
state on snapshot (001 protocol). `Snapshot.playback.speed` reflects the current speed.
