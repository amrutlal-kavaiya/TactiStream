# Implementation Plan: Walking Skeleton

**Branch**: `001-walking-skeleton` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-walking-skeleton/spec.md`

## Summary

Stand up the thinnest complete path: a hand-authored synthetic fixture is replayed onto a `FeedBus`, ingested into
`MatchState`, a `forward_progress` metric is computed for the pass, a deterministic `fact.forward_pass` template renders
four variants, output checks verify numbers/names/IDs, and the bundle is pushed over WebSocket to a React shell that shows
one card and resolves evidence through a REST endpoint. In parallel, two smoke CLIs prove Foundry and Event Hubs access.
CI enforces contract-first development from the first commit.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend), Node 22 (build)

**Primary Dependencies**: FastAPI, Uvicorn, Pydantic v2, jsonschema + referencing, azure-eventhub, azure-identity,
agent-framework (exact version recorded in research R5), azure-monitor-opentelemetry; React 19, Vite, Zustand,
json-schema-to-typescript

**Storage**: In-memory session state; fixture file `data/fixtures/skeleton.jsonl`

**Testing**: pytest, pytest-asyncio, httpx (ASGI transport); Vitest + Testing Library; Playwright (chromium)

**Target Platform**: Linux container (Azure Container Apps), modern Chromium/Edge/Firefox

**Project Type**: Web application (backend + frontend in one container)

**Performance Goals**: fast overlay p95 ≤ 2 s (receipt → display ack) — measured, not assumed

**Constraints**: no model call on the fast path; no secrets in repo; deterministic fixture playback with injectable clock

**Scale/Scope**: 1 match, ≤ 10 viewers, 4 events, 60 frames

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Evidence before narrative | PASS | Card text rendered from template with metric/event slots; `check_packet` blocks unmatched numbers/names/IDs |
| II Provenance | PASS | `source.kind = synthetic` on every record; persistent badge; fictional teams |
| III Deterministic core | PASS | No agents yet; fact template is the future fallback path; fast path has no model call |
| IV Contract-first | PASS | Schemas + examples exist; contract tests + TS drift job are the first tasks |
| V Test-first | PASS | Every task pair below is test → implementation |
| VI Measure | PASS | `display_ack` latency recorded; smoke prints real latency; values recorded in research.md |
| VII Scope | PASS | Single replica, in-memory state, no 3D yet |

Post-design re-check: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/001-walking-skeleton/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
└── contracts/
    ├── rest-api.md          # full REST surface incl. later features
    └── ws-protocol.md       # WebSocket lifecycle and message table
```

### Source Code (repository root)

```text
Makefile                               install, dev, test, e2e, lint, contracts, smoke
.env.example
.github/workflows/ci.yml
data/fixtures/skeleton.jsonl
contracts/                             (exists) schemas + examples
backend/
├── pyproject.toml · uv.lock · .python-version
├── src/tactistream/
│   ├── __init__.py                    __version__ = "0.1.0"
│   ├── settings.py                    Settings (pydantic-settings) incl. bus/agents selection
│   ├── contracts/{common,match,event,tracking,metric,moment,claim,insight,recap,envelope,ws}.py
│   ├── contracts/schema_registry.py   load /contracts/schemas, validate(name, obj)
│   ├── transport/{bus,memory_bus,eventhubs_bus,replayer,clock,fixtures}.py
│   ├── state/match_state.py
│   ├── metrics/forward_progress.py
│   ├── narrative/{render.py,factual.py,catalog/en.json,catalog/hi.json}
│   ├── agents/checks.py               check_packet (skeleton subset)
│   ├── telemetry/{otel.py,latency.py}
│   ├── smoke/{cli.py,foundry.py,eventhubs.py}
│   └── api/{app.py,session.py,ws_hub.py,evidence.py,routes_sessions.py,routes_evidence.py,ws.py}
└── tests/
    ├── contract/test_examples.py
    ├── unit/{test_memory_bus,test_replayer,test_match_state,test_forward_progress,test_render,test_checks,test_factual,test_ws_hub}.py
    ├── integration/{test_session_flow,test_ws_resume,test_evidence_api}.py
    └── live/{test_foundry_smoke,test_eventhubs_smoke}.py      (@pytest.mark.live)
frontend/
├── package.json · vite.config.ts · tsconfig.json · eslint.config.js · playwright.config.ts
├── src/
│   ├── main.tsx · App.tsx · styles/tokens.css
│   ├── contracts/generated.ts         (generated; committed)
│   ├── api/{client.ts,socket.ts}
│   ├── store/matchStore.ts
│   ├── i18n/{en.ts,hi.ts,useT.ts}     UI chrome strings only (narrative comes from server)
│   └── components/{TopBar,SourceBadge,EventList,InsightCard,EvidenceDrawer,PlaybackControls}.tsx
└── tests/
    ├── unit/{matchStore.test.ts,InsightCard.test.tsx,EvidenceDrawer.test.tsx,socket.test.ts}
    └── e2e/skeleton.spec.ts
```

**Structure Decision**: Web application layout (`backend/` + `frontend/`) with shared root `contracts/`, matching the
naming registry in `specs/README.md`. `narrative/factual.py` is the deterministic fact path that 004 reuses as its fallback.

## Key Design Notes

- **Clock injection**: `transport/clock.py` defines `Clock` protocol (`now_ms()`, `sleep_ms()`), `MonotonicClock`, and `FakeClock`
  (manual `advance(ms)`), so replay timing is tested without real sleeps.
- **Session wiring** (`api/session.py`): `MatchSession.start()` creates the replayer task and a consumer task
  `async for env in bus.subscribe("live-state")` → `state.apply` → `on_delta` (metric, fact bundle, WS fan-out).
- **WS hub** keeps the per-match message log (`list[ServerMessage]`) so `resume` can compute the snapshot; seq is assigned in `WsHub.broadcast`.
- **Evidence index**: dict id → (`kind`, record, `session_clock_ms`) populated on apply/compute; `resolve(id, as_of_ms)`.
- **Frontend dev proxy**: Vite proxies `/api` and `/ws` to `http://localhost:8000`.

## Complexity Tracking

No violations.
