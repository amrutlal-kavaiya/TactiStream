# Feature Specification: Azure Platform — deploy, observe, analyse, remember

**Feature Branch**: `007-azure-platform`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan, "Use a small Microsoft architecture with a fast live path", "Treat reliability as part of the
demonstration", "Finish with proof that someone else can run it". Roadmap splits delivery: **007a = US1–US2 on 15 Oct**
(skeleton deployed to Container Apps reading from Event Hubs; telemetry in Application Insights), **007b = US3–US4 on
20–21 Oct** (Fabric Eventstream → Eventhouse populated; historical evidence tool answers as-of queries). Judging access must
stay up through **10 Nov 2026 Pacific Time**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Judges open a live deployed TactiStream (Priority: P1) — 007a, 15 Oct

A judge opens the public HTTPS URL of the Azure Container Apps deployment, presses **Start demo match**, and sees the same
verified card and evidence drawer as the local walking skeleton, with the feed travelling through Azure Event Hubs
(`tactistream-feed`, consumer group `live-state`). The builder provisions everything with one Bicep deployment (`azd up` or
`az deployment group create`) and ships every merge to `main` with a GitHub Actions workflow that authenticates by OIDC — no
secrets in git. Checkpoints, feed archives, datasets and recap exports go to Azure Blob Storage through the
`ArtifactStore` protocol so a container restart does not lose them.

**Why this priority**: "Working judging experience" is an official requirement; Event Hubs and Container Apps are claimed in
the architecture and must be real (constitution VI). Deploying the skeleton on day two surfaces quota, region, identity and
WebSocket-ingress problems while they are cheap.

**Independent Test**: After `azd up` (or the deploy workflow), `uv run tactistream-smoke deployed --base-url https://<app>`
exits 0: `/healthz` reports `bus = eventhubs`, a session is created, a WebSocket opens and receives `snapshot` then at least
one `event` within 15 s. `az deployment group what-if` against the live resource group reports no unexpected changes.

**Acceptance Scenarios**:

1. **Given** an empty resource group and the Bicep parameters file, **When** the builder runs `azd up`, **Then** Log
   Analytics, Application Insights, ACR, a Container Apps environment + app (min = max = 1 replica, external ingress on port
   8000, `/healthz` liveness/readiness/startup probes, user-assigned managed identity), an Event Hubs Standard namespace with
   hub `tactistream-feed` (2 partitions, consumer groups `live-state` and `fabric`), and a storage account with containers
   `datasets`, `artifacts`, `checkpoints` exist, and the managed identity holds exactly the roles listed in FR-007.
2. **Given** the app is deployed, **When** a judge opens the URL in a fresh browser and presses Start demo match, **Then**
   the Synthetic badge and the verified forward-pass card appear and `evt-0042` opens in the evidence drawer.
3. **Given** a push to `main`, **When** the deploy workflow runs, **Then** it logs in with `azure/login` using OIDC federated
   credentials, builds the root `Dockerfile`, pushes `<acr>/tactistream:<git-sha>` to ACR, updates the container app to that
   image, and the post-deploy smoke step passes; on smoke failure the job fails and the previous revision stays active.
4. **Given** the app has written a checkpoint for a running match, **When** the replica restarts, **Then** the checkpoint is
   readable from the `checkpoints` container and restoring it yields the same `state_hash` as before the restart.
5. **Given** the WebSocket connection is idle for 60 s, **When** heartbeats flow every 10 s, **Then** the ingress does not
   close the connection (no 240 s idle drop observed in a 5-minute soak).

---

### User Story 2 - Builder sees latency, fallbacks and token usage in Application Insights (Priority: P1) — 007a, 15 Oct (+ agent wiring 17 Oct)

The builder opens Application Insights and, using saved queries from `infra/appinsights/queries.kql`, sees request traces,
fast-overlay and narrative latency samples with p50/p95, narrative fallback counts by reason, model calls and token usage per
agent, and history-query timings. Selecting an agent `trace_id` shown in the TactiStream trace view finds the same
end-to-end OpenTelemetry trace (`operation_Id`) in Application Insights.

**Why this priority**: Constitution VI ("Measure, don't claim") and the build-plan observability row. 008 relies on these
signals for latency and economics; judges can challenge any number we publish.

