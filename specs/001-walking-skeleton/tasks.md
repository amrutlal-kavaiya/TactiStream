---
description: "Task list for 001 walking skeleton"
---

# Tasks: Walking Skeleton

**Input**: `specs/001-walking-skeleton/` (spec, plan, research, data-model, contracts, quickstart)

**Tests**: REQUIRED (constitution V). Each implementation task is preceded by a test task that must fail first.

**Format**: `[ID] [P?] [Story] Description` — `[P]` = parallelizable (different files, no unmet dependency).

## Phase 1: Setup

- [x] T001 Create root scaffolding: `Makefile` (targets `install`, `dev`, `test`, `e2e`, `lint`, `contracts`, `smoke`), `.gitignore` (Python, Node, `.env`, `frontend/dist`, `.venv`, `test-results`), `.env.example` with names only: `TACTISTREAM_BUS=memory`, `TACTISTREAM_AGENTS=off`, `EVENTHUBS_FULLY_QUALIFIED_NAMESPACE=`, `EVENTHUBS_NAME=tactistream-feed`, `EVENTHUBS_CONSUMER_GROUP=live-state`, `FOUNDRY_PROJECT_ENDPOINT=`, `FOUNDRY_MODEL_DEPLOYMENT=`, `APPLICATIONINSIGHTS_CONNECTION_STRING=`, `AZURE_STORAGE_ACCOUNT_URL=`, `FABRIC_KUSTO_QUERY_URI=`, `FABRIC_KUSTO_DATABASE=`, `TACTISTREAM_NARRATIVE_DEADLINE_MS=8000`
- [x] T002 Initialize backend uv project `backend/pyproject.toml` (package `tactistream`, src layout, Python `>=3.12,<3.13`, `.python-version` = 3.12) with deps fastapi, uvicorn[standard], pydantic>=2.9, pydantic-settings, jsonschema, referencing, numpy, azure-identity, azure-eventhub, azure-monitor-opentelemetry, opentelemetry-sdk, typer; dev deps pytest, pytest-asyncio, httpx, ruff, mypy; console scripts `tactistream-api = tactistream.api.app:main`, `tactistream-smoke = tactistream.smoke.cli:app`; ruff (line 110, select E,F,I,B,UP,N,SIM,RUF) and mypy strict config; pytest config `asyncio_mode=auto`, marker `live` excluded by default (`-m "not live"`); commit `uv.lock`
- [x] T003 [P] Scaffold frontend with Vite React-TS in `frontend/` (React 19, TS strict, `noUncheckedIndexedAccess`), add zustand, vitest, @testing-library/react, jsdom, @playwright/test, eslint (typescript-eslint strict), prettier, json-schema-to-typescript; `vite.config.ts` proxies `/api` → `http://localhost:8000` and `/ws` (ws: true); npm scripts `dev`, `build`, `test`, `lint`, `typecheck`, `e2e`, `contracts:gen`
- [x] T004 [P] Create `.github/workflows/ci.yml` with jobs `backend` (uv sync, ruff check, ruff format --check, mypy, pytest) and `frontend` (npm ci, lint, typecheck, vitest, build); extended in T052

**Checkpoint**: `make install && make lint && make test` run (empty test suites pass).

---

## Phase 2: Foundational (blocks all stories)

### Contracts

