# Research & Decisions: 007 Azure Platform

Builds on 001 research R5 (agent runtime), R6 (`DefaultAzureCredential` everywhere), R7 (Event Hubs layout), R11
(observability) and R13 (container). Items marked **Record at deploy** are filled by tasks with observed values; they are
measurements, not open questions.

## R1. Region and resource placement

- **Decision**: One resource group `rg-tactistream-prod` in one region (Bicep param `location`, default `eastus2`) for Container
  Apps, Event Hubs, Storage, ACR, Log Analytics and Application Insights. The **existing** Foundry resource stays where its
  model quota is; it may be in another region and resource group (params `foundryResourceGroup`, `foundryAccountName`). If the
  Foundry region also offers Container Apps, Event Hubs Standard and Storage, prefer that region to cut narrative round-trips.
- **Rationale**: Co-locating the live path (Event Hubs ↔ Container App) keeps fast-overlay latency low; the narrative path
  tolerates a cross-region model call within its 8 s deadline.
- **Alternatives rejected**: Central India (closest to the builder, farther from most judges, variable model quota); multi-region
  (no benefit for one replica).
- **Record at deploy** (T020): `location`: `____`; Foundry account: `____` in `____` (RG `____`); model deployment `____`
  (model + version `____`); Fabric capacity region `____`; app URL `____`.

## R2. Infrastructure as code and deployment tool

- **Decision**: Bicep modules + `azd` (`azure.yaml`) for first provisioning; GitHub Actions (`deploy.yml`) for every subsequent image
  rollout using plain `az` commands. `azd` and the workflow target the same resource names via `main.parameters.json` and the
  `azd-service-name: web` tag on the container app.
- **Rationale**: Bicep is native, linted and supports `what-if`; azd gives a one-command fresh setup for the README; Actions gives
  reproducible CI/CD without azd state in CI.
- **Alternatives rejected**: Terraform (state backend to manage); `azd deploy` in CI (needs azd env state and service principal
  login mode — OIDC with `azure/login` is simpler to audit).

## R3. Container Apps configuration

- **Decision**: Consumption environment; app with `minReplicas = maxReplicas = 1`, single revision mode, external ingress
  `targetPort: 8000`, `transport: auto` (supports WebSocket upgrade), no session affinity needed with one replica; 1.0 vCPU /
  2 GiB; probes: startup (`/healthz`, period 3 s, failureThreshold 20), liveness (period 10 s), readiness (period 5 s).
  User-assigned managed identity used both for `registries[].identity` (ACR pull) and Azure SDKs via `AZURE_CLIENT_ID`.
- **WebSockets**: server sends `heartbeat` every 10 s (001 protocol), well inside the ingress idle timeout; verified by the 5-minute
  soak in US1 acceptance 5.
- **Alternatives rejected**: App Service (WebSockets fine, but Container Apps is the documented plan choice); scale-to-zero (cold
  starts during judging); multiple replicas (needs durable match ownership — constitution VII).

## R4. Event Hubs authentication for Fabric

- **Decision**: The application uses Entra ID only (Data Sender/Receiver roles). The Fabric Eventstream cloud connection uses a
  **hub-scoped, Listen-only** SAS rule `fabric-listen`, because Eventstream's Event Hubs source has historically required a
  shared access key. The key lives only inside the Fabric connection (entered in the portal); it is never in git, env vars or
  the container. If the portal offers Entra/organizational authentication for the source at setup time, use it, delete
  `fabric-listen`, and set `disableLocalAuth: true` (task T061).
- **Rationale**: Least privilege within the connector's capabilities; keeps the security rule ("no secrets in git") intact.
- **Alternatives rejected**: Namespace-level RootManageSharedAccessKey (send/manage rights); pushing from the app directly to
  Eventhouse (couples live path to Fabric).

## R5. GitHub Actions OIDC

