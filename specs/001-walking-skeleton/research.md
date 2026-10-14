# Research & Decisions: 001 Walking Skeleton

Each decision lists what was chosen, why, and what was rejected. Items marked **Record on day one** are
filled in by task T051 with values observed from the real Azure environment — they are measurements,
not open design questions.

## R1. Backend runtime and packaging

- **Decision**: Python 3.12 (`.python-version`), uv project in `backend/` with committed `uv.lock`; console scripts
  `tactistream-api`, `tactistream-sim`, `tactistream-smoke`, `tactistream-eval`.
- **Rationale**: Azure SDKs, Agent Framework and NumPy all support 3.12; uv gives reproducible, fast installs in CI and Docker.
- **Alternatives rejected**: Python 3.14 (container image currently installed locally, but SDK wheel coverage is a risk); Poetry (slower, no benefit).

## R2. API and live transport to the browser

- **Decision**: FastAPI + Uvicorn, one process; WebSocket at `/ws/matches/{match_id}`; JSON text frames; per-match monotonic `seq`.
- **Rationale**: Container Apps supports WebSocket ingress; one replica keeps match ownership trivial (constitution VII).
- **Alternatives rejected**: SignalR Service (extra service, not needed for 10 viewers); SSE (no client → server acks for latency).

## R3. Contract bindings

- **Decision**: JSON Schemas in `/contracts/schemas` are canonical. Backend Pydantic v2 models are hand-written in
  `tactistream.contracts` with `extra="forbid"`; contract tests validate every example against the schema *and* round-trip it
  through the model (`model_validate` → `model_dump(mode="json", exclude_none=True)` equals input). Frontend types are generated with
  `json-schema-to-typescript` into `frontend/src/contracts/generated.ts`; CI regenerates and fails on diff.
- **Rationale**: Readable domain types in Python with discriminated unions; zero-effort, drift-proof TS types.
- **Alternatives rejected**: `datamodel-code-generator` for Python (awkward names for `$defs`, poor ergonomics in domain code).

## R4. Frontend stack

- **Decision**: Vite + React 19 + TypeScript strict, Zustand store, CSS modules with design tokens, Vitest + Testing Library,
  Playwright for e2e. three.js via `@react-three/fiber` + `@react-three/drei` is added in 005, not now.
- **Rationale**: Fast dev loop; R3F keeps the 3D pitch declarative and testable.
- **Alternatives rejected**: Next.js (SSR unnecessary; single container serves static assets from FastAPI).

## R5. Agent runtime and model access

- **Decision**: Microsoft Agent Framework for Python (`agent-framework` package) with a chat client bound to the Microsoft Foundry
  project endpoint and model deployment, authenticated with `DefaultAzureCredential`. All model use goes through the
  `ModelClient` protocol in `tactistream.agents.model_client` so tests use `ScriptedModelClient`.
- **Structured output**: request JSON conforming to the relevant `claim.schema.json` `$defs` entry; validate on receipt; invalid JSON counts as a model error.
- **Fallback if Agent Framework blocks progress for > 2 h**: implement `FoundryModelClient` with the `openai` SDK against the Foundry
  OpenAI-compatible endpoint behind the same protocol and remove the Agent Framework claim from docs (constitution VI).
- **Packages pinned** (001-B4): `agent-framework-core==1.21.0` + `agent-framework-foundry==1.14.1` (the selective install the
  `agent-framework` 1.21.0 README documents; the meta-package pulls ~30 connectors). Chat client:
  `agent_framework.foundry.FoundryChatClient(project_endpoint=…, model=<deployment>, credential=azure.identity.aio.DefaultAzureCredential())`,
  called with `get_response([Message(...)])` → `ChatResponse` (`.text`, `.model`, `.usage_details`). It ignores `FOUNDRY_MODEL`
  because the deployment is passed explicitly from `FOUNDRY_MODEL_DEPLOYMENT`. Fallback not needed.
- **Record on day one** (T051): PENDING-LIVE: run `uv run tactistream-smoke foundry`. Model deployment name: `____`;
  model + version: `____`; region: `____`; smoke latency (ms): `____`; tokens in/out: `____`.

## R6. Azure authentication

- **Decision**: `DefaultAzureCredential` everywhere (local `az login`, user-assigned managed identity in Container Apps, OIDC in GitHub Actions). No keys or connection strings in env except the Application Insights connection string (not a secret credential).
- **Alternatives rejected**: SAS keys (secret handling burden, constitution security rule).

## R7. Event transport

- **Decision**: `azure-eventhub` async client. One hub `tactistream-feed`, 2 partitions, partition key = `match_id`, consumer groups
  `live-state` and `fabric`. Live-state consumer starts at `@latest` on boot and relies on its own state checkpoints (003) for recovery,
  so no Event Hubs checkpoint store is required for the MVP.
- **Local**: `InMemoryBus` with per-consumer-group asyncio queues, same ordering guarantee (per match) and at-least-once semantics.
- **Clients** (001-B4): `azure-eventhub==5.15.1` (`azure.eventhub.aio.EventHubProducerClient.send_event(…, partition_key=match_id)`,
  `EventHubConsumerClient.receive(on_event, starting_position=…)`), `azure-identity==1.26.0` async `DefaultAzureCredential`.
  Because `@latest` is resolved when the receive link opens, the app and the smoke start each consumer at an enqueued time of
  subscribe time minus 5 s (`enqueued_since_subscribe()`); otherwise the session's first metadata envelope, published right after
  subscribe, can be missed. Duplicates from that window are deduped by ingest.
- **Record on day one** (T051): PENDING-LIVE: run `uv run tactistream-smoke eventhubs`. Namespace: `____`; SKU: `____`;
  round-trip ms: `____`.

## R8. Deterministic narrative path

- **Decision**: All user-facing narrative is rendered from catalog templates (`narrative/catalog/{en,hi}.json`) with typed slots.
  Free-form model prose is never shown. The skeleton uses `fact.forward_pass` and `title.forward_pass` only.
- **Rationale**: Guarantees number/identity preservation across languages (build plan: "Keep the Producer within approved claim templates").

## R9. Output checks (skeleton subset)

- **Decision**: `agents/checks.py::check_packet(packet, evidence)` extracts all numbers (regex on Western digits with optional decimal),
  player display names and evidence IDs from `title` + `body`, and asserts each appears in the resolved evidence (metric values rounded
  to the template's precision, player names from metadata). Failure prevents release.

## R10. Latency measurement

- **Decision**: Browser sends `display_ack {target_kind, target_id, server_seq}` on first paint of a card or event row (via
  `requestAnimationFrame` after commit). Server computes `ack_received_ms − server_receipt_ms`. This includes the return trip, so it is an
  **upper bound** on receipt-to-display; documented as such in `docs/metrics.md` (008).

## R11. Observability

- **Decision**: `azure-monitor-opentelemetry` `configure_azure_monitor()` when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set; otherwise
  console exporter in dev and no-op in tests. Custom histograms: `tactistream.fast_overlay_latency_ms`, `tactistream.narrative_latency_ms`.

## R12. Tooling

- **Decision**: ruff (lint + format), mypy `--strict` on `backend/src`, pytest + pytest-asyncio + httpx; ESLint (typescript-eslint strict) + Prettier;
  Makefile targets `dev`, `test`, `lint`, `contracts`, `smoke`.

## R13. Container and hosting

- **Decision**: One multi-stage Dockerfile: Node 22 builds the frontend → Python 3.12-slim runtime with uv-installed backend; FastAPI serves
  `frontend/dist` at `/`. Deployed to Azure Container Apps with `minReplicas = maxReplicas = 1` (feature 007).
