---
description: "Task list for 007 Azure platform"
---

# Tasks: Azure Platform

**Input**: `specs/007-azure-platform/` (spec, plan, research, data-model, contracts/eventhouse-tables.md, quickstart)

**Tests**: REQUIRED (constitution V). Code tasks are preceded by a failing test. Infrastructure tasks are preceded by
compiled-template assertions (`pytest -m infra`) and verified with `az bicep build`/lint, `what-if`, and the deployed smoke.

**Format**: `[ID] [P?] [Story] Description` — `[P]` = parallelizable (different files, no unmet dependency).

**Delivery split**: Phases 1–4 = **007a (15 Oct)**; Phases 5–6 = **007b (20–21 Oct)**. T037–T040 (agent wiring) run on
17 Oct right after 004 merges.

## Phase 1: Setup

- [ ] T001 Add runtime deps `azure-storage-blob[aio]`, `azure-kusto-data[aio]` and pytest markers `infra` (needs `az` CLI), `kusto` (needs Kusto emulator) to `backend/pyproject.toml`; exclude `live`, `infra`, `kusto` from the default `pytest` addopts; update `uv.lock`
- [ ] T002 Write failing `backend/tests/unit/test_settings_platform.py`: defaults `artifact_store="local"`, `analytics_publish=False`, `history="memory"`, `history_timeout_ms=1500`, `environment="dev"`; env overrides for every variable in data-model.md "Runtime configuration"; `artifact_store="blob"` without `AZURE_STORAGE_ACCOUNT_URL` raises a validation error naming the variable; `history="eventhouse"` without `FABRIC_KUSTO_QUERY_URI` raises likewise
- [ ] T003 Extend `backend/src/tactistream/settings.py` with the fields in data-model.md and the two cross-field validators; run T002 → green
- [ ] T004 [P] Append the new variable names (no values) to `.env.example`: `TACTISTREAM_ARTIFACT_STORE`, `TACTISTREAM_ANALYTICS_PUBLISH`, `TACTISTREAM_HISTORY`, `TACTISTREAM_HISTORY_TIMEOUT_MS`, `TACTISTREAM_STATIC_DIR`, `TACTISTREAM_ENVIRONMENT`, `AZURE_CLIENT_ID`

**Checkpoint**: settings tests green; `make test` unchanged otherwise.

---

## Phase 2: Foundational (blocks US1)

- [ ] T005 Create `bicepconfig.json` (analyzers core enabled, every rule level `error`, `use-recent-api-versions` warning-as-error) and add job `infra` to `.github/workflows/ci.yml`: `az bicep install`, `az bicep build --file infra/main.bicep --stdout > /dev/null`, `uv run pytest -m infra tests/infra`
- [ ] T006 Write failing `backend/tests/infra/test_bicep_template.py`: helper compiles `infra/main.bicep` with `az bicep build --stdout` (skip with reason if `az` missing), flattens nested deployments, and asserts every property listed in plan.md "Compiled-template tests" (replicas 1/1, ingress port 8000 external `auto`, three `/healthz` probes, hub partitions 2 + retention 7, consumer groups exactly `{live-state, fabric}`, rule `fabric-listen` rights exactly `[Listen]`, containers exactly `{datasets, artifacts, checkpoints}`, `allowSharedKeyAccess false`, `allowBlobPublicAccess false`, ACR `adminUserEnabled false`, role definition GUID set equals FR-007, budget notifications at 50/80/100 actual + 100 forecast, container app tag `azd-service-name: web`)

**Checkpoint**: T006 fails because `infra/main.bicep` does not exist.

---

## Phase 3: User Story 1 — Judges open a live deployed TactiStream (P1) 🎯 007a

**Goal**: one-command provisioning, OIDC CI/CD, WebSocket-capable single replica reading Event Hubs, Blob artifacts.

**Independent Test**: `uv run tactistream-smoke deployed --base-url $APP_URL` exits 0; Playwright skeleton passes 5/5 against `BASE_URL`.

### Infrastructure