**Independent Test**: Unit tests with OpenTelemetry in-memory exporters prove instrument names, attributes and trace-ID
correlation; after a deployed demo match, `infra/scripts/check-telemetry.sh` runs every saved query and each returns ≥ 1 row.

**Acceptance Scenarios**:

1. **Given** `APPLICATIONINSIGHTS_CONNECTION_STRING` is set, **When** a viewer displays a card, **Then** a
   `tactistream.fast_overlay_latency_ms` histogram point and a `tactistream.latency` log record (kind, value_ms, outcome,
   match_id) reach Application Insights, and the `FastOverlayP95` query returns p50, p95 and sample count.
2. **Given** the agent workflow explains a moment, **When** it releases or falls back, **Then** the workflow span's trace id
   equals the `trace_id` in the `AgentTrace` and every `InsightPacket` of that moment, and the `TraceById` query returns
   the workflow span and its model-call (and history-query) child spans for that id.
3. **Given** a model timeout fixture, **When** the narrative falls back, **Then** `tactistream.narrative_fallback_total`
   increments with `reason = timeout` and the narrative latency sample is recorded with `outcome = fallback` (never dropped).
4. **Given** three model calls in one workflow, **When** they complete, **Then** `tactistream.model_tokens_total` increments
   by the reported input and output tokens with attributes `agent ∈ {analyst, verifier, producer, single_agent}`,
   `direction ∈ {input, output}` and `model`.
5. **Given** telemetry is not configured (local dev or tests), **When** the app runs, **Then** it starts normally, trace ids
   are still valid 32-hex W3C ids, and no exporter errors are logged.

---

### User Story 3 - Analyst inspects the durable match record in Fabric (Priority: P2) — 007b, 20–21 Oct

The live feed and the system's own outputs land in Microsoft Fabric: an Eventstream reads Event Hubs through consumer
group `fabric` and ingests into Eventhouse KQL database `tactistream`. Update policies route envelopes by `kind` into
`Events`, `Frames`, `Insights`, `AgentTraces` and `Latency`. The API publishes `insight`, `agent_trace` and `latency`
envelopes to the same hub (non-blocking), so one KQL database answers "what happened, what did we say, how fast, and how often
did we fall back". Saved functions `MatchSummary`, `LatencyP95`, `FallbackRate`, `ClaimSupportByConfig` power the analysis.

**Why this priority**: Fabric is part of the claimed architecture and powers evaluation dashboards and historical evidence,
but the live path never depends on it; it can land after agents and Why Mode.

**Independent Test**: With the Fabric setup in `infra/fabric/SETUP.md` done, run one deployed demo match, then
`uv run tactistream-smoke fabric` publishes a probe `latency` envelope and finds it in `Latency` within 5 minutes, and
`MatchSummary('<match_id>', <as_of>)` returns the expected event counts for that match.

**Acceptance Scenarios**:

1. **Given** Eventstream is connected with consumer group `fabric`, **When** a demo match plays, **Then** `Events` contains
   one row per unique `event_id` (duplicates collapsed by the `EventsDeduped` view) and `Frames` contains every frame;
   `Frames2Hz()` returns every fifth frame.
2. **Given** a released insight, **When** the API publishes it, **Then** `Insights` holds one row per (insight_id,
   insight_version, mode, language) with its evidence IDs and trace id, and the WebSocket card was not delayed by the publish.
3. **Given** Fabric or Eventstream is paused, **When** a demo match plays, **Then** live cards, metrics and latency are
   unaffected (separate consumer group; publisher never awaits Fabric) and Eventstream catches up from Event Hubs
   retention when resumed.
4. **Given** `Latency` and `AgentTraces` rows exist, **When** the analyst runs `LatencyP95("narrative", 1d)` and
   `FallbackRate(1d)`, **Then** results include sample counts, p50/p95 and per-reason fallback counts with timeouts included.

---

### User Story 4 - Analyst agent cites earlier match history without slowing the live path (Priority: P2) — 007b, 20–21 Oct

While explaining a moment, the Analyst may call the read-only tool `get_history` to ask "how many forward passes has Blue
completed so far" or "what did Blue 9 do earlier in this match". The tool queries Eventhouse (or an in-memory store
locally) with an as-of filter equal to the snapshot's `as_of_session_ms`, returns event IDs and counts only, and answers in
≤ 1.5 s or degrades to "no history". Returned event IDs are resolvable in the session evidence index so the Verifier and
output checks treat them like any other evidence.

