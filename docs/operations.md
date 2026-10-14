# TactiStream operations runbook (v1, 007a)

Status: written before the first deployment. Values marked `____` are filled after `azd up` (research.md R1) and from
`infra/scripts/inventory.sh`. 009 finalizes this document.

## Resources

Resource group `rg-tactistream-prod`, region `____` (default `eastus2`). Names carry a stable suffix
`<token> = uniqueString(subscription, resource group, location)`.

| Resource | Type | Name | SKU / size | Purpose |
|---|---|---|---|---|
| Managed identity | `Microsoft.ManagedIdentity/userAssignedIdentities` | `id-tactistream-<token>` | — | ACR pull, Event Hubs, Blob, Foundry (no keys) |
| Log Analytics | `Microsoft.OperationalInsights/workspaces` | `log-tactistream-<token>` | PerGB2018, 30 d | Container logs, App Insights store |
| Application Insights | `Microsoft.Insights/components` | `appi-tactistream-<token>` | workspace-based | Traces, latency logs, metrics |
| Container registry | `Microsoft.ContainerRegistry/registries` | `crtactistream<token>` | Basic, admin disabled | `tactistream:<git-sha>` images |
| Event Hubs | `Microsoft.EventHub/namespaces` | `evhns-tactistream-<token>` | Standard, 1 TU | Hub `tactistream-feed` (2 partitions, 7 d), groups `live-state`, `fabric` |
| Storage | `Microsoft.Storage/storageAccounts` | `sttacti<token>` | StorageV2 Standard_LRS, shared key off | Containers `datasets`, `artifacts`, `checkpoints` |
| Container Apps environment | `Microsoft.App/managedEnvironments` | `cae-tactistream-<token>` | Consumption | — |
| Container app | `Microsoft.App/containerApps` | `tactistream` | 1 vCPU / 2 GiB, 1 replica | API + WebSocket + SPA |
| Budget | `Microsoft.Consumption/budgets` | `budget-tactistream` | 100 / month | Email alerts 50/80/100 % actual, 100 % forecast |
| Foundry role | role assignment on existing account `____` (RG `____`) | — | Azure AI User | Narrative model calls |

Refresh from the live resource group (the output is the source of truth for architecture claims):

```bash
infra/scripts/inventory.sh rg-tactistream-prod <foundry-rg> <foundry-account> > docs/deployment-inventory.json
```

## URLs

| What | URL |
|---|---|
| App (judges) | `____` (`SERVICE_WEB_URI` from `azd`) |
| Health | `<app>/healthz` → `{"status":"ok","bus":"eventhubs",…}` |
| Application Insights | Azure portal → `appi-tactistream-<token>`; saved queries in `infra/appinsights/queries.kql` |

## Deploy

- First provisioning: `specs/007-azure-platform/quickstart.md` §2 (`azd up`).
- Every push to `main`: `.github/workflows/deploy.yml` (OIDC login → build/push `tactistream:<sha>` → `az containerapp update`
  → wait for `healthState == Healthy` → `tactistream-smoke deployed`). If the smoke fails after the update, the workflow
  restores the previously running image.
- Manual smoke: `cd backend && uv run tactistream-smoke deployed --base-url <app>` (add `--soak-s 300` for the WebSocket soak).

## Rollback

```bash
az containerapp revision list -n tactistream -g rg-tactistream-prod -o table
az containerapp update -n tactistream -g rg-tactistream-prod --image <acr>.azurecr.io/tactistream:<previous-sha>
```

## Uptime check

`.github/workflows/uptime.yml` runs daily at 03:00 UTC (and on dispatch) through 2026-11-11, executing the deployed smoke
against repository variable `APP_URL`. A failed run emails the repository owner; record every miss in the incident log below.

## Budget

Resource-group budget `budget-tactistream`, 100 per month in the billing currency, email alerts to `ALERT_EMAIL` at 50 %, 80 %
and 100 % actual and 100 % forecast. There is no automatic shutdown: shutting down would break judging access.

## Telemetry

After a demo match: `infra/scripts/check-telemetry.sh rg-tactistream-prod <appinsights-name>` runs every named query in
`infra/appinsights/queries.kql` and fails if any returns no rows.

## Availability commitment

- The app stays reachable for judges through **10 Nov 2026, Pacific Time** (one always-ready replica, no scale to zero).
- No infrastructure changes after 26 Oct 2026 except fixes.
- Teardown **not before 12 Nov 2026**.

## Stop rule

Any service that is not deployed **and** used by the running app is removed from architecture claims (README, docs, video).
`inventory.sh` output is the evidence; Fabric items are added by 007b only once they are running (see `infra/fabric/SETUP.md`).

## Incident log

| Date (UTC) | Symptom | Cause | Fix | Duration |
|---|---|---|---|---|
