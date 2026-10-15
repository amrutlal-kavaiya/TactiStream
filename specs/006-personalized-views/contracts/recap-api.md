# Recap API Contract (v1)

Owner: 006. Canonical document schema: `contracts/schemas/recap.schema.json` (unchanged, v1.0). Example:
`contracts/examples/recap.json`. Pydantic: `backend/src/tactistream/contracts/recap.py` (`Recap`, `RecapItem`,
`OverlayCue`, from 001).

## Endpoint

`POST /api/matches/{match_id}/recap`

Request:

```json
{ "mode": "fan", "language": "en", "pinned_player_id": "blue-09" }
```

`pinned_player_id` may be `null` or omitted. Validated as `ViewerPrefs` (`contracts/prefs.py`).

| Status | Body | When |
|---|---|---|
| 200 | `Recap` | ≥ 1 eligible released insight |
| 404 | `{"error":"match_not_found"}` | unknown match |
| 409 | `{"error":"no_moments_yet","detail":"No released insights as of 00:12.4"}` | no eligible insight |
| 422 | `{"error":"invalid_prefs","detail":"…"}` | bad mode/language, or pinned player not in roster |

Rules:

- **As-of**: only moments detected and insights released at or before the current session clock are considered.
- **Eligibility**: latest non-revoked version of each bundle with `claim_status ∈ {verified_fact,
  interpretation_supported, fallback_template}` (never `insufficient_data`), and the variant for `(mode, language)`
  present. All such bundles passed `check_packet` and `check_bundle_consistency` before release.
- **Ranking**: `rank_for_viewer(moments, prefs, lookup)` (see `ws-ranking.md`); take eligible moments in that order, first 8;
  **off-ball reservation**: if `pinned_player_id` is set and the best eligible `off_ball` moment is not in the 8, it
  replaces item 8. `rank` = 1..n after selection.
- **Item fields** from the `(mode, language)` variant: `insight_id`, `title`, `evidence_ids`; `replay_window` =
  `render.replay_window` if present else `replay_window(moment, first_frame_ms)` (005); `pinned_player_involvement` only
  when pinned.
- **No model call**: assembly, summary and timing are deterministic.

## Summary templates (catalog keys)

| Key | Used when | en (fan) example |
|---|---|---|
| `recap.summary.general` | no pin | "{count} key moments so far." |
| `recap.summary.pinned` | pin, ≥ 1 involved item | "{player} was involved in {count} key moments." |
| `recap.summary.pinned_off_ball` | appended when an included item has involvement `off_ball`, pattern `space_creation`, `claim_status = interpretation_supported` | ", including an off-ball run that helped create room for a forward pass." |
| `recap.summary.pinned_none` | pin, 0 involved items | "{player} has not been involved in a key moment yet." |

Analyst variants add counts by involvement: "{player}: {direct_count} direct and {off_ball_count} off-ball involvements
across {count} key moments." Slots are `player` (PlayerId, rendered via metadata display name) and integer counts. The
summary is ≤ 600 characters and subject to the same number/identity preservation property as claim templates.

## Overlay timing (recap-relative clock, ms from recap start)

```text
LEAD_IN_MS = 1500     MIN_CUE_MS = 2000     MAX_CUE_MS = 6000

segment_start[0] = 0
segment_len[i]   = LEAD_IN_MS + (replay_window[i].end_ms − replay_window[i].start_ms)
segment_start[i] = segment_start[i−1] + segment_len[i−1]

cue[i].start_ms  = segment_start[i] + LEAD_IN_MS                    # replay begins here
display_ms       = clamp(show_until_ms − show_from_ms, MIN_CUE_MS, MAX_CUE_MS)   # from the variant's render
cue[i].end_ms    = min(cue[i].start_ms + display_ms, segment_start[i] + segment_len[i])
cue[i].text      = variant.body if len(body) ≤ 200 else variant.title
cue[i].annotations = variant.render.annotations
```

Exactly one cue per item, in item order. Consumers derive segment boundaries from `items[*].replay_window` with the
formula above (normative; `LEAD_IN_MS` is part of this contract). Replay time inside segment *i* at recap time *t* is
`replay_window[i].start_ms + (t − segment_start[i] − LEAD_IN_MS)` for `t ≥ segment_start[i] + LEAD_IN_MS`.

Example (hero, Blue 9 pinned, fan/en): item 1 window 36000–46500 (10.5 s) → segment 0–12000, cue 1500–7500 (matches
`contracts/examples/recap.json`).

## Caching and identity

- `recap_id = "recap-{match_id}-{pinned_player_id or 'all'}-{mode}-{language}"`.
- `generated_at_state_version = content_state_version = max(state_version)` over considered moments and bundles.
- Cache key `(content_state_version, mode, language, pinned_player_id)`; LRU 64 entries per session; cleared on reset.
- Serialization `model_dump(mode="json", exclude_none=True)`; the cache stores the serialized bytes, so repeated
  responses are byte-identical.

## Client usage

`frontend/src/api/client.ts`:

```ts
export function createRecap(matchId: string, prefs: { mode: ViewerMode; language: Language; pinned_player_id: string | null })
  : Promise<{ ok: true; recap: Recap } | { ok: false; error: "no_moments_yet" }>;
```

**Download overlay JSON** saves `JSON.stringify(recap, null, 2)` as `${recap_id}.json` (`application/json`).