- [ ] T007 [P] [US1] Create `infra/modules/identity.bicep` (user-assigned identity; outputs `id`, `principalId`, `clientId`) and `infra/modules/monitoring.bicep` (Log Analytics PerGB2018 30 d; workspace-based App Insights; outputs `workspaceId`, `workspaceCustomerId`, `appInsightsName`, `appInsightsId`; `main.bicep` reads the connection string from the existing component and passes it to `containerapps.bicep` as a `@secure()` param, never as a plain output)
- [ ] T008 [P] [US1] Create `infra/modules/registry.bicep` (ACR Basic, `adminUserEnabled: false`; outputs `loginServer`, `id`, `name`)
- [ ] T009 [P] [US1] Create `infra/modules/eventhubs.bicep` (Standard, capacity 1, `minimumTlsVersion: '1.2'`; hub `tactistream-feed` partitionCount 2, messageRetentionInDays 7; consumer groups `live-state`, `fabric`; hub-scoped authorization rule `fabric-listen` rights `['Listen']`; outputs `namespaceFqdn`, `namespaceId`, `hubName`)
- [ ] T010 [P] [US1] Create `infra/modules/storage.bicep` (StorageV2 Standard_LRS, `allowSharedKeyAccess: false`, `allowBlobPublicAccess: false`, `minimumTlsVersion: 'TLS1_2'`; containers `datasets`, `artifacts`, `checkpoints` with `publicAccess: 'None'`; outputs `blobEndpoint`, `id`)
- [ ] T011 [P] [US1] Create `infra/modules/roles.bicep` (AcrPull on ACR; Event Hubs Data Sender + Data Receiver on the namespace; Storage Blob Data Contributor on the account; names `guid(scope, principalId, roleId)`; `principalType: 'ServicePrincipal'`) and `infra/modules/foundry-role.bicep` (existing `Microsoft.CognitiveServices/accounts` `foundryAccountName`; role param `foundryRoleDefinitionId` default `53ca6127-db72-4b80-b1b0-d745d6d5456d`)
- [ ] T012 [US1] Create `infra/modules/containerapps.bicep`: Consumption environment with Log Analytics `appLogsConfiguration`; app `tactistream` (tag `azd-service-name: web`), `activeRevisionsMode: 'Single'`, identity = UAMI, `registries: [{server: acrLoginServer, identity: uamiId}]`, secret `appinsights-connection-string`, ingress `{external: true, targetPort: 8000, transport: 'auto', allowInsecure: false}`, scale `{minReplicas: 1, maxReplicas: 1}`, container 1.0 vCPU / 2Gi with startup/liveness/readiness probes on `/healthz` (plan.md R3 periods), env vars from data-model.md (`APPLICATIONINSIGHTS_CONNECTION_STRING` via `secretRef`); image param `imageName` defaulting to `mcr.microsoft.com/k8se/quickstart:latest` when empty; outputs `fqdn`, `name`
- [ ] T013 [US1] Create `infra/modules/budget.bicep` (`Microsoft.Consumption/budgets` at RG scope, monthly, `monthlyBudget` default 100, start date first of current month, notifications 50/80/100 Actual + 100 Forecast → `alertEmail`) and `infra/main.bicep` + `infra/main.parameters.json` wiring all modules per plan.md "Bicep composition" (`foundry-role` with `scope: resourceGroup(foundryResourceGroup)`), outputs `AZURE_CONTAINER_REGISTRY_ENDPOINT`, `SERVICE_WEB_NAME`, `SERVICE_WEB_URI`, `EVENTHUBS_FULLY_QUALIFIED_NAMESPACE`, `AZURE_STORAGE_ACCOUNT_URL`, `APPINSIGHTS_NAME`, `MANAGED_IDENTITY_CLIENT_ID`; run `az bicep build` (0 warnings) and T006 → green
- [ ] T014 [P] [US1] Create root `azure.yaml` (name `tactistream`, `infra.path: infra`, service `web`: `project: .`, `language: docker`, `host: containerapp`, `docker.path: ./Dockerfile`, `docker.remoteBuild: true`)

### Container and app serving

