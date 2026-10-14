# WebSocket Protocol (v1) — `/ws/matches/{match_id}`

Schema: `/contracts/schemas/ws_message.schema.json`. Text frames, one JSON object per frame.

## Connection lifecycle

1. Client connects. Server immediately sends `{"type":"snapshot","seq":N,...}` where `N` is the current head seq.
2. Server streams live messages with `seq` strictly increasing by 1 per message for this match.
3. Client tracks `last_seq` (highest processed). On reconnect it sends `{"type":"resume","last_seq":K}` as the first message.
4. Server replies with a fresh `snapshot` (seq = head). Messages with `seq <= head` are covered by the snapshot; nothing older is replayed.
   Clients MUST treat the snapshot as authoritative and replace local state (prevents double counting).
5. `heartbeat` every 10 s with `payload: {"session_clock_ms": …}`; client reconnects with exponential backoff (0.5 s → 8 s) after 25 s silence.

## Server → client

| type | payload | Notes |
|---|---|---|
| `snapshot` | `Snapshot` | metadata, events so far, latest frame, moments, insight bundles, playback |
| `event` | `MatchEvent` | after dedupe and ordering |
| `frame` | `TrackingFrame` | 10 Hz; client may drop frames when tab hidden |
| `metric` | `MetricResult` | |
| `moment` | `CandidateMoment` | 003+ |
| `insight` | `InsightBundle` (all mode × language variants) | client picks the variant matching local prefs |
| `insight_revoked` | `InsightRevoked` | 003+ late-event revisions |
| `narrative_status` | `NarrativeStatus` | 004+ stage updates; skeleton only sends `fallback` on check failure |
| `ranking` | `RankingPayload` | 006: sent only to the connection whose `prefs` changed; carries the current head `seq` and is not added to the shared log |
| `heartbeat` | `{session_clock_ms}` | |
| `error` | `{"error": code, "detail": text}` | non-fatal |

## Client → server

| type | fields | Effect |
|---|---|---|
| `resume` | `last_seq` | fresh snapshot |
| `prefs` | `mode`, `language`, `pinned_player_id` | 006: affects moment ranking and recap for this connection only |
| `display_ack` | `target_kind`, `target_id`, `server_seq` | records fast-overlay latency sample |

## Display rules (client)

- Show at most one insight card. Higher `render.priority` (1 = highest) preempts lower; ties → newest.
- Never display a packet when `session_clock_ms > expires_at_session_ms`; move it to the timeline instead.
