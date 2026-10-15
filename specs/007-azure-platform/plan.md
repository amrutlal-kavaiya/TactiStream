# Implementation Plan: Azure Platform

**Branch**: `007-azure-platform` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-azure-platform/spec.md`

## Summary

Deliver the claimed Microsoft architecture as real, tested infrastructure in two drops. **007a (15 Oct)**: Bicep modules +
`azd` provision Log Analytics/App Insights, ACR, a single-replica WebSocket-capable Container App with a user-assigned managed
identity, Event Hubs (`tactistream-feed`, 2 partitions, `live-state` + `fabric`), Storage (`datasets`, `artifacts`,
`checkpoints`) and least-privilege roles including the existing Foundry resource; a multi-stage root `Dockerfile` serves the SPA
from FastAPI; GitHub Actions deploys by OIDC and runs a WebSocket smoke; `BlobArtifactStore` persists checkpoints and archives;
OpenTelemetry instruments, per-sample latency logs and workflow-span trace correlation make latency, fallbacks and tokens
visible in Application Insights. **007b (20–21 Oct)**: the API publishes `insight`/`agent_trace`/`latency` envelopes through a
non-blocking `AnalyticsPublisher`; Fabric Eventstream (consumer group `fabric`) lands everything in Eventhouse `RawEnvelopes`,
KQL update policies route by kind into typed tables, and saved functions support summaries and evaluation; a `HistoryStore`
(in-memory or Eventhouse, 1.5 s timeout, as-of filtered, event IDs only) backs the Analyst's read-only `get_history` tool.

## Technical Context

**Language/Version**: Bicep (Azure CLI ≥ 2.60 bundled), Python 3.12, TypeScript 5 (unchanged), KQL, YAML (GitHub Actions)

**Primary Dependencies**: azure-storage-blob[aio], azure-identity, azure-kusto-data[aio], azure-monitor-opentelemetry,
opentelemetry-sdk, azure-eventhub (from 001), websockets (smoke client; already via uvicorn[standard]), typer;
GitHub Actions `azure/login@v2`, `actions/checkout@v4`, `docker/setup-buildx-action@v3`

**Storage**: Azure Blob (artifacts), Eventhouse KQL database `tactistream` (analytics/history), in-memory live state (unchanged)

**Testing**: pytest (unit, integration, `infra` marker for compiled-Bicep assertions, `live` marker for Azure/Fabric), OTel
in-memory span/metric/log exporters, fake Blob and Kusto clients; `az bicep build`/lint, `az deployment group what-if`; deployed
smoke CLI; Playwright skeleton e2e against `BASE_URL`; optional Kusto emulator (`kustainer`) test marked `kusto`

**Target Platform**: Azure Container Apps (Consumption, Linux amd64), Azure Event Hubs Standard, Azure Storage, Microsoft Fabric
Real-Time Intelligence

**Project Type**: Web application + infrastructure

**Performance Goals**: Deploy ≤ 12 min push-to-smoke; history tool ≤ 1.5 s; analytics publish adds 0 awaited work to the live path;
fast overlay p95 target ≤ 2 s on the deployed app (measured by 008)

**Constraints**: no secrets in git or container env (except App Insights connection string as a Container App secret); OIDC only
in CI; min = max = 1 replica; Fabric never on the live path; availability through 10 Nov 2026 PT

**Scale/Scope**: 1 replica, 1 match per session, ≤ 10 viewers per match; ~10 resources in one resource group + 1 role on the
Foundry resource; 1 Eventstream, 1 Eventhouse DB, 7 tables

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Evidence before narrative | PASS | `get_history` returns event IDs + counts only; IDs not resolvable in the session evidence index as of the snapshot are dropped, so history claims remain checkable by Verifier and output checks |
| II Provenance | PASS | Envelopes keep `source.kind`; Eventhouse tables carry `SourceKind`; no real-world data introduced |
| III Deterministic core, bounded agents | PASS | Fabric consumes a separate consumer group; `AnalyticsPublisher` is fire-and-forget; history tool is Analyst-only with 1.5 s timeout inside the 8 s deadline; architecture test forbids fast-path imports of `tactistream.history` |
| IV Contract-first | PASS | New `latency_sample.schema.json` + `LatencySample` model with contract test; Eventhouse columns fixed in `contracts/eventhouse-tables.md` and checked by a static test |
| V Test-first | PASS | Every code task is preceded by a failing test; infra tasks are preceded by compiled-template assertions and verified by what-if + deployed smoke |
| VI Measure, don't claim | PASS | Per-sample latency logs enable exact percentiles; fallbacks/timeouts recorded, never dropped; inventory script + stop rule keep architecture claims to deployed services |
| VII Scope discipline | PASS | One replica, Consumption plan, no AKS/Cosmos; Fabric items manual (documented) rather than an extra IaC toolchain |

Post-design re-check: PASS. One justified exception recorded under Complexity Tracking (Listen-only SAS key for Fabric).

## Project Structure

### Documentation (this feature)

```text
specs/007-azure-platform/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
└── contracts/
    └── eventhouse-tables.md     # RawEnvelopes + typed tables, update policies, functions
