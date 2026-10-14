# Quickstart: 005 Why Mode Replay

## Prerequisites

001–004 merged locally (`make install` done). No Azure needed: use the scripted agent client.

## Run the hero sequence

```bash
TACTISTREAM_AGENTS=scripted make dev      # API :8000, Vite :5173
```

1. Open http://localhost:5173 → **Start demo match** (scenario `space_creation`, seed 42). The live 3D pitch shows
   Blue (discs) and Amber (diamonds) with shirt numbers; the Synthetic badge is visible.
2. After the shot, the card "Space opened before the shot" appears (announced by screen readers).
3. Press **Why?** (or Tab to it and press Enter). Expected: the main surface switches to **Tactical replay** of the
   preceding 8–12 s; Blue 9 is ringed, the Amber defender's path is drawn as it happens, and the channel band between
   Blue 8 and Blue 11 widens with the label "1.9 m → 5.3 m" (seed-42 values from the golden file).
4. Try: Space (play/pause), drag the scrubber, 0.5×, Loop, camera presets Broadcast / Top-down / Follow runner,
   Timeline ←/→/Home/End, Escape (back to live).
5. Press **Evidence**: the drawer lists `metric-channel-0042` with definition, window, value, components, input events
   and the "Scene geometry" coordinates; the header shows "Interpretation" for the conclusion and "Verified fact" for
   records.

## Other patterns and degradation

```bash
curl -s -X POST localhost:8000/api/sessions -H 'content-type: application/json' \
  -d '{"scenario":"press_turnover","seed":42}'
curl -s localhost:8000/api/matches/<match_id>/replay/<moment_id> | jq '.scene.annotations[].kind'
```

- `press_turnover` → `pressure_ring`, `highlight`, `path`; `switch_escape` → `pressure_ring`, `highlight`, `path`.
- Missing-data fixture (see 002 quickstart for its scenario name) → `409 {"error":"insufficient_tracking", "events": [...]}`;
  the UI shows "Insufficient tracking for this explanation" plus the ordinary event card.

## Tests

```bash
cd backend && uv run pytest tests/unit/test_scene.py tests/unit/test_scene_golden.py tests/integration -k replay
cd frontend && npm test -- ReplayController annotationGeometry Players ReplayView Timeline EvidenceDrawer
cd frontend && npx playwright test why-mode why-mode-insufficient why-mode-patterns a11y
```

Regenerate the golden scene only on an intentional change: `uv run pytest tests/unit/test_scene_golden.py --update-golden`
and review the diff.

## Measure FPS (development figure)

```bash
cd frontend && node scripts/capture-fps.mjs --url http://localhost:5173 --scenario space_creation --seed 42 \
  --seconds 20 --machine-label "dev-codespace"
# → eval/results/fps/fps-<timestamp>.json ; add the numbers to specs/005-why-mode-replay/research.md R7
```

Append `?fps=1` to the URL to see the FPS overlay in a production build.
