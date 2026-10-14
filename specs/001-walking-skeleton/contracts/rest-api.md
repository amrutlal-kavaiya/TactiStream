# REST API Contract (v1)

Base path: same origin as the frontend. JSON bodies; errors are `{"error": "<code>", "detail": "<human text>"}`.
Endpoints added by later features are listed with their owning feature so the API surface is visible in one place.

| Method & path | Feature | Request | 200 response | Errors |
|---|---|---|---|---|
| `GET /healthz` | 001 (004 adds `demo_fixtures`) | — | `{"status":"ok","version":"0.1.0","bus":"memory\|eventhubs","agents":"off\|scripted\|foundry","demo_fixtures":false}` | — |
| `POST /api/sessions` | 001 (002 adds seed/scenario/variant; 009 adds capacity cap) | `{"scenario":"skeleton"}` or `{"scenario":"space_creation","seed":42,"variant":"A"}` | `{"session_id":"s-…","match_id":"…","ws_path":"/ws/matches/{match_id}"}` | 422 `invalid_scenario` (unknown, or its fixture is missing on this server), 422 `invalid_request` (malformed body), 503 `session_start_timeout` (metadata not ingested in time; session discarded), 503 `capacity_reached` (009) |
| `POST /api/matches/{match_id}/control` | 001 (002 adds `seek`, `speed`) | `{"action":"play"\|"pause"\|"reset"}` · `{"action":"speed","speed":1.0}` · `{"action":"seek","to_ms":12000}` | `{"playback":{"state":"playing","speed":1.0,"seed":42},"session_clock_ms":0}` | 404 `match_not_found`, 422 `invalid_action` (unknown action), 422 `invalid_request` (malformed body) |
| `GET /api/matches/{match_id}/evidence/{evidence_id}?language=en\|hi` | 001 (005 adds `presentation`) | — | `{"evidence_id":"evt-0042","kind":"event"\|"frame"\|"metric","record":{…contract record…}}`; metric records add `presentation` {definition, limitation, unit_label} | 404 `match_not_found`, 404 `evidence_not_found` (unknown id, or not yet reached by the session clock), 422 `invalid_request` (bad `language`) |
| `GET /api/matches/{match_id}/snapshot?as_of_ms=` | 003 | — | `ws_message.schema.json#/$defs/Snapshot` | 404 |
| `GET /api/matches/{match_id}/replay/{moment_id}` | 005 | — | `ReplayResponse` (`scene_annotations.schema.json`) | 404 `match_not_found` / `moment_not_found`, 409 `insufficient_tracking` (`ReplayUnavailable` body with `moment` and events) |
| `GET /api/matches/{match_id}/traces/{trace_id}` | 004 | — | `AgentTrace` (`agent_trace.schema.json`) | 404 |
| `POST /api/matches/{match_id}/fixtures` | 004 | `{"inject":"bad_claim"\|"model_timeout"}` (only when `TACTISTREAM_DEMO_FIXTURES=true`) | `{"armed":"bad_claim"}` | 404 (fixtures disabled or match), 422 |
| `POST /api/matches/{match_id}/recap` | 006 | `{"mode":"fan","language":"en","pinned_player_id":"blue-09"\|null}` | `recap.schema.json` | 404, 409 `no_moments_yet`, 422 `invalid_prefs` |
| `GET /api/evaluation/results` | 008 | — | `EvaluationReport` (`evaluation_report.schema.json`) | 404 `report_not_found` |
| `GET /api/diagnostics/latency?match_id=` | 007 | — | latency percentiles per kind, fallback counted separately | 404 when diagnostics disabled |

Notes:

- SPA routes served by FastAPI's static fallback: `/`, `/demo` (009, `?seed=42`), `/evidence` (008), `/render/recap` (009, optional).

- `evidence_id` resolution uses the session `EvidenceIndex` and only returns records with `session_clock_ms <= current session clock`
  (as-of access; constitution III).
- `reset` keeps the same `match_id` and seed and leaves the replay `paused` at `session_clock_ms` 0 (send `play` to
  restart); a new seed creates a new session (`POST /api/sessions`). Live state is cleared when the republished metadata
  is ingested, and connected clients then receive a fresh `snapshot` (ws-protocol.md).
- `POST /api/sessions` for a scenario whose match already has a session resets that session and returns the same
  `session_id` and `match_id`; a new session starts `paused`.
- Body validation failures (FastAPI `RequestValidationError`) use the same envelope with code `invalid_request`.