```

### Source Code (repository root)

```text
azure.yaml                                   azd: infra/main.bicep + service "web" (docker, containerapp)
Dockerfile · .dockerignore                   Node 22 build → python:3.12-slim + uv runtime
bicepconfig.json                             linter: all rules warning→error
.github/workflows/
├── deploy.yml                               OIDC → build/push ACR → containerapp update → smoke
├── uptime.yml                               daily /healthz + WS smoke until 2026-11-11
└── ci.yml                                   (exists) + job `infra` (bicep build/lint + pytest -m infra)
infra/
├── main.bicep · main.parameters.json
├── modules/
│   ├── monitoring.bicep                     Log Analytics + workspace-based App Insights
│   ├── registry.bicep                       ACR Basic, admin disabled
│   ├── containerapps.bicep                  environment + app (1 replica, ingress, probes, UAMI, env, secrets)
│   ├── eventhubs.bicep                      Standard ns, hub tactistream-feed, CGs live-state + fabric, fabric-listen rule
│   ├── storage.bicep                        account + containers datasets/artifacts/checkpoints
│   ├── identity.bicep                       user-assigned managed identity
│   ├── roles.bicep                          AcrPull, EH Data Sender/Receiver, Blob Data Contributor
│   ├── foundry-role.bicep                   Foundry user role on existing account (cross-RG scope)
│   └── budget.bicep                         RG budget + email alerts
├── appinsights/queries.kql                  named saved queries
├── fabric/
│   ├── tables.kql · mappings.kql · functions.kql
│   └── SETUP.md                             portal steps + verification
└── scripts/
    ├── setup-github-oidc.sh                 app registration + federated creds + role assignments
    ├── check-telemetry.sh                   runs every named query, fails on 0 rows
    └── inventory.sh                         JSON inventory for docs claims
docs/operations.md                           runbook (finalized by 009)
backend/
├── pyproject.toml                           + azure-storage-blob[aio], azure-kusto-data[aio]; markers infra, kusto
├── src/tactistream/
│   ├── settings.py                          + artifact_store, analytics_publish, history, history_timeout_ms, … (data-model)
│   ├── contracts/latency.py                 LatencySample
│   ├── storage/blob.py                      BlobArtifactStore
│   ├── storage/factory.py                   build_artifact_store(settings)
│   ├── history/__init__.py
│   ├── history/base.py                      HistoryStore, HistorySummary, EventRef, HistoryUnavailable
│   ├── history/memory.py                    InMemoryHistoryStore
│   ├── history/eventhouse.py                KustoHistoryStore
│   ├── history/tool.py                      GetHistoryArgs, HistoryToolResult, get_history, GET_HISTORY_TOOL_SPEC
│   ├── history/factory.py                   build_history_store(settings)
│   ├── transport/analytics_publisher.py     AnalyticsPublisher
│   ├── telemetry/otel.py                    (exists) always-on SDK TracerProvider, resource attrs
│   ├── telemetry/instruments.py             Instruments, get_instruments()
│   ├── telemetry/correlation.py             workflow_span(), current_trace_id()
│   ├── telemetry/latency.py                 (exists) + log record + publisher hook
│   ├── smoke/deployed.py · smoke/fabric.py  new smoke commands
│   └── api/app.py                           (exists) lifespan wiring, SPA fallback, history + publisher DI
└── tests/
    ├── unit/{test_blob_store,test_artifact_factory,test_analytics_publisher,test_instruments,test_correlation,
    │         test_latency_logging,test_history_memory,test_history_eventhouse,test_history_tool,test_ingest_ignores_analytics,
    │         test_smoke_deployed,test_spa_fallback,test_settings_platform}.py
    ├── contract/test_latency_sample.py
    ├── architecture/test_fast_path_imports.py
    ├── infra/{test_bicep_template.py,test_kql_scripts.py,test_queries_kql.py}
    ├── integration/{test_workflow_telemetry.py,test_history_in_workflow.py,test_analytics_in_session.py}
    ├── fixtures/history_golden.json
    ├── kusto/test_kql_emulator.py           (@pytest.mark.kusto, optional)
    └── live/{test_blob_live,test_history_eventhouse,test_fabric_ingest}.py   (@pytest.mark.live)