- [ ] T015 [P] [US1] Write failing `backend/tests/unit/test_spa_fallback.py`: with a temp `static_dir` containing `index.html` and `assets/app.js`, `GET /` and `GET /evidence` and `GET /demo?seed=42` return `index.html`; `GET /assets/app.js` returns the file; `GET /api/unknown` returns 404 JSON `{"error":"not_found"}`; `GET /healthz` unaffected; when `static_dir` does not exist the app starts and `/` returns 404
- [ ] T016 [US1] Implement SPA static serving + fallback in `backend/src/tactistream/api/app.py` (`StaticFiles` under `/assets`, catch-all GET registered last, excluded prefixes `/api`, `/ws`, `/healthz`); run T015 → green
- [ ] T017 [US1] Create root `Dockerfile` and `.dockerignore` per research R6 (pinned `node:22-slim`, pinned `ghcr.io/astral-sh/uv` tag, `python:3.12-slim`, non-root uid 10001, `ENV TACTISTREAM_STATIC_DIR=/app/frontend/dist TACTISTREAM_CONTRACTS_DIR=/app/contracts/schemas PYTHONUNBUFFERED=1`, `HEALTHCHECK` omitted — probes are in Container Apps); add `make image` (`docker build -t tactistream:local .`) and `make image-smoke` (run container with `TACTISTREAM_BUS=memory` on :8000, then T019's smoke with `--allow-memory`)

### Deployed smoke

- [ ] T018 [P] [US1] Write failing `backend/tests/unit/test_smoke_deployed.py`: start `create_app(Settings(bus="memory"))` with uvicorn on a free port in a background thread; `run_deployed_smoke(base_url, allow_memory=True)` returns a result with `healthz_ok`, `snapshot_ms`, `first_event_ms`; without `allow_memory` it fails with reason `bus is memory, expected eventhubs`; unreachable URL exits 2 with a one-line reason and no traceback; `--soak-s 30` keeps the socket open and counts ≥ 2 heartbeats
- [ ] T019 [US1] Implement `backend/src/tactistream/smoke/deployed.py` (`async run_deployed_smoke(base_url: str, *, allow_memory: bool = False, timeout_s: float = 30, soak_s: int = 0) -> DeployedSmokeResult`) and command `deployed` in `smoke/cli.py` printing a one-line JSON summary; run T018 → green; run `make image-smoke`

### Provision and ship

- [ ] T020 [US1] Run `az deployment group what-if` then `azd up` into `rg-tactistream-prod` per quickstart §2; run `tactistream-smoke deployed`; record region, Foundry account/RG, deployment, model, app URL and the verified Foundry role definition id in `specs/007-azure-platform/research.md` R1
- [ ] T021 [P] [US1] Create `infra/scripts/setup-github-oidc.sh` (idempotent: `az ad app create`, `az ad sp create`, two `az ad app federated-credential create` for `ref:refs/heads/main` and `environment:production`, AcrPush on ACR, Contributor on RG; prints the `gh variable set` commands) and run it
- [ ] T022 [US1] Create `.github/workflows/deploy.yml`: on push `main` + `workflow_dispatch`; `environment: production`; `permissions: {id-token: write, contents: read}`; `concurrency: deploy-prod`; steps checkout → `azure/login@v2` (vars) → `az acr login` → `docker buildx build --push -t $ACR.azurecr.io/tactistream:${{ github.sha }} .` → `az containerapp update --image …` → poll `az containerapp revision show` until `healthState == Healthy` (timeout 5 min) → `uv run tactistream-smoke deployed --base-url ${{ vars.APP_URL }}`; push a commit and confirm the run passes (SC-002 timing noted in research R1)
- [ ] T023 [US1] Make `frontend/playwright.config.ts` use `process.env.BASE_URL` when set (and skip `webServer`); run `BASE_URL=$APP_URL npx playwright test tests/e2e/skeleton.spec.ts --repeat-each=5` (SC-003) and a 5-minute WebSocket soak `tactistream-smoke deployed --soak-s 300` (US1 scenario 5); note results in research R1

### Blob artifacts

- [ ] T024 [P] [US1] Write failing `backend/tests/unit/test_blob_store.py` with an injected fake `BlobServiceClient` (dict-backed): keys route to containers per data-model.md table; `put` then `get` round-trips bytes and content type; `exists`/`list(prefix)` behave per 003's `ArtifactStore` contract tests (reuse 003's shared protocol test suite `backend/tests/unit/artifact_store_contract.py` via parametrization); missing key raises `ArtifactNotFound`; credential is never a key or connection string
- [ ] T025 [US1] Implement `backend/src/tactistream/storage/blob.py` (`BlobArtifactStore(account_url, credential, *, client_factory=None)`; async `azure.storage.blob.aio.BlobServiceClient`; `aclose()`); run T024 → green
- [ ] T026 [P] [US1] Write failing `backend/tests/unit/test_artifact_factory.py` then implement `backend/src/tactistream/storage/factory.py` (`build_artifact_store(settings) -> ArtifactStore`: `local` → `LocalArtifactStore(settings.data_dir / "artifacts")`, `blob` → `BlobArtifactStore(settings.azure_storage_account_url, DefaultAzureCredential())`); wire into `api/app.py` lifespan and pass to 003's checkpoint writer; checkpoint write failures call `get_instruments().record_checkpoint_failure()` (no-op until T032) and never raise into the live path
- [ ] T027 [US1] Write `backend/tests/integration/test_checkpoint_blob_restore.py` (fake Blob client): play skeleton to end, write checkpoint via 003 `state/checkpoint.py`, construct a new `MatchState` from the stored checkpoint, assert identical `state_hash` (US1 scenario 4); add `backend/tests/live/test_blob_live.py` (`@pytest.mark.live`) round-tripping a 1 KB key in each container against the real account; run once with `uv run pytest -m live tests/live/test_blob_live.py`