**Why this priority**: The build plan wires "Historical evidence and recaps → Analyst". It adds depth to Analyst claims but
is optional per moment, so failures must be invisible to the viewer except as absent history.

**Independent Test**: Unit tests with `InMemoryHistoryStore` and a fake Kusto client prove as-of filtering, timeouts and
degradation; a `@pytest.mark.live` test runs `KustoHistoryStore.match_summary` against the real Eventhouse.

**Acceptance Scenarios**:

1. **Given** events up to sequence 60 exist in history, **When** the tool is called with a snapshot as of the session time
   of sequence 45, **Then** no event with `session_clock_ms` greater than the as-of time is counted or returned.
2. **Given** Eventhouse takes 3 s, **When** the tool is called, **Then** it returns `status = unavailable, reason = timeout`
   after ≤ 1.5 s (+ 100 ms tolerance), the workflow continues and the narrative deadline is still met.
3. **Given** the model asks for a different `match_id` or a future `as_of`, **When** the tool runs, **Then** the server ignores
   model-supplied match and time values and uses the session match and snapshot as-of time.
4. **Given** a returned event ID not present in the session evidence index, **When** the tool builds its result, **Then**
   that ID is dropped and counted in `dropped_unresolvable`.

### Edge Cases

- Foundry model deployment lives in a different region or resource group than the Container App → role assignment module is
  scoped to the Foundry resource group; cross-region narrative calls are allowed (narrative path only, never fast path).
- Event Hubs throttling or transient failure → `EventHubsBus.publish` retries with the SDK's default backoff; persistent failures
  appear in the `RequestsAndFailures` query and fail the uptime smoke; analytics publishes are dropped and counted, never retried indefinitely.
- Analytics publisher queue full (1000 envelopes) → the new envelope is dropped, `tactistream.analytics_dropped_total{kind}`
  increments, and the caller is never blocked.
- Live-state consumer receives `insight` / `agent_trace` / `latency` envelopes from the shared hub → ignored by ingest without
  changing `state_version`.
- Container restart during a match → in-memory sessions are lost; the app restarts healthy; checkpoints remain in Blob and a new
  session can be started from the judge route. Judges see a reconnecting banner, then a fresh snapshot.
- Blob unavailable → the app still starts; checkpoint and archive writes fail soft (logged, counted in
  `tactistream.checkpoint_write_failures_total`) and never block the live path; there is no silent switch to local storage.
- Eventhouse ingestion lag (seconds to minutes) → history may be behind live state; the as-of filter still guarantees no
  future data; missing recent events simply reduce counts.
- Fabric trial or capacity paused before 10 Nov → live demo unaffected; `docs/operations.md` states the capacity end date
  and the stop rule removes Fabric from architecture claims if it is not running at submission.
- Deploy workflow fails mid-way → Container Apps keeps the previous active revision (single-revision mode updates only when
  the new revision is healthy).
- Budget threshold reached → email alert; no automated shutdown (shutdown would break judging access).

## Requirements *(mandatory)*

### Functional Requirements

**Deploy (US1)**