```

**Structure Decision**: Infrastructure lives under `infra/` (registry layout); Python additions stay in the registry's `storage/`,
`history/`, `telemetry/`, `transport/`, `smoke/` packages. Compiled-Bicep and KQL static tests live under `backend/tests/infra`
so they run with the existing pytest toolchain.

## Key Design Notes

- **Bicep composition** (`main.bicep`): `identity` → `monitoring` → `registry`, `eventhubs`, `storage` → `roles` (needs principal id +
  resource ids) → `containerapps` (needs identity, ACR login server, endpoints, App Insights connection string as secret) →
  `foundry-role` with `scope: resourceGroup(foundryResourceGroup)` → `budget`. Role assignment names are
  `guid(scope.id, principalId, roleDefinitionId)` for idempotency. Role definition IDs: AcrPull `7f951dda-4ed3-4680-a7ca-43fe172d538d`,
  Event Hubs Data Sender `2b629674-e913-4c01-ae53-ef4638d8f975`, Data Receiver `a638d3c7-ab3a-418d-83e6-5f17a39d4fde`, Storage Blob
  Data Contributor `ba92f5b4-2d11-453d-a403-e96b0029c9fe`, Foundry default Azure AI User `53ca6127-db72-4b80-b1b0-d745d6d5456d`
  (param; verify in portal at deploy and record in research R1).
- **Identity split**: the user-assigned identity is created in `identity.bicep` (not inside `containerapps.bicep`) so `roles.bicep`
  grants AcrPull before the app's first ACR-backed revision; `containerapps.bicep` only attaches it.
- **First deploy chicken-and-egg**: the container app is created with a public placeholder image
  (`mcr.microsoft.com/k8se/quickstart:latest`) when param `imageName` is empty; `azd deploy` / `deploy.yml` then switch to the ACR image.
- **Compiled-template tests** (`tests/infra/test_bicep_template.py`): run `az bicep build --stdout`, load ARM JSON, resolve modules,
  and assert: `minReplicas == maxReplicas == 1`; ingress `targetPort 8000`, `external true`, `transport auto`; three probes on `/healthz`;
  hub `partitionCount 2`; consumer groups exactly `{live-state, fabric}`; containers exactly `{datasets, artifacts, checkpoints}`;
  storage `allowSharedKeyAccess false`; ACR `adminUserEnabled false`; role definition id set equals FR-007. Skipped with reason when
  `az` is missing locally; required in CI job `infra`.
- **SPA + static**: `create_app` mounts `StaticFiles(directory=settings.static_dir)` under `/assets` and registers a catch-all GET
  returning `index.html` for paths not starting with `/api`, `/ws`, `/healthz`.
- **Lifespan wiring** (`api/app.py`): build `ArtifactStore`, `HistoryStore | None`, `AnalyticsPublisher`; start publisher drain task;
  on shutdown `aclose()` publisher, close Blob/Kusto clients and `DefaultAzureCredential`.
- **Ingest guard**: `MatchState.apply` (or 003's `Ingestor`) returns `StateDelta(ignored=True)` for `insight|agent_trace|latency`
  envelopes — a three-line change with its own test (`test_ingest_ignores_analytics.py`).
- **Instruments** use `metrics.get_meter("tactistream")`; logs use the stdlib `logging` logger `tactistream.latency` with `extra=`
  attributes (Azure Monitor exporter maps them to `customDimensions`).
- **Correlation**: `workflow_span` uses `tracer.start_as_current_span("tactistream.explain_moment", attributes={match_id, moment_id,
  config})`; `format(span.get_span_context().trace_id, "032x")`.
- **History tool spec** (registered in 004's tool registry):
  `GET_HISTORY_TOOL_SPEC = ToolSpec(name="get_history", description="Read-only counts and event IDs from earlier in this match, as of the current snapshot.", args_model=GetHistoryArgs, handler=get_history)`.
- **KustoHistoryStore query**: `declare query_parameters(match_id:string, as_of_ms:long); MatchSummary(match_id, as_of_ms)` with
  `ClientRequestProperties` parameters and `servertimeout`; rows mapped to `HistorySummary`; any exception → `HistoryUnavailable("error")`,
  `asyncio.TimeoutError` → `HistoryUnavailable("timeout")`.
- **Smoke deployed**: `httpx.AsyncClient` + `websockets.connect(wss://…/ws/matches/{id})`; sequence: healthz → POST session → WS
  snapshot (≤ 5 s) → POST control play → first `event` (≤ 15 s) → POST control reset; prints a one-line JSON summary for CI logs.
- **Uptime workflow** guard: `if [ "$(date -u +%F)" \> "2026-11-11" ]; then echo "window over"; exit 0; fi`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| One SAS key (`fabric-listen`, Listen-only, hub-scoped) despite "Entra everywhere" (constitution security rule) | Fabric Eventstream's Event Hubs source may require a shared access key for the cloud connection | Root namespace key grants send/manage; skipping Fabric removes a claimed architecture component. The key is stored only in the Fabric connection, never in git or app config, and is deleted if Entra auth is available (T061) |