- **Decision**: Entra app registration `gh-tactistream-deploy` with federated credentials for `repo:<owner>/TactiStream:ref:refs/heads/main`
  and `repo:<owner>/TactiStream:environment:production`; roles: AcrPush on ACR and Contributor on the resource group (container
  app update). Repository **variables** `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `ACR_NAME`,
  `CONTAINERAPP_NAME`, `RESOURCE_GROUP`, `APP_URL` (identifiers, not secrets).
- **Alternatives rejected**: client secret in GitHub secrets (rotation burden, violates constitution security rule).

## R6. Image build

- **Decision**: Root `Dockerfile`: stage `web` (`node:22-slim`, `npm ci`, `npm run build`) → stage `runtime` (`python:3.12-slim`,
  `COPY --from=ghcr.io/astral-sh/uv:<pinned> /uv /bin/uv`, `uv sync --frozen --no-dev --project backend`, copy `frontend/dist`,
  `contracts/schemas`, `data/fixtures`, `eval/results/latest`). Non-root user `app` (uid 10001). Tag = git SHA; `latest` is not used
  for deploys.
- **Rationale**: Single container serves API, WebSocket and static SPA (001 R13); pinned uv + lockfile = reproducible image.

## R7. Percentiles in Application Insights

- **Decision**: Keep OTel histograms for dashboards, **and** emit one structured log record (`tactistream.latency`) per latency
  sample. Exact p50/p95 are computed in KQL with `percentiles()` over the `traces` table (`customDimensions.value_ms`).
- **Rationale**: Azure Monitor stores OTel histograms as pre-aggregated `customMetrics` (count/sum/min/max), from which p95 cannot
  be computed. Per-sample records are cheap at our volume (≤ a few thousand per match) and make the number auditable.
- **Alternatives rejected**: Only Eventhouse percentiles (Fabric is a later, optional dependency; App Insights must stand alone for 007a).

## R8. Trace correlation

- **Decision**: `workflow_span()` opens an OTel span and returns its trace id as the W3C 32-hex `trace_id` used by the agent workflow,
  `AgentTrace`, `InsightPacket.trace_id` and `NarrativeStatus.trace_id`. Model-call spans and history-query spans are children. In
  App Insights the id appears as `operation_Id`. If the span context is invalid (should not happen, SDK provider always installed),
  fall back to `secrets.token_hex(16)` and log a warning.

## R9. Fabric ingestion layout

- **Decision**: Eventstream has **one** destination: Eventhouse table `RawEnvelopes` (JSON mapping, `payload` as `dynamic`). KQL
  **update policies** route by `kind` into typed tables `Events`, `Frames`, `Insights`, `AgentTraces`, `Latency`. Frames are ingested
  in full (10 Hz × ~23 entities ≈ trivial volume); `Frames2Hz()` returns `frame_index % 5 == 0` for dashboards.
- **Rationale**: One connector to configure in the portal; routing logic lives in versioned, reviewable `.kql` files and can be tested
  in the Kusto emulator; Eventstream no-code filters cannot express modulo sampling.
- **Alternatives rejected**: five Eventstream filter destinations (portal-only logic, untestable); 2 Hz filtering before ingest
  (loses data needed for replay audits).
- **Retention**: `RawEnvelopes` soft-delete 14 days; typed tables 365 days; streaming ingestion enabled on `RawEnvelopes` when the
  Eventhouse supports it (lower lag), otherwise queued ingestion (lag recorded by `tactistream-smoke fabric`).

## R10. Fabric capacity availability

- **Decision**: Before 20 Oct, record the Fabric capacity type and end date. If it is a trial ending before 11 Nov 2026, either
  move the workspace to a paid capacity (F2 is sufficient) or apply the stop rule: label Fabric as "used during development" and
  remove it from the live architecture claim. Live judging never depends on Fabric.
- **Record before 20 Oct** (T056): capacity SKU `____`; trial? `____`; end date `____`; workspace `____`.

## R11. Historical evidence store

- **Decision**: `azure-kusto-data[aio]` async client created with `KustoConnectionStringBuilder.with_azure_token_credential(query_uri,
  DefaultAzureCredential())`; calls stored functions `MatchSummary` and `PlayerHistory` with `ClientRequestProperties.set_parameter`
  and `declare query_parameters`; overall `asyncio.wait_for(..., 1.5 s)` plus server timeout `servertimeout=00:00:02`. The managed
  identity is granted **database viewer** on `tactistream` (`.add database tactistream viewers ('aadapp=<client-id>;<tenant-id>')`).
- **Same-match only**: history results are restricted to the current `match_id`; IDs must resolve in the session evidence index, so
  any cited history is still verifiable evidence (constitution I).
- **Alternatives rejected**: querying other matches for "season trends" (no evidence index for them; synthetic matches are not a season).

## R12. Analytics publishing from the API

- **Decision**: `AnalyticsPublisher` is a bounded in-process queue (1000) with one drain task calling `FeedBus.publish`. Synchronous
  `offer_*` methods return immediately. On overflow or publish error the envelope is dropped and counted. The live path (WebSocket
  broadcast) never awaits it.
- **Ingest guard**: live-state consumer ignores `insight`, `agent_trace`, `latency` kinds (shared hub, same partition key).

## R13. Availability through judging

- **Decision**: min replica 1 (no scale to zero); daily uptime workflow until 11 Nov; Azure budget alert (no auto-shutdown); no
  infrastructure changes after 26 Oct except fixes; teardown not before 12 Nov 2026. GitHub disables scheduled workflows only after
  60 days of repository inactivity — not reached in the window.