- **FR-001**: Repository MUST contain `infra/main.bicep` composing modules `infra/modules/{monitoring,registry,identity,containerapps,eventhubs,storage,roles,foundry-role,budget}.bicep` (`identity.bicep` creates the user-assigned managed identity that `containerapps.bicep` attaches, split out so role assignments exist before the first ACR pull), a parameters file `infra/main.parameters.json` (azd-style env substitution, no secrets), and `bicepconfig.json` enabling the linter with warnings as errors.
- **FR-002**: `monitoring.bicep` MUST create a Log Analytics workspace (PerGB2018, 30-day retention) and a workspace-based Application Insights component; outputs connection string and names.
- **FR-003**: `registry.bicep` MUST create ACR (Basic, admin user disabled).
- **FR-004**: `containerapps.bicep` MUST create a Consumption Container Apps environment linked to Log Analytics and one app `tactistream` with `minReplicas = maxReplicas = 1`, single revision mode, external ingress (targetPort 8000, transport `auto`, HTTP/1.1 upgrade for WebSockets, `allowInsecure = false`), liveness/readiness/startup HTTP probes on `/healthz`, 1 vCPU / 2 GiB, the user-assigned managed identity for ACR pull and Azure SDKs (`AZURE_CLIENT_ID` env), and the environment variables listed in data-model.md "Runtime configuration".
- **FR-005**: `eventhubs.bicep` MUST create a Standard namespace (1 TU, TLS 1.2) with hub `tactistream-feed` (2 partitions, 7-day retention), consumer groups `live-state` and `fabric`, and a hub-scoped Listen-only authorization rule `fabric-listen` used solely by the Fabric Eventstream connection (research R4).
- **FR-006**: `storage.bicep` MUST create a StorageV2 Standard_LRS account (shared-key access disabled, public blob access disabled, TLS 1.2) with private containers `datasets`, `artifacts`, `checkpoints`.
- **FR-007**: `roles.bicep` MUST grant the managed identity: AcrPull on ACR, Azure Event Hubs Data Sender and Azure Event Hubs Data Receiver on the namespace, Storage Blob Data Contributor on the storage account; `foundry-role.bicep`, deployed at the scope of the existing Foundry resource's resource group (params `foundryResourceGroup`, `foundryAccountName`), MUST grant the Foundry user role (param `foundryRoleDefinitionId`, default Azure AI User) on that account. No other role assignments.
- **FR-008**: `budget.bicep` MUST create a resource-group budget (param `monthlyBudget`, default 100 in billing currency) with alerts at 50%, 80% and 100% actual and 100% forecast to `alertEmail`.
- **FR-009**: Root `azure.yaml` MUST let `azd up` provision `infra/main.bicep` and deploy service `web` (Docker, host `containerapp`); `main.bicep` outputs `AZURE_CONTAINER_REGISTRY_ENDPOINT`, `SERVICE_WEB_NAME`, `SERVICE_WEB_URI` and all runtime endpoint values.
- **FR-010**: Root `Dockerfile` MUST be multi-stage: Node 22 builds `frontend/dist`; `python:3.12-slim` runtime installs the backend with uv from the lockfile (`--frozen --no-dev`), copies `frontend/dist`, `contracts/schemas`, `data/fixtures` and `eval/results/latest` (if present); runs as non-root; `EXPOSE 8000`; `CMD ["tactistream-api"]`; sets `TACTISTREAM_STATIC_DIR` and `TACTISTREAM_CONTRACTS_DIR`. A `.dockerignore` excludes `.git`, `node_modules`, `.venv`, `.env*`, test outputs.
- **FR-011**: The FastAPI app MUST serve `frontend/dist` with SPA fallback (non-`/api`, non-`/ws`, non-`/healthz` GETs return `index.html`) so deep links work in the container.
- **FR-012**: `.github/workflows/deploy.yml` MUST trigger on push to `main` and `workflow_dispatch`, use `permissions: id-token: write, contents: read`, `azure/login@v2` with `client-id`/`tenant-id`/`subscription-id` from repository variables (not secrets-with-keys), build and push `tactistream:<sha>` to ACR, run `az containerapp update --image`, wait for the revision to be healthy, then run `tactistream-smoke deployed`.
- **FR-013**: `tactistream-smoke deployed --base-url URL` MUST check `/healthz` (`status=ok`, `bus=eventhubs` unless `--allow-memory`), create a session, open `/ws/matches/{match_id}` with `wss://`, require `snapshot` within 5 s, send `play`, require ≥ 1 `event` within 15 s, print timings, and exit non-zero with a one-line reason on failure.
- **FR-014**: `backend/src/tactistream/storage/blob.py` `BlobArtifactStore` MUST implement 003's `ArtifactStore` protocol over `azure-storage-blob` (async) with `DefaultAzureCredential`, routing keys by first path segment (`checkpoints/…` → `checkpoints`, `datasets/…` → `datasets`, everything else → `artifacts`), and `storage/factory.py` MUST select `LocalArtifactStore` or `BlobArtifactStore` from `TACTISTREAM_ARTIFACT_STORE`.
- **FR-015**: `.github/workflows/uptime.yml` MUST run daily (cron `0 3 * * *` UTC) and on dispatch, skip itself after 2026-11-11, and run `tactistream-smoke deployed` against the production URL; failure notifies via the failed-workflow email.
- **FR-016**: `infra/scripts/inventory.sh` MUST print a JSON inventory (resource type, name, region, SKU) of the resource group plus the Foundry deployment name/model/region, used by 009 to keep architecture claims to deployed services only.

**Telemetry (US2)**