- [x] T005 Write failing contract test `backend/tests/contract/test_examples.py`: for each `(example file, schema ref, model)` pair in a table (`match_metadata.json`→`MatchMetadata`, `event.json`→`MatchEvent`, `tracking_frame.json`→`TrackingFrame`, `metric_result.json`→`MetricResult`, `candidate_moment.json`→`CandidateMoment`, `analyst_output.json`→`AnalystOutput`, `insight_packet.json`→`InsightPacket`, `recap.json`→`Recap`, `feed_envelope_event.json`→`FeedEnvelope`) assert (a) schema validation passes via `schema_registry.validate`, (b) `Model.model_validate(obj).model_dump(mode="json", exclude_none=True) == obj`; plus negative tests: invisible player with `pos_m` rejected by both schema and model; `MetricResult` with `status="unavailable"` and a `value` rejected by both
- [x] T006 Implement `backend/src/tactistream/contracts/schema_registry.py`: locate repo `contracts/schemas` (env `TACTISTREAM_CONTRACTS_DIR` override, default `Path(__file__).parents[4] / "contracts/schemas"`), build a `referencing.Registry` keyed by `$id` and file name, `validate(schema: str, obj: object) -> None` raising `ContractError` with the JSON path
- [x] T007 [P] Implement `backend/src/tactistream/contracts/common.py` and `match.py` per data-model.md (frozen, `extra="forbid"`, ID aliases with regex patterns identical to `common.schema.json`)
- [x] T008 [P] Implement `backend/src/tactistream/contracts/event.py` and `tracking.py` incl. model validators: pass requires `end_m`+`duration_ms`; complete pass requires `recipient_id`; visible ⇔ `pos_m`
- [x] T009 [P] Implement `backend/src/tactistream/contracts/metric.py`, `moment.py`, `claim.py` incl. validator ok ⇔ value+unit; `AnalystOutput.claims` max 2
- [x] T010 [P] Implement `backend/src/tactistream/contracts/insight.py`, `recap.py`, `envelope.py` (payload parsed into typed model by `kind`; `insight`/`agent_trace`/`latency` kept typed where defined), `ws.py` (`ServerMessage`, `Snapshot`, `NarrativeStatus`, `InsightRevoked`, `ClientMessage` discriminated union on `type`); export all from `contracts/__init__.py`. Run T005 → green
- [x] T011 Add `frontend/scripts/gen-contracts.mjs` compiling every schema in `../contracts/schemas` into one `frontend/src/contracts/generated.ts` (banner "GENERATED — do not edit"), wire `npm run contracts:gen` and `make contracts` (backend contract tests + generation + `git diff --exit-code frontend/src/contracts/generated.ts`); commit the generated file

### Runtime primitives