### Operations

- [ ] T028 [P] [US1] Create `.github/workflows/uptime.yml` (cron `0 3 * * *` + `workflow_dispatch`; date guard from plan.md; `uv run tactistream-smoke deployed --base-url ${{ vars.APP_URL }}`; no Azure login needed)
- [ ] T029 [P] [US1] Create `infra/scripts/inventory.sh` (`az resource list -g $1` → JSON array of `{type, name, location, sku}` + `az cognitiveservices account deployment list` for the Foundry account → `{deployment, model, version, region}`; exits non-zero if the Container App, Event Hubs namespace or storage account is missing)
- [ ] T030 [US1] Create `docs/operations.md` (first version): resource table from `inventory.sh`, URLs, deploy and rollback commands (quickstart §Rollback), uptime workflow, budget, availability commitment through 10 Nov 2026 PT, teardown not before 12 Nov 2026, stop rule (services not deployed are removed from claims), incident log table (empty)

**Checkpoint (007a, US1)**: deployed URL passes smoke + Playwright 5/5; deploy workflow green; Blob round-trip live test passes.

---

## Phase 4: User Story 2 — Latency, fallbacks and tokens in Application Insights (P1) 🎯 007a

**Goal**: measurable, correlated telemetry for every number 008 will publish.

**Independent Test**: unit tests with OTel in-memory exporters; `infra/scripts/check-telemetry.sh` returns rows for every query after one deployed match.

