# WebSocket Prefs & Ranking Contract (v1.1 addition)

Owner: 006. Extends `specs/001-walking-skeleton/contracts/ws-protocol.md` and
`contracts/schemas/ws_message.schema.json` (additive minor bump: `schema_version` "1.1" where carried; new server
`type` `ranking` and `$defs/Ranking`).

## Client → server: `prefs` (existing shape, now acted upon)

```json
{ "type": "prefs", "mode": "analyst", "language": "hi", "pinned_player_id": "blue-09" }
```

- Sent on every prefs change and immediately after each `snapshot` (connect and resume).
- Server stores `ConnectionPrefs` for this connection only. Unknown `pinned_player_id` → server keeps
  `pinned_player_id = null` and sends `{"type":"error","payload":{"error":"unknown_player","detail":"blue-77"}}`.
- `mode`/`language` do not change what the server sends (bundles always carry all four variants); they are stored for
  diagnostics and as the default for recap requests.

## Server → client: `ranking` (new, connection-scoped)

```json
{
  "type": "ranking",
  "seq": 1830,
  "match_id": "demo-blue-amber-001",
  "payload": {
    "pinned_player_id": "blue-09",
    "entries": [
      { "moment_id": "mom-0045", "rank": 1, "rank_score": 0.82, "pinned_involvement": "off_ball" },
      { "moment_id": "mom-0031", "rank": 2, "rank_score": 0.91, "pinned_involvement": "none" }
    ]
  }
}
```

Schema addition (`ws_message.schema.json`):

```json
"Ranking": {
  "type": "object",
  "required": ["pinned_player_id", "entries"],
  "additionalProperties": false,
  "properties": {
    "pinned_player_id": { "anyOf": [{ "$ref": "common.schema.json#/$defs/PlayerId" }, { "type": "null" }] },
    "entries": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["moment_id", "rank", "rank_score", "pinned_involvement"],
        "additionalProperties": false,
        "properties": {
          "moment_id": { "$ref": "common.schema.json#/$defs/MomentId" },
          "rank": { "type": "integer", "minimum": 1 },
          "rank_score": { "type": "number" },
          "pinned_involvement": { "enum": ["direct", "off_ball", "none"] }
        }
      }
    }
  }
}
```

plus `"ranking"` in `ServerMessage.type` enum and an `if type == ranking then payload $ref Ranking` clause.

Rules:

- **Not logged**: `ranking` messages are not appended to the per-match message log; `seq` = current head seq (not
  incremented). Clients MUST NOT treat them as advancing `last_seq` beyond the head they already know.
- **When sent**: after each `prefs`; after each `snapshot` sent to a connection that has prefs; after each `moment`
  broadcast (new or updated moment) to every connection with prefs.
- **Content**: all moments known as of the session clock, ordered by `rank(moments, pinned_player_id, lookup=…)`;
  `rank` is 1-based; `pinned_involvement = "none"` for every entry when no player is pinned.

## Involvement and ordering (normative)

```text
direct    pinned player is player_id or recipient_id of any event with session_clock_ms in moment.window
off_ball  not direct, and pinned player ∈ subject_ids of an `ok` off_ball_run or defender_follow metric in moment.metric_ids
none      otherwise

sort key  (pinned_involvement == "none", −rank_score, moment_id)       # pinned bonus: involved moments first
          without a pin: (−rank_score, moment_id)                        # 003 default
```

## Client handling

- `MatchSocket` exposes `sendPrefs(prefs)`; it re-sends the last prefs after every snapshot.
- `matchStore.applyMessage(ranking)` stores `ranking` (replacing the previous one); `Timeline` and `RecapPanel` read it.
  Absent a ranking, the client orders by `rank_score` desc then `moment_id`.