- [x] T012 [P] Write failing `backend/tests/unit/test_clock.py`: `FakeClock.now_ms()` starts at given value; `await sleep_ms(500)` completes only after `advance(500)`; concurrent sleepers wake in deadline order
- [x] T013 [P] Implement `backend/src/tactistream/transport/clock.py` (`Clock` protocol, `MonotonicClock`, `FakeClock`)
- [x] T014 [P] Write failing `backend/tests/unit/test_memory_bus.py`: two consumer groups each receive all envelopes in publish order per match; a group subscribing late receives only later envelopes; a duplicate publish is delivered twice (at-least-once — dedupe is ingest's job)
- [x] T015 [P] Implement `backend/src/tactistream/transport/bus.py` (`FeedBus` protocol) and `memory_bus.py` (`InMemoryBus` with per-group `asyncio.Queue`s; `close()` ends iterators)
- [x] T016 [P] Implement `backend/src/tactistream/settings.py` (`Settings` via pydantic-settings reading the `.env.example` names; `bus: Literal["memory","eventhubs"]`, `agents: Literal["off","scripted","foundry"]`) with `backend/tests/unit/test_settings.py` covering defaults and env override
- [x] T017 [P] Implement `backend/src/tactistream/telemetry/otel.py` (`setup_telemetry(settings)`: Azure Monitor if connection string set, else no-op) and `telemetry/latency.py` (`LatencyRecorder.record(kind: Literal["fast_overlay","narrative"], ms: int, attrs)` storing samples in memory + OTel histogram; `percentile(kind, p)`), with `backend/tests/unit/test_latency.py` (p95 of 1..100 == 95)

**Checkpoint**: contracts green, bus + clock tested.

---

## Phase 3: User Story 1 — Verified card for a synthetic pass (P1) 🎯 MVP

**Goal**: fixture → bus → state → metric → fact card → WS → UI → evidence drawer.

**Independent Test**: `make e2e` (Playwright `skeleton.spec.ts`) passes with in-memory bus.

### Backend

- [x] T018 [US1] Author `data/fixtures/skeleton.jsonl` exactly as in data-model.md "Fixture" (metadata from `contracts/examples/match_metadata.json`; 60 frames with all 22 players visible, ball following carrier/pass path; events evt-0040..0043) and add `backend/tests/unit/test_fixture.py` validating every line against `feed_envelope.schema.json`, frame indices 0..59 contiguous, event sequences 40..43 contiguous
- [x] T019 [US1] Write failing `backend/tests/unit/test_replayer.py` with `FakeClock` and `InMemoryBus`: at speed 1.0 the pass envelope is published when clock reaches 3000 ms (not before); `pause()` stops publishing while clock advances; `play()` resumes from paused session time; `reset()` sets `session_clock_ms` to 0 and republishes metadata first; state becomes `ended` after the last record
- [x] T020 [US1] Implement `backend/src/tactistream/transport/replayer.py` (`FeedReplayer`, `PlaybackState`) and `transport/fixtures.py` (`load_fixture(path) -> list[FeedEnvelope]`, sorted metadata-first then by `session_clock_ms`, events before frames at equal time)
- [x] T021 [US1] Write failing `backend/tests/unit/test_match_state.py`: applying metadata then events increments `state_version` per accepted record; duplicate (`kind`,`record_id`) returns `StateDelta(duplicate=True)` and does not change version; events kept sorted by `sequence` even if applied 42 before 41; `server_receipt_ms` preserved on the stored record; final-state hash (sha256 of canonical JSON of metadata+events+latest frame) identical for in-order vs shuffled-with-duplicates input (SC-004)
- [x] T022 [US1] Implement `backend/src/tactistream/state/match_state.py` (`MatchState`, `StateDelta`, `state_hash()`)
- [x] T023 [P] [US1] Write failing `backend/tests/unit/test_forward_progress.py`: evt-0042 with Blue attacking +1 → `MetricResult(kind="forward_progress", metric_id="metric-forward_progress-0042", value=13.1, unit="m", definition_version="forward_progress.v1", inputs.event_ids=["evt-0042"])`; same pass with attack direction −1 → −13.1; pass with `outcome=None` → still computed (it is geometry of the attempt); non-pass event → `ValueError`
- [x] T024 [P] [US1] Implement `backend/src/tactistream/metrics/forward_progress.py` (`compute_forward_progress(event, metadata, state_version) -> MetricResult`, value rounded to 1 decimal, window = event time .. event time + duration)
- [x] T025 [P] [US1] Write failing `backend/tests/unit/test_render.py`: `render_claim("fact.forward_pass", slots, "fan", "en")` → "Blue 8 played a forward pass to Blue 11 (13.1 m forward)."; analyst/en adds "Progress along attack axis: 13.1 m (evt-0042)."; fan/hi contains "ब्लू 8", "ब्लू 11" and "13.1"; missing slot → `TemplateError`; unknown template → `TemplateError`; all four variants contain identical numbers
- [x] T026 [P] [US1] Implement `backend/src/tactistream/narrative/render.py` (`render_claim`, `render_title`, `RenderedText(text, numbers: list[str], player_ids: list[str])`, slot resolution from metadata display names and metric values with per-template precision) and catalogs `narrative/catalog/en.json`, `narrative/catalog/hi.json` containing `title.forward_pass`, `fact.forward_pass` (fan + analyst variants), `status.insufficient_tracking`, `label.synthetic`, `label.interpretation`
- [x] T027 [P] [US1] Write failing `backend/tests/unit/test_checks.py`: valid packet passes; body number "14.0" not in evidence → `CheckFailure(code="unsupported_number")`; player name "Blue 7" absent from evidence subjects → `unsupported_player`; evidence ID not in index → `unknown_evidence`; `show_until_ms <= show_from_ms` → `invalid_timing`; packet already expired at `now_ms` → `expired`
- [x] T028 [P] [US1] Implement `backend/src/tactistream/agents/checks.py` (`check_packet(packet, evidence: EvidenceIndex, metadata, now_ms) -> list[CheckFailure]`)
- [ ] T029 [US1] Write failing `backend/tests/unit/test_factual.py` then implement `backend/src/tactistream/narrative/factual.py` (`build_fact_bundle(event, metric, metadata, state_version, trace_id, now_session_ms) -> InsightBundle` producing 4 variants, `insight_id = "ins-0042"`, `moment_id = "mom-0042"`, `claim_status="verified_fact"`, labels `["synthetic"]`, `show_from_ms = event end`, `show_until_ms = +6000`, `expires_at_session_ms = +30000`, `panel="lower_third"`, `priority=3`, no annotations)
- [x] T030 [US1] Implement `backend/src/tactistream/api/evidence.py` (`EvidenceIndex.add(kind, record, session_clock_ms)`, `resolve(id, as_of_ms)`) with `backend/tests/unit/test_evidence_index.py` (future record not resolvable before its time)
- [ ] T031 [US1] Write failing `backend/tests/unit/test_ws_hub.py`: `broadcast` assigns seq 1,2,3…; two subscribers receive same seq order; `snapshot_for(match_state)` returns head seq; slow subscriber with full queue (maxsize 1000) is disconnected, not blocking others
- [ ] T032 [US1] Implement `backend/src/tactistream/api/ws_hub.py` (`WsHub`)
- [ ] T033 [US1] Implement `backend/src/tactistream/api/session.py` (`MatchSession`, `SessionRegistry`): starts replayer + live-state consumer; on each accepted delta: broadcast `event`/`frame`; for completed passes compute metric → index → `build_fact_bundle` → `check_packet` for each variant → broadcast `metric` + `insight`, or `narrative_status{stage:"fallback", fallback_reason:"output_check_failed"}`
- [ ] T034 [US1] Write failing `backend/tests/integration/test_session_flow.py` (httpx ASGI + FakeClock): POST `/api/sessions {"scenario":"skeleton"}` → 200 with `match_id`; WS connect receives `snapshot`; control `play`; advance clock 4000 ms; receive `event` ×3 (kickoff, carry, pass), `metric`, `insight` whose `variants` length 4 and fan/en body equals the expected sentence
- [ ] T035 [US1] Implement `backend/src/tactistream/api/app.py` (`create_app(settings, clock=None)`, `main()`), `routes_sessions.py` (`POST /api/sessions`, `POST /api/matches/{id}/control`), `routes_evidence.py`, `ws.py` (`/ws/matches/{match_id}`; handles `resume` and `display_ack` → `LatencyRecorder.record("fast_overlay", ...)`), `GET /healthz`; static mount of `frontend/dist` when present. Run T034 → green
- [ ] T036 [P] [US1] Write failing `backend/tests/integration/test_ws_resume.py`: client disconnects after seq K, reconnects with `resume{last_seq:K}` → receives snapshot whose `events` contain each event exactly once and later live messages have `seq > snapshot.seq`
- [ ] T037 [P] [US1] Write failing `backend/tests/integration/test_evidence_api.py`: `evt-0042` → 200 kind `event`; `metric-forward_progress-0042` → 200 kind `metric`; `evt-9999` → 404 `evidence_not_found`; `evt-0043` before its session time → 404
- [ ] T038 [US1] Fix/complete implementation until T036–T037 pass; add duplicate+swap replay test to `test_session_flow.py` (bus publishes each envelope twice with adjacent swaps) asserting exactly one `insight` message (SC-004)

### Frontend

- [ ] T039 [P] [US1] Write failing `frontend/tests/unit/matchStore.test.ts`: `applySnapshot` replaces state; `applyMessage(event)` ignores already-known `event_id`; `applyMessage(insight)` sets `activeInsight` only if priority ≥ current or current expired; `variantFor(prefs)` returns matching mode/language packet
- [ ] T040 [P] [US1] Implement `frontend/src/store/matchStore.ts` (Zustand: metadata, events, latestFrame, insights by id, activeInsightId, playback, lastSeq, prefs {mode:"fan", language:"en"})
- [ ] T041 [P] [US1] Write failing `frontend/tests/unit/socket.test.ts` with a mock WebSocket: sends `resume` with `lastSeq` on reconnect; backoff 500 → 1000 → 2000 ms capped at 8000; reconnects after 25 s without messages; sends `display_ack` once per target
- [ ] T042 [P] [US1] Implement `frontend/src/api/socket.ts` (`MatchSocket`) and `frontend/src/api/client.ts` (`createSession`, `control`, `getEvidence`)
- [ ] T043 [US1] Write failing `frontend/tests/unit/InsightCard.test.tsx` and `EvidenceDrawer.test.tsx`: card renders title/body, Synthetic label, evidence chips as buttons; activating chip (click or Enter) calls `onOpenEvidence(id)`; drawer shows loading, then key fields (type, player, start/end, clocks, source kind), and "Evidence unavailable" on 404; drawer is a labelled dialog that returns focus on close
- [ ] T044 [US1] Implement `frontend/src/components/{TopBar,SourceBadge,PlaybackControls,EventList,InsightCard,EvidenceDrawer}.tsx`, `src/App.tsx` (Start demo match → createSession → connect socket), `src/styles/tokens.css` (dark slate surface, Blue `#3B82F6`, Amber `#F59E0B`, text contrast ≥ 4.5:1), `src/i18n/{en,hi,useT}.ts` for chrome strings; InsightCard calls `display_ack` after first paint (`requestAnimationFrame`)
- [ ] T045 [US1] Write `frontend/tests/e2e/skeleton.spec.ts` + `playwright.config.ts` (webServer: build frontend, run `uv run tactistream-api` serving dist on :8000): click Start → expect Synthetic badge → expect card text "Blue 8 played a forward pass to Blue 11 (13.1 m forward)." within 6 s → click `evt-0042` → drawer contains "pass" and "blue-08"; then Pause and Reset → card hidden. Run 5× (`--repeat-each=5`) for SC-001

**Checkpoint**: US1 independently demonstrable locally.

---

## Phase 4: User Story 2 — Azure smoke on day one (P1)

**Independent Test**: both smoke commands exit 0 against real Azure; values recorded.

- [ ] T046 [P] [US2] Write failing `backend/tests/unit/test_smoke_cli.py`: with required env vars unset, `tactistream-smoke foundry` exits 2 and prints "Missing FOUNDRY_PROJECT_ENDPOINT"; same for `eventhubs` and `EVENTHUBS_FULLY_QUALIFIED_NAMESPACE`; no traceback in output
- [ ] T047 [US2] Add `agent-framework` (and its Azure/Foundry chat client extra as documented by the package) to `backend/pyproject.toml`, pin the resolved exact version; implement `backend/src/tactistream/smoke/foundry.py`: create the Foundry-backed chat client with `DefaultAzureCredential`, ask for `{"ok": true, "echo": "<random token>"}` as JSON, validate shape and echo, print deployment, region (from endpoint/config), latency ms, tokens; implement `smoke/cli.py` (typer app with `foundry`, `eventhubs` commands). If Agent Framework blocks > 2 h, apply research R5 fallback
- [ ] T048 [US2] Write failing `backend/tests/unit/test_eventhubs_bus.py` using a fake producer/consumer client object injected into `EventHubsBus`: `publish` sends JSON body with `partition_key=match_id`; `subscribe("live-state")` yields parsed `FeedEnvelope`s and stamps nothing (stamping is ingest's job)
- [ ] T049 [US2] Implement `backend/src/tactistream/transport/eventhubs_bus.py` (`EventHubsBus(namespace, hub, credential, client_factory=None)`; async producer with `partition_key`; async consumer per consumer group starting at `"@latest"`, pushing into an asyncio queue) and `smoke/eventhubs.py` (publish one envelope with random `record_id`, read it back via `live-state` within 30 s, print round-trip ms)
- [ ] T050 [US2] Add `backend/tests/live/test_foundry_smoke.py` and `test_eventhubs_smoke.py` (`@pytest.mark.live`) invoking the smoke functions; run them once with real credentials (`uv run pytest -m live`)
- [ ] T051 [US2] Record observed values in `specs/001-walking-skeleton/research.md` R5/R7 blanks (version, client class, deployment, model, region, latency, tokens, namespace, SKU, round-trip) and wire `Settings.bus == "eventhubs"` to construct `EventHubsBus` in `create_app`; verify `TACTISTREAM_BUS=eventhubs make dev` shows the card

**Checkpoint**: Day-one exit condition met (event reaches browser + real Foundry call).

---

## Phase 5: User Story 3 — Contract-first CI (P2)

- [ ] T052 [US3] Extend `.github/workflows/ci.yml`: job `contracts` (backend contract tests + `npm run contracts:gen` + `git diff --exit-code`), job `e2e` (install Playwright chromium, build frontend, run `npm run e2e`), cache uv and npm; all jobs on push and PR to `main`
- [ ] T053 [US3] On a throwaway branch rename `MatchEvent.player_id` → `actor_id`; confirm CI fails in `contracts`; delete branch; note the run URL in the PR description (SC-005)

---

## Phase 6: Polish

- [ ] T054 [P] Update `README.md`: one-paragraph pitch, Synthetic-data disclaimer, quickstart (`make install && make dev`), test commands, link to `specs/README.md` and constitution
- [ ] T055 [P] Run quickstart.md on a fresh clone (new codespace or `git clone` to /tmp) and fix any gaps
- [ ] T056 Update `specs/README.md` feature table: mark 001 exit condition met with date

---

## Dependencies & Execution Order

- Setup (T001–T004) → Foundational (T005–T017) → US1 and US2 can run in parallel → US3 → Polish.
- Within US1: T018 → T019/T020 → T021/T022 → (T023–T028 parallel) → T029 → T030 → T031/T032 → T033 → T034/T035 → T036–T038; frontend T039–T044 can start after T011 (generated types) and run parallel to backend; T045 needs both.
- US2 depends only on T002, T010, T015 — start T046–T047 first thing on day one to surface Azure access issues early.

## Parallel Example

```text
Day one, morning:   T047 (Foundry smoke)  ||  T005–T010 (contracts)  ||  T003 (frontend scaffold)
Day one, afternoon: T023–T028 (metric, render, checks)  ||  T039–T042 (store, socket)
```

## Implementation Strategy

MVP = Phase 1–3. Then US2 (if not already done in the morning), then US3. Stop and validate after each checkpoint.
