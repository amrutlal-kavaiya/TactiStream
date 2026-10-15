#!/usr/bin/env bash
# Idempotent GitHub Actions OIDC setup (research R5): app registration + service principal, federated credentials for
# the main branch and the production environment, AcrPush on the registry and Contributor on the resource group.
# Prints the `gh variable set` commands; repository variables are identifiers, never secrets.
#
# Usage: infra/scripts/setup-github-oidc.sh <github-owner> <github-repo> <resource-group> [app-name]
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "usage: $0 <github-owner> <github-repo> <resource-group> [app-name]" >&2
  exit 2
fi
owner=$1
repo=$2
rg=$3
app_name=${4:-gh-tactistream-deploy}

subscription_id=$(az account show --query id -o tsv)
tenant_id=$(az account show --query tenantId -o tsv)
rg_id=$(az group show -n "$rg" --query id -o tsv)
acr_name=$(az acr list -g "$rg" --query '[0].name' -o tsv)
acr_id=$(az acr list -g "$rg" --query '[0].id' -o tsv)
app_url=$(az containerapp show -n tactistream -g "$rg" --query 'properties.configuration.ingress.fqdn' -o tsv)
if [[ -z "$acr_name" || -z "$app_url" ]]; then
  echo "resource group $rg has no container registry or container app 'tactistream'; run azd up first" >&2
  exit 1
fi

app_id=$(az ad app list --display-name "$app_name" --query '[0].appId' -o tsv)
if [[ -z "$app_id" ]]; then
  app_id=$(az ad app create --display-name "$app_name" --query appId -o tsv)
  echo "created app registration $app_name ($app_id)" >&2
fi
sp_id=$(az ad sp list --filter "appId eq '$app_id'" --query '[0].id' -o tsv)
if [[ -z "$sp_id" ]]; then
  sp_id=$(az ad sp create --id "$app_id" --query id -o tsv)
  echo "created service principal $sp_id" >&2
fi

ensure_federated_credential() {
  local name=$1 subject=$2
  if [[ -n "$(az ad app federated-credential list --id "$app_id" --query "[?name=='$name'].name" -o tsv)" ]]; then
    return
  fi
  az ad app federated-credential create --id "$app_id" --parameters "$(
    printf '{"name":"%s","issuer":"https://token.actions.githubusercontent.com","subject":"%s","audiences":["api://AzureADTokenExchange"]}' \
      "$name" "$subject"
  )" >/dev/null
  echo "created federated credential $name ($subject)" >&2
}
ensure_federated_credential gh-main "repo:$owner/$repo:ref:refs/heads/main"
ensure_federated_credential gh-production "repo:$owner/$repo:environment:production"

ensure_role() {
  local role=$1 scope=$2
  if [[ -n "$(az role assignment list --assignee "$sp_id" --role "$role" --scope "$scope" --query '[0].id' -o tsv)" ]]; then
    return
  fi
  az role assignment create --assignee-object-id "$sp_id" --assignee-principal-type ServicePrincipal \
    --role "$role" --scope "$scope" >/dev/null
  echo "assigned $role on $scope" >&2
}
ensure_role AcrPush "$acr_id"
ensure_role Contributor "$rg_id"

cat <<EOF
gh variable set AZURE_CLIENT_ID --repo $owner/$repo --body $app_id
gh variable set AZURE_TENANT_ID --repo $owner/$repo --body $tenant_id
gh variable set AZURE_SUBSCRIPTION_ID --repo $owner/$repo --body $subscription_id
gh variable set ACR_NAME --repo $owner/$repo --body $acr_name
gh variable set CONTAINERAPP_NAME --repo $owner/$repo --body tactistream
gh variable set RESOURCE_GROUP --repo $owner/$repo --body $rg
gh variable set APP_URL --repo $owner/$repo --body https://$app_url
EOF
