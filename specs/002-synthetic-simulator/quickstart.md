# Quickstart: 002 Synthetic Simulator

## Generate the hero sequence

```bash
cd backend
uv run tactistream-sim list
uv run tactistream-sim generate --scenario space_creation --seed 42 --variant A --split dev --out ../data/generated/hero
uv run tactistream-sim generate --scenario space_creation --seed 42 --variant A --split dev --out /tmp/hero2
sha256sum ../data/generated/hero/feed.jsonl /tmp/hero2/feed.jsonl     # identical
```

Expected: `match_id=demo-blue-amber-001 events=9 …`; the hash equals `backend/tests/golden/simulator_hashes.json["space_creation/42/A"]`.

## Other scenarios

```bash
uv run tactistream-sim generate --scenario demo_match --seed 42 --out ../data/generated/demo           # ~4.5 min, demo-blue-amber-002
uv run tactistream-sim generate --scenario tracking_gap --seed 42 --out ../data/generated/gap
uv run tactistream-sim generate --scenario press_turnover --seed 10000 --variant D --split eval --out ../data/generated/eval-pt-d
uv run tactistream-sim generate --scenario press_turnover --seed 10000 --split dev --out /tmp/x           # exit 2: reserved for split=eval
```

## Replay in the app

```bash
make dev
```

Open http://localhost:5173. Session controls: Scenario = **Demo match**, Seed = 42 → **Start**. Try **2×**, **Pause**,
**Reset**, **New seed**. Choose **Skeleton fixture** to see the 001 card.

API-only:

```bash
curl -s localhost:8000/api/scenarios | jq '.[].scenario'
curl -s -XPOST localhost:8000/api/sessions -H 'content-type: application/json' -d '{"scenario":"space_creation","seed":42}'
curl -s -XPOST localhost:8000/api/matches/demo-blue-amber-001/control -H 'content-type: application/json' -d '{"action":"speed","speed":2.0}'
curl -s -XPOST localhost:8000/api/matches/demo-blue-amber-001/control -H 'content-type: application/json' -d '{"action":"seek","to_ms":8000}'
```

## Tests

```bash
cd backend && uv run pytest tests/unit/simulator tests/unit/test_replayer_speed_seek.py tests/integration/test_sim_sessions.py tests/integration/test_sim_seek.py
uv run pytest -m slow tests/unit/simulator/test_library_matrix.py      # 4,200 outputs
cd ../frontend && npm test -- SessionControls && npx playwright test simulator.spec.ts
```
