#!/usr/bin/env bash
# JSON inventory of the deployed resource group plus the Foundry deployments (FR-016), used to keep architecture
# claims to deployed services only. Exits non-zero if the Container App, Event Hubs namespace or storage account
# is missing.
#
# Usage: infra/scripts/inventory.sh <resource-group> [foundry-resource-group foundry-account-name]
#        (Foundry values default to $FOUNDRY_RESOURCE_GROUP and $FOUNDRY_ACCOUNT_NAME)
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <resource-group> [foundry-resource-group foundry-account-name]" >&2
  exit 2
fi
rg=$1
foundry_rg=${2:-${FOUNDRY_RESOURCE_GROUP:-}}
foundry_account=${3:-${FOUNDRY_ACCOUNT_NAME:-}}

resources=$(az resource list -g "$rg" \
  --query '[].{type: type, name: name, location: location, sku: sku.name}' -o json)

if [[ -n "$foundry_rg" && -n "$foundry_account" ]]; then
  foundry_region=$(az cognitiveservices account show -g "$foundry_rg" -n "$foundry_account" --query location -o tsv)
  deployments=$(az cognitiveservices account deployment list -g "$foundry_rg" -n "$foundry_account" \
    --query "[].{deployment: name, model: properties.model.name, version: properties.model.version, region: '$foundry_region'}" \
    -o json)
else
  echo "warning: Foundry account not given; foundry_deployments is empty" >&2
  deployments='[]'
fi

missing=()
for type in Microsoft.App/containerApps Microsoft.EventHub/namespaces Microsoft.Storage/storageAccounts; do
  if [[ "$(jq --arg t "$type" '[.[] | select((.type | ascii_downcase) == ($t | ascii_downcase))] | length' <<<"$resources")" == 0 ]]; then
    missing+=("$type")
  fi
done

jq -n --arg rg "$rg" --argjson resources "$resources" --argjson deployments "$deployments" \
  '{resource_group: $rg, resources: $resources, foundry_deployments: $deployments}'

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "missing required resources in $rg: ${missing[*]}" >&2
  exit 1
fi