- **FR-017**: `telemetry/otel.py::setup_telemetry` MUST always install an SDK `TracerProvider` (so trace ids are valid) and export to Azure Monitor when the connection string is set; resource attributes `service.name = tactistream-api`, `service.version`, `deployment.environment`.
- **FR-018**: `telemetry/instruments.py` MUST define instruments `tactistream.fast_overlay_latency_ms` and `tactistream.narrative_latency_ms` (histograms, ms), `tactistream.narrative_fallback_total` (counter, attr `reason`), `tactistream.model_calls_total` and `tactistream.model_tokens_total` (counters, attrs `agent`, `direction`, `model`), `tactistream.history_query_ms` (histogram, attr `status`), `tactistream.analytics_dropped_total` (counter, attr `kind`), `tactistream.checkpoint_write_failures_total` (counter).
- **FR-019**: `LatencyRecorder.record` MUST additionally emit one structured log record `tactistream.latency` per sample (attributes `kind`, `value_ms`, `outcome`, `match_id`, `target_id`, `trace_id`) so Application Insights can compute exact percentiles, and MUST hand the sample to the analytics publisher.
- **FR-020**: `telemetry/correlation.py::workflow_span(match_id, moment_id)` MUST open span `tactistream.explain_moment` and yield its 32-hex trace id; 004's `explain_moment` and baselines MUST use it as `WorkflowContext.trace_id`, so `AgentTrace.trace_id == InsightPacket.trace_id == operation_Id`.
- **FR-021**: `infra/appinsights/queries.kql` MUST contain named queries `FastOverlayP95`, `NarrativeP95`, `FallbackByReason`, `TokensByAgent`, `TraceById`, `RequestsAndFailures`, `HistoryQueryHealth`, each preceded by a `// name:` comment; `infra/scripts/check-telemetry.sh` runs each with `az monitor app-insights query`.

**Fabric (US3)**

- **FR-022**: `transport/analytics_publisher.py` `AnalyticsPublisher` MUST publish `insight` (one envelope per variant, `record_id = {insight_id}:{insight_version}:{mode}:{language}`), `agent_trace` (`record_id = trace_id`) and `latency` (`record_id = sample_id`) envelopes to the `FeedBus` via a bounded queue (1000) drained by a background task; `offer_*` methods are synchronous, never await, and drop + count on overflow. Disabled by `TACTISTREAM_ANALYTICS_PUBLISH=off`.
- **FR-023**: Live-state ingest MUST ignore envelope kinds `insight`, `agent_trace`, `latency` (no state change, no `state_version` bump).
- **FR-024**: `infra/fabric/tables.kql` MUST create `RawEnvelopes`, `Events`, `Frames`, `Insights`, `AgentTraces`, `Latency`, `ReviewLabels` with the columns in `contracts/eventhouse-tables.md`; `mappings.kql` the JSON mapping `RawEnvelopesMapping`; `functions.kql` the parse functions, update policies routing by `kind`, views `EventsDeduped`, `Frames2Hz`, and functions `MatchSummary`, `PlayerHistory`, `LatencyP95`, `FallbackRate`, `ClaimSupportByConfig`. Scripts MUST be idempotent (`.create-merge`, `.create-or-alter`).
- **FR-025**: `infra/fabric/SETUP.md` MUST list the portal steps (Eventhouse + KQL DB, script order, Event Hubs cloud connection, Eventstream source with consumer group `fabric`, destination `RawEnvelopes` with mapping, database viewer grant for the managed identity, capacity end-date check, verification queries) with expected results per step.
- **FR-026**: `tactistream-smoke fabric` MUST publish a probe `latency` envelope with a unique `sample_id` and poll `Latency` until found (timeout 300 s), printing ingestion lag.

**History (US4)**