- [ ] T031 [P] [US2] Write failing `backend/tests/contract/test_latency_sample.py`: `contracts/examples/latency_sample.json` validates against new `contracts/schemas/latency_sample.schema.json` and round-trips through `LatencySample`; narrative sample with `outcome="fallback"` and no `fallback_reason` is rejected by both; `value_ms < 0` rejected
- [ ] T032 [US2] Add `contracts/schemas/latency_sample.schema.json`, `contracts/examples/latency_sample.json` and `backend/src/tactistream/contracts/latency.py` (`LatencySample`, model validator for the fallback-reason rule); regenerate TS types (`make contracts`); run T031 → green
- [ ] T033 [P] [US2] Write failing `backend/tests/unit/test_correlation.py` (in-memory span exporter): inside `workflow_span("demo-blue-amber-001", "mom-0045")` the yielded id is 32 lowercase hex and equals the exported span's trace id; span name `tactistream.explain_moment` with attributes `match_id`, `moment_id`, `config`; nested spans share the trace id; `current_trace_id()` outside a span returns `None`; with telemetry unconfigured ids are still valid
- [ ] T034 [US2] Implement `backend/src/tactistream/telemetry/correlation.py` and change `telemetry/otel.py::setup_telemetry` to always install an SDK `TracerProvider` + `MeterProvider` + `LoggerProvider` with resource attributes (FR-017), exporting to Azure Monitor only when the connection string is set; run T033 → green
- [ ] T035 [P] [US2] Write failing `backend/tests/unit/test_instruments.py` (in-memory metric reader): each `Instruments` method records to the instrument named in FR-018 with the exact attribute keys; `record_model_call` adds input and output tokens as two data points with `direction`; unknown fallback reason raises `ValueError`
- [ ] T036 [US2] Implement `backend/src/tactistream/telemetry/instruments.py` (`Instruments`, module-level `get_instruments()` lazily bound to the global meter); run T035 → green
- [ ] T037 [US2] Write failing `backend/tests/unit/test_latency_logging.py` then extend `backend/src/tactistream/telemetry/latency.py`: `LatencyRecorder.record(...)` builds a `LatencySample`, keeps the in-memory sample (unchanged API), calls `Instruments.record_latency`, logs `tactistream.latency` with `extra` attributes (kind, value_ms, outcome, match_id, target_id, trace_id, viewer_id) and invokes an optional `on_sample: Callable[[LatencySample], None]` hook (used by T048); fallback samples are logged, never skipped
- [ ] T038 [P] [US2] Write failing `backend/tests/infra/test_queries_kql.py` (parses `// name:` blocks; asserts the seven names from FR-021 exist, each block is non-empty and references only `traces`, `requests`, `dependencies`, `customMetrics`, `exceptions`), then create `infra/appinsights/queries.kql` (`FastOverlayP95`/`NarrativeP95` use `traces | where message == "tactistream.latency"` and `percentiles(todouble(customDimensions.value_ms), 50, 95)` with `count()` and fallback share; `FallbackByReason`, `TokensByAgent` over `customMetrics`; `TraceById` with `let trace_id = "<id>";` union of requests/dependencies/traces by `operation_Id`; `RequestsAndFailures`; `HistoryQueryHealth`)
- [ ] T039 [P] [US2] Create `infra/scripts/check-telemetry.sh` (splits `queries.kql` by `// name:`, runs each via `az monitor app-insights query --app $2 -g $1 --analytics-query`, substitutes the latest `operation_Id` for `TraceById`, prints row counts, exits 1 if any query returns 0 rows)
- [ ] T040 [US2] (17 Oct, after 004 merges) Write failing `backend/tests/integration/test_workflow_telemetry.py`: run 004 `explain_moment` with `ScriptedModelClient` (3 calls with fixed usage) → `AgentTrace.trace_id == every InsightPacket.trace_id == exported workflow span trace id`; model-call spans are children; `model_tokens_total` increments match scripted usage per agent; with `model_timeout` fixture → `narrative_fallback_total{reason="timeout"} == 1` and a narrative latency sample with `outcome="fallback"` is recorded after display ack
- [ ] T041 [US2] Wire telemetry into 004 code: `backend/src/tactistream/agents/workflow.py` (`explain_moment` wraps its body in `workflow_span` and uses the yielded id as `WorkflowContext.trace_id`; `record_fallback` on every fallback path), `agents/baselines.py` (same span, `config="single_agent"` / `"deterministic"`), `agents/model_client.py` (child span `tactistream.model_call` + `record_model_call` with the client's reported usage); run T040 → green
- [ ] T042 [US2] Deploy, play one demo match (with one `model_timeout` fixture via `POST /api/matches/{id}/fixtures`), run `infra/scripts/check-telemetry.sh`; for 3 moments compare trace view `trace_id` with App Insights `operation_Id` (SC-004); record results in research.md R7/R8 notes

**Checkpoint (007a done)**: roadmap exit "Skeleton deployed to Container Apps reading from Event Hubs; telemetry in Application Insights" met.

---

## Phase 5: User Story 3 — Durable match record in Fabric (P2) 🎯 007b

**Goal**: Eventstream → Eventhouse with typed tables and saved functions, fed by match records and system outputs.

**Independent Test**: `tactistream-smoke fabric` finds the probe in `Latency`; `MatchSummary` counts match one deployed demo match.

### Contracts and publishing

- [ ] T043 [P] [US3] Write failing contract tests in `backend/tests/contract/test_examples.py` for new examples `contracts/examples/feed_envelope_latency.json` and `contracts/examples/feed_envelope_agent_trace.json`; then add `if kind == "latency" → latency_sample.schema.json` and `if kind == "agent_trace" → agent_trace.schema.json` (from 004) branches to `contracts/schemas/feed_envelope.schema.json`, update the `record_id` description to the formats in data-model.md, bump `schema_version` minor; run → green
- [ ] T044 [P] [US3] Write failing `backend/tests/unit/test_ingest_ignores_analytics.py`: applying `insight`, `agent_trace` and `latency` envelopes to `MatchState` returns `StateDelta(ignored=True)`, leaves `state_version` and `state_hash()` unchanged, and does not add evidence; then implement the guard in `backend/src/tactistream/state/match_state.py` (or 003's ingestor if it owns dispatch)
- [ ] T045 [P] [US3] Write failing `backend/tests/unit/test_analytics_publisher.py` (InMemoryBus + FakeClock): `offer_insight(bundle with 4 variants)` → 4 `insight` envelopes with record ids `ins-0045:1:fan:en` …; `offer_agent_trace` → `record_id == trace_id`; `offer_latency` → `record_id == sample_id`; all with `partition` key `match_id` and `published_ms` from clock; `enabled=False` → nothing published; queue size 3 + 5 offers → 2 dropped, `dropped["insight"] == 2`, `record_analytics_drop` called; a bus whose `publish` raises → envelope dropped and counted, drain task keeps running; `offer_*` never awaits (synchronous signature asserted)
- [ ] T046 [US3] Implement `backend/src/tactistream/transport/analytics_publisher.py`; run T045 → green
- [ ] T047 [US3] Write failing `backend/tests/integration/test_analytics_in_session.py`: with `TACTISTREAM_ANALYTICS_PUBLISH=on`, a played session publishes `insight` envelopes for each released bundle, one `agent_trace` per explained moment and one `latency` per display ack; with a bus whose `publish` blocks forever for analytics kinds, the WebSocket still receives the `insight` message (live path does not await Fabric — SC-006 logic)
- [ ] T048 [US3] Wire `AnalyticsPublisher` into `backend/src/tactistream/api/app.py` lifespan (start drain task), `api/session.py` (after release → `offer_insight`), 004 workflow completion hook (→ `offer_agent_trace`) and `LatencyRecorder(on_sample=publisher.offer_latency)`; run T047 → green

### Eventhouse scripts

- [ ] T049 [P] [US3] Create shared golden fixture `backend/tests/fixtures/history_golden.json`: 40 events (two teams, passes complete/incomplete, 2 shots, 3 interceptions/recoveries, duplicates of 3 events) with `session_clock_ms`, plus expected `MatchSummary` and `PlayerHistory("blue-09")` outputs at three as-of times (before first event, mid, after last)
- [ ] T050 [US3] Write failing `backend/tests/infra/test_kql_scripts.py`: parse `infra/fabric/tables.kql` `.create-merge table` statements and assert tables/columns/types equal `specs/007-azure-platform/contracts/eventhouse-tables.md` (parsed from its column lists); `mappings.kql` maps every `RawEnvelopes` column; `functions.kql` defines every function in the contract table, has one `.alter table … policy update` per typed table with `IsTransactional=false` and source `RawEnvelopes`, uses only `.create-or-alter`/`.create-merge` (idempotent); `MatchSummary` and `PlayerHistory` bodies contain `SessionClockMs <= as_of_ms`
- [ ] T051 [US3] Create `infra/fabric/tables.kql` (tables + retention policies + streaming ingestion policy on `RawEnvelopes`), `infra/fabric/mappings.kql` (`RawEnvelopesMapping` JSON), `infra/fabric/functions.kql` (Parse* functions, update policies, `EventsDeduped`, `Frames2Hz`, `MatchMetadata`, `MatchSummary`, `PlayerHistory`, `LatencyP95`, `FallbackRate`, `ClaimSupportByConfig`) per the contract; run T050 → green
- [ ] T052 [P] [US3] Write optional `backend/tests/kusto/test_kql_emulator.py` (`@pytest.mark.kusto`; uses `KUSTO_EMULATOR_URI`, default `http://localhost:8080`, for `mcr.microsoft.com/azuredataexplorer/kustainer-linux`): run the three scripts, ingest `history_golden.json` as envelopes into `RawEnvelopes` inline, assert typed-table routing, `EventsDeduped` counts and `MatchSummary`/`PlayerHistory` outputs equal the golden expectations; add `make kusto-test` (docker run emulator + pytest -m kusto)
- [ ] T053 [US3] Write `infra/fabric/SETUP.md`: (0) record capacity SKU/trial/end date (research R10); (1) create Eventhouse `tactistream-eh` + KQL DB `tactistream`; (2) run `tables.kql` → `mappings.kql` → `functions.kql` in the DB query editor; (3) create cloud connection to Event Hubs (namespace FQDN, hub `tactistream-feed`, auth per research R4; Listen key from `az eventhubs eventhub authorization-rule keys list … --name fabric-listen` typed directly into the portal); (4) Eventstream `tactistream-feed-es`: source Azure Event Hubs, consumer group `fabric`, format JSON; destination Eventhouse `tactistream`.`RawEnvelopes`, mapping `RawEnvelopesMapping`, direct ingestion; (5) `.add database tactistream viewers ('aadapp=<MANAGED_IDENTITY_CLIENT_ID>;<tenant>')`; (6) copy Query URI to `FABRIC_KUSTO_QUERY_URI`; (7) verification queries with expected results; troubleshooting table (no rows, mapping errors via `.show ingestion failures`, update-policy failures)

### Smoke and measurement

- [ ] T054 [P] [US3] Write failing `backend/tests/unit/test_smoke_fabric.py` (fake bus + fake Kusto client returning the row on the 3rd poll): `run_fabric_smoke` publishes one `latency` envelope with unique `sample_id` and `config="smoke"`, polls `Latency | where SampleId == …` with parameters every 10 s, returns `lag_s`; times out after 300 s with exit 1
- [ ] T055 [US3] Implement `backend/src/tactistream/smoke/fabric.py` + command `fabric` in `smoke/cli.py`; run T054 → green
- [ ] T056 [US3] (by 19 Oct) Execute `infra/fabric/SETUP.md` steps 0–6 in the Fabric workspace; record capacity SKU, trial status and end date in research.md R10; if it ends before 11 Nov 2026, move to paid capacity or record the stop-rule decision in `docs/operations.md`
- [ ] T057 [US3] Add `backend/tests/live/test_fabric_ingest.py` (`@pytest.mark.live`): run `tactistream-smoke fabric`; play one deployed demo match; assert `EventsDeduped` count == unique events from the session snapshot, `Frames` count == frames published, `Insights` rows == released variants; run it and record lag + counts (SC-005) in research.md R9
- [ ] T058 [US3] Measure SC-006: play one deployed demo match with Eventstream running and one with Eventstream paused, compare `FastOverlayP95` (App Insights) p95 values; record both in research.md R12
- [ ] T059 [P] [US3] Set `TACTISTREAM_HISTORY=eventhouse`, `FABRIC_KUSTO_QUERY_URI`, `FABRIC_KUSTO_DATABASE=tactistream` as Bicep params/outputs in `infra/main.parameters.json` and `infra/modules/containerapps.bicep` env; `azd provision`; `what-if` shows only env changes
- [ ] T060 [P] [US3] Run `LatencyP95("narrative", 1d)`, `FallbackRate(1d)`, `ClaimSupportByConfig()` in the KQL editor after a deployed match; record the textual results in research.md R9 (row counts only; detailed results belong to 008)
- [ ] T061 [US3] Check whether the Eventstream Event Hubs source accepts Entra authentication; if yes, switch the connection, delete `fabric-listen` from `infra/modules/eventhubs.bicep`, set `disableLocalAuth: true`, update T006 assertions and research R4; if no, record "SAS Listen-only retained" in research R4 and plan Complexity Tracking

**Checkpoint (US3)**: Eventhouse populated by a deployed match; live path unaffected with Eventstream paused.

---

## Phase 6: User Story 4 — History tool for the Analyst (P2) 🎯 007b

**Goal**: as-of, same-match history as verifiable evidence IDs, never on the fast path.

**Independent Test**: unit tests with the golden fixture and fake Kusto client; live test against Eventhouse.

- [ ] T062 [P] [US4] Write failing `backend/tests/unit/test_history_memory.py`: load `history_golden.json`, dedupe by `event_id`, and assert `InMemoryHistoryStore.match_summary`/`player_history` equal the golden expectations at all three as-of times; no returned `EventRef` has `session_clock_ms > as_of_ms`; unknown match → empty summary (zeros), not an exception
- [ ] T063 [US4] Implement `backend/src/tactistream/history/base.py` (`HistoryStore`, `HistorySummary`, `EventRef`, `HistoryUnavailable`) and `history/memory.py` (`InMemoryHistoryStore` with `add(event)` called from the session's accepted-event hook); run T062 → green
- [ ] T064 [P] [US4] Write failing `backend/tests/unit/test_history_eventhouse.py` with a fake async Kusto client: query text is exactly `declare query_parameters(match_id:string, as_of_ms:long); MatchSummary(match_id, as_of_ms)` with parameters set on `ClientRequestProperties` (a `match_id` containing `"; .drop table` is passed as a parameter, never interpolated); `servertimeout` set; rows map to `HistorySummary` equal to golden; a client sleeping 3 s → `HistoryUnavailable("timeout")` raised within 1.6 s; client exception → `HistoryUnavailable("error")`; durations reported to `record_history_query`
- [ ] T065 [US4] Implement `backend/src/tactistream/history/eventhouse.py` (`KustoHistoryStore(query_uri, database, credential, *, timeout_ms=1500, client=None)`, `aclose()`); run T064 → green
- [ ] T066 [P] [US4] Write failing `backend/tests/unit/test_history_tool.py`: `GetHistoryArgs` rejects extra fields (`match_id`, `as_of_ms` supplied by a model → validation error mapped to tool error `invalid_args`); `get_history` uses `ctx.snapshot.match_id` and `ctx.snapshot.as_of_ms`; IDs absent from `ctx.evidence.resolve(id, as_of_ms)` are dropped and counted; store `HistoryUnavailable("timeout")` → `HistoryToolResult(status="unavailable", reason="timeout")`; `history="off"` → `reason="disabled"`; `player_history` without `player_id` → `invalid_args`
- [ ] T067 [US4] Implement `backend/src/tactistream/history/tool.py` (`GetHistoryArgs`, `HistoryToolResult`, `get_history(args, ctx)`, `GET_HISTORY_TOOL_SPEC`) and `history/factory.py` (`build_history_store(settings) -> HistoryStore | None`); run T066 → green
- [ ] T068 [P] [US4] Write `backend/tests/architecture/test_fast_path_imports.py`: walk imports (via `ast`) of `tactistream.state`, `metrics`, `moments`, `transport`, `narrative`, `api/ws.py`, `api/ws_hub.py` and assert none import `tactistream.history` or `tactistream.agents`; only `agents/` and `api/app.py` may import `tactistream.history`
- [ ] T069 [US4] Write failing `backend/tests/integration/test_history_in_workflow.py` (ScriptedModelClient whose Analyst step calls `get_history` then cites two returned event IDs): claim passes Verifier and output checks; with a store that sleeps 3 s the tool returns `unavailable`, the workflow still releases (or falls back) within the 8 s deadline on FakeClock, and the card contains no history-derived numbers
- [ ] T070 [US4] Register `GET_HISTORY_TOOL_SPEC` in 004's tool registry `backend/src/tactistream/agents/tools.py` (Analyst only; Verifier gets read access to resolve cited IDs through the evidence index, not the tool), add one sentence to the Analyst instructions (`agents/prompts/analyst.md` or 004's equivalent): "`get_history` returns earlier events of this match as of now; cite its event IDs like any other evidence; if unavailable, continue without history"; wire `build_history_store` into `api/app.py`; run T069 → green
- [ ] T071 [US4] Add `backend/tests/live/test_history_eventhouse.py` (`@pytest.mark.live`): after a deployed match, 50 `match_summary` calls at random as-of times → 0 future events, p95 ≤ 1.5 s, timeouts counted; run it and record p95 + timeout count in research.md R11 (SC-007)

**Checkpoint (007b done)**: roadmap exit "Fabric Eventstream → Eventhouse populated; historical evidence tool answers as-of queries" met.

---

## Phase 7: Polish

- [ ] T072 [P] Update `docs/operations.md` with Fabric items (workspace, Eventhouse, Eventstream, capacity end date), history mode, telemetry query usage and the incident-log procedure; link `infra/fabric/SETUP.md` and `infra/appinsights/queries.kql`
- [ ] T073 [P] Run `specs/007-azure-platform/quickstart.md` §1–§3 against a scratch resource group `rg-tactistream-verify` from a fresh clone, fix gaps, then delete the scratch group
- [ ] T074 Run `infra/scripts/inventory.sh` and compare with every architecture claim currently in `README.md`/`docs/` (if present); remove or relabel any service not deployed and used (stop rule); attach the inventory JSON path for 009
- [ ] T075 Update `specs/README.md` feature table rows 007a and 007b: mark exit conditions met with dates (or record which stop rule was applied)

---

## Dependencies & Execution Order

- Setup (T001–T004) → Foundational (T005–T006) → US1 infra (T007–T014; T007–T011 parallel, then T012 → T013) and app/container work (T015–T019) in parallel → provision (T020) → OIDC + CI/CD (T021–T023) → Blob (T024–T027, can start right after T003) → ops (T028–T030).
- US2: T031–T039 can start in parallel with US1 after T003; T040–T041 need 004's `explain_moment`, `AgentTrace`, `ScriptedModelClient` (17 Oct); T042 needs a deployed app (T020) and T041.
- US3 needs US1 deployed, US2 T032 (LatencySample) and 004's `AgentTrace` schema; T056 (Fabric portal setup) should happen by 19 Oct to surface capacity/permission issues early.
- US4: T062–T068 need only T003 and the golden fixture T049; T069–T070 need 004's tool registry; T071 needs T056 + T059.
- Polish after US4.

## Parallel Example

```text
15 Oct morning:   T007–T011 (Bicep modules)  ||  T015–T016 (SPA fallback)  ||  T031–T036 (latency contract, correlation, instruments)
15 Oct afternoon: T020 (azd up) → T021–T022 (OIDC deploy)  ||  T024–T026 (Blob)  ||  T038–T039 (KQL queries)
20 Oct:           T049–T051 (KQL scripts)  ||  T062–T067 (history store + tool)  ||  T045–T046 (publisher)
21 Oct:           T057–T058 (Fabric measurements)  ||  T069–T071 (history in workflow + live)
```

## Implementation Strategy

007a MVP = Phases 1–4 on 15 Oct (agent wiring T040–T041 on 17 Oct). 007b = Phases 5–6 on 20–21 Oct. If Fabric is blocked by
21 Oct (capacity, permissions, connector auth), apply the stop rule: keep `InMemoryHistoryStore` (labelled "in-process history"),
remove Fabric from architecture claims, record the decision in `docs/operations.md`, and continue with 008.
