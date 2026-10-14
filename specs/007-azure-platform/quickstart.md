# Quickstart: 007 Azure Platform

## Prerequisites

- Azure CLI ≥ 2.60 with Bicep (`az bicep install`), Azure Developer CLI (`azd`) ≥ 1.10, Docker, uv, Node 22.
- Owner (or Contributor + User Access Administrator) on the target subscription/resource group.
- The existing Foundry resource name, its resource group, and the model deployment name (from 001 research R5).

## 1. Validate templates locally (no Azure changes)

```bash
az bicep build --file infra/main.bicep --stdout > /dev/null   # compile; linter warnings fail via bicepconfig.json
cd backend && uv run pytest tests/infra -m "infra"            # compiled-template assertions (replicas, roles, hub, containers)
```

## 2. First provisioning with azd

```bash
azd auth login
azd env new tactistream-prod
azd env set AZURE_LOCATION eastus2                 # record final choice in research.md R1
azd env set FOUNDRY_RESOURCE_GROUP <rg-of-foundry>
azd env set FOUNDRY_ACCOUNT_NAME <foundry-account>
azd env set FOUNDRY_PROJECT_ENDPOINT <https://…/api/projects/…>
azd env set FOUNDRY_MODEL_DEPLOYMENT <deployment-name>
azd env set ALERT_EMAIL <you@example.com>
az deployment group what-if -g rg-tactistream-prod -f infra/main.bicep -p infra/main.parameters.json   # review before first up
azd up                                             # provisions infra + builds Dockerfile + deploys service "web"
```

Expected: `azd` prints `SERVICE_WEB_URI=https://tactistream.<hash>.<region>.azurecontainerapps.io`.

## 3. Smoke the deployment

```bash
cd backend
uv run tactistream-smoke deployed --base-url "$SERVICE_WEB_URI"
# healthz ok (bus=eventhubs, agents=foundry) · session created · snapshot in 0.4 s · first event in 3.1 s · PASS
cd ../frontend && BASE_URL="$SERVICE_WEB_URI" npx playwright test tests/e2e/skeleton.spec.ts --repeat-each=5
```

## 4. Wire GitHub Actions (OIDC)

```bash
infra/scripts/setup-github-oidc.sh <github-owner> TactiStream rg-tactistream-prod
# creates app registration gh-tactistream-deploy, federated credentials (main branch + production environment),
# assigns AcrPush (ACR) + Contributor (RG), then prints the gh commands below
gh variable set AZURE_CLIENT_ID --body <appId>
gh variable set AZURE_TENANT_ID --body <tenantId>
gh variable set AZURE_SUBSCRIPTION_ID --body <subId>
gh variable set ACR_NAME --body <acr>
gh variable set CONTAINERAPP_NAME --body tactistream
gh variable set RESOURCE_GROUP --body rg-tactistream-prod
gh variable set APP_URL --body "$SERVICE_WEB_URI"
```

Push to `main` → `deploy.yml` builds `tactistream:<sha>`, updates the app, runs the smoke.

## 5. Telemetry check (after one demo match)

```bash
infra/scripts/check-telemetry.sh rg-tactistream-prod <appinsights-name>   # runs every query in infra/appinsights/queries.kql
```

## 6. Fabric (007b, 20–21 Oct)

Follow `infra/fabric/SETUP.md` (Eventhouse + KQL DB `tactistream`, run `tables.kql` → `mappings.kql` → `functions.kql`,
Eventstream with consumer group `fabric`, viewer grant for the managed identity). Then:

```bash
azd env set FABRIC_KUSTO_QUERY_URI https://<eventhouse>.kusto.fabric.microsoft.com
azd env set TACTISTREAM_HISTORY eventhouse && azd provision    # updates container app env vars
cd backend && uv run tactistream-smoke fabric                  # probe latency envelope found in Latency; prints lag
uv run pytest -m live tests/live/test_history_eventhouse.py
```

## 7. Inventory for documentation claims

```bash
infra/scripts/inventory.sh rg-tactistream-prod > docs/deployment-inventory.json   # consumed by 009 docs/architecture.md
```

## Rollback

```bash
az containerapp revision list -n tactistream -g rg-tactistream-prod -o table
az containerapp update -n tactistream -g rg-tactistream-prod --image <acr>.azurecr.io/tactistream:<previous-sha>
```
