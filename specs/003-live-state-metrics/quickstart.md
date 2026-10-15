# Quickstart: 003 Live State & Metrics

## See moments live

```bash
make dev
```

Open http://localhost:5173 → Scenario **Space creation (scripted)**, seed 42 → **Start**. About 1 s after the shot (≈ 13 s
session time) the side panel lists one moment: **Space creation** (rank 1, no "Partial tracking" badge). Choose
**Missing tracking (fixture)** → the moment is **Shot** with a **Partial tracking** badge.

## Inspect metrics and snapshots

```bash
curl -s -XPOST localhost:8000/api/sessions -H 'content-type: application/json' -d '{"scenario":"space_creation","seed":42}'
curl -s -XPOST localhost:8000/api/matches/demo-blue-amber-001/control -H 'content-type: application/json' -d '{"action":"seek","to_ms":14100}'
curl -s localhost:8000/api/matches/demo-blue-amber-001/snapshot | jq '.moments'
curl -s localhost:8000/api/matches/demo-blue-amber-001/evidence/metric-channel-0005 | jq '.record | {value, components, inputs}'
curl -s 'localhost:8000/api/matches/demo-blue-amber-001/snapshot?as_of_ms=12000' | jq '.events | length'     # 6
```

## Checkpoints and restore

```bash
ls .data/artifacts/checkpoints/demo-blue-amber-001/        # 0000NNNN.json, latest 3
wc -l .data/artifacts/feed-archive/demo-blue-amber-001/*.jsonl
# stop the API (Ctrl-C) and start it again: the session is restored paused at the last checkpoint
```

## Tests

```bash
cd backend
uv run pytest tests/unit/state tests/unit/metrics tests/unit/moments
uv run pytest tests/integration/test_replay_consistency.py tests/integration/test_late_event_revision.py tests/integration/test_restore.py
uv run pytest -m slow tests/perf/test_state_perf.py         # record numbers in research.md R11
cd ../frontend && npm test -- matchStore.moments MomentList
```

Metric formulas, parameters and limitations: `docs/metrics.md`.
