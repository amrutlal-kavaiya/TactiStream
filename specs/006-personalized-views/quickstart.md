# Quickstart: 006 Personalized Views

## Prerequisites

001–005 merged; `make install` done. No Azure needed (`TACTISTREAM_AGENTS=scripted`).

```bash
TACTISTREAM_AGENTS=scripted make dev
```

## Fan ↔ Analyst, English ↔ Hindi

1. http://localhost:5173 → **Start demo match** (space_creation, seed 42) → wait for "Space opened before the shot".
2. Top bar **Fan / Analyst**: Fan shows "Blue 9's run helped create room for the pass."; Analyst shows the defender /
   channel sentence with the metre values, time window and evidence chips. Open **Evidence** in Analyst: definitions,
   components and the **Agent trace** tab. DevTools Network shows no request when toggling.
3. Top bar **EN / हिं**: chrome and card switch to Hindi ("ब्लू 9 की बिना गेंद की दौड़ ने पास के लिए जगह बनाने में मदद
   की।"); the numbers (1.9, 5.3) and player identities are unchanged; labels "व्याख्या", "सिंथेटिक".
4. Press **Why?** in each mode: Fan shows a single pulse and no numbers on the band; Analyst shows "1.9 मीटर → 5.3 मीटर".

## Pin a player

5. Side panel **Player focus** → choose "Blue 9" → **Pin**. Timeline "Key moments" re-orders: the space-creation moment
   moves to #1 with an "Off-ball" badge. **Unpin** restores the previous order.

## Recap

6. **Generate recap** → summary "Blue 9 was involved in N key moments, including an off-ball run that helped create room
   for a forward pass." → **Play recap** (1.5 s title slate, then the replay with the overlay text) → **Download overlay
   JSON** saves `recap-<match_id>-blue-09-fan-en.json`.

```bash
curl -s -X POST localhost:8000/api/matches/<match_id>/recap -H 'content-type: application/json' \
  -d '{"mode":"analyst","language":"hi","pinned_player_id":"blue-09"}' | jq '.items[] | {rank,moment_id,pinned_player_involvement}'
```

## Catalog review tools

```bash
cd backend
uv run tactistream-catalog lint                 # parity, placeholders, digits, glossary consistency
uv run tactistream-catalog preview --language hi --scenario space_creation --seed 42
```

## Tests

```bash
cd backend && uv run pytest tests/unit/test_variant_property.py tests/unit/test_consistency.py \
  tests/unit/test_ranking_pinned.py tests/unit -k recap tests/integration/test_ws_prefs.py tests/integration/test_recap_api.py
cd frontend && npm test -- prefs i18n PlayerFocus Timeline.ranking RecapSequencer RecapPanel modes
cd frontend && npx playwright test personalize recap
```