- **FR-027**: `history/base.py` MUST define `HistoryStore` protocol with `async match_summary(match_id, as_of_ms) -> HistorySummary` and `async player_history(match_id, player_id, as_of_ms) -> list[EventRef]`, plus `HistorySummary`, `EventRef` and `HistoryUnavailable`.
- **FR-028**: `history/memory.py` `InMemoryHistoryStore` MUST answer from accepted `MatchEvent`s with identical semantics to the KQL functions (same counts on the same events; shared golden test).
- **FR-029**: `history/eventhouse.py` `KustoHistoryStore` MUST use `azure-kusto-data` (async) with `DefaultAzureCredential`, call `MatchSummary` / `PlayerHistory` with **query parameters** (never string interpolation), enforce a 1.5 s timeout (`TACTISTREAM_HISTORY_TIMEOUT_MS`), and return event IDs and counts only.
- **FR-030**: `history/tool.py::get_history` MUST be registered as a read-only Analyst tool; it takes only `{"query": "match_summary" | "player_history", "player_id"?}` from the model, injects `match_id` and `as_of_ms` from the server-side snapshot, drops event IDs not resolvable in the evidence index as of that time, and returns `status = unavailable` (reason `timeout` | `error` | `disabled`) instead of raising.
- **FR-031**: The history tool MUST NOT be called on the fast path (event → state → metrics → overlay); an architecture test asserts `tactistream.history` is imported only by `agents/` and `api/app.py` wiring.

**Operations**

- **FR-032**: `docs/operations.md` MUST document resources, URLs, deploy/rollback, uptime check, budget, Fabric capacity end date, availability commitment through 10 Nov 2026 PT, teardown date (not before 12 Nov 2026), and the stop rule: any service not deployed and used is removed from architecture claims.

### Key Entities

- **Deployment inventory**: resource group, region(s), resource names/SKUs, Foundry deployment/model/region, app URL — recorded in research.md R1 and produced by `inventory.sh`.
- **LatencySample**: one measured latency observation (fast overlay or narrative) with outcome and fallback reason; published as envelope kind `latency`.
- **AgentTrace** (004): per-moment workflow record published as envelope kind `agent_trace`.
- **HistorySummary / EventRef**: as-of counts and event references returned by the history tool.
- **Eventhouse tables**: `RawEnvelopes` + typed `Events`, `Frames`, `Insights`, `AgentTraces`, `Latency`, `ReviewLabels`.
- **ArtifactStore key**: slash-separated key whose first segment selects the Blob container.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From an empty resource group, `azd up` completes and the deployed smoke passes on the first or second attempt; `az bicep build` and lint report 0 errors and 0 warnings; `what-if` after deploy shows no changes.
- **SC-002**: The deploy workflow takes ≤ 12 minutes from push to passing smoke, and 5 consecutive daily uptime runs pass before 25 Oct.
- **SC-003**: The Playwright skeleton smoke passes 5/5 runs against the deployed URL (`BASE_URL=https://… npm run e2e`).
- **SC-004**: After one deployed demo match, every saved Application Insights query returns ≥ 1 row, and for 3 sampled moments the agent `trace_id` equals the Application Insights `operation_Id` of the workflow span (3/3).
- **SC-005**: After one deployed demo match, Eventhouse row counts equal the match's unique events and frames (100%), every released insight variant appears in `Insights`, and the probe envelope's ingestion lag is recorded.
- **SC-006**: With Eventstream paused, fast-overlay p95 over one demo match differs by ≤ 10% from the unpaused run (live path independent of Fabric).
- **SC-007**: History tool: 0 future events returned across the as-of golden tests; p95 tool latency ≤ 1.5 s across 50 live calls, with timeouts reported as a count.
- **SC-008**: The app answers `/healthz` on every daily uptime check from submission (26 Oct) through 10 Nov 2026 PT; any miss is recorded in `docs/operations.md` with cause and fix.

## Assumptions

- Azure subscription with Owner (or Contributor + User Access Administrator) on the target resource group; an existing Microsoft Foundry (AI Services) resource with a chat model deployment in a region with quota; a Fabric workspace with capacity exists (user confirmed).
- GitHub repository is public; the builder can create an Entra app registration with a federated credential for `repo:<owner>/TactiStream:ref:refs/heads/main` and the `production` environment.
- 003 provides `ArtifactStore` (`storage/base.py`), `LocalArtifactStore` (`storage/local.py`) and `state/checkpoint.py`; 004 provides `AgentTrace` (`agents/trace.py`), the tool registry (`agents/tools.py`), model clients (`agents/model_client.py`) and `WorkflowContext`. Where 007 tasks touch those files, they add hooks only.
- Fabric items (Eventhouse, KQL database, Eventstream, cloud connection) are created manually in the portal following `SETUP.md`; Bicep does not provision Fabric.
- One always-ready replica is sufficient for one demo match and ≤ 10 viewers per session (constitution VII); no multi-instance claims.
