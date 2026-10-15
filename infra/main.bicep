targetScope = 'resourceGroup'

@description('azd environment name; tags every resource.')
param environmentName string

@description('Region for every resource in this resource group.')
param location string = resourceGroup().location

@description('Resource group of the existing Foundry (AI Services) account.')
param foundryResourceGroup string

@description('Name of the existing Foundry (AI Services) account.')
param foundryAccountName string

@description('Role granted on the Foundry account; default Azure AI User.')
param foundryRoleDefinitionId string = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

@description('Foundry project endpoint (FOUNDRY_PROJECT_ENDPOINT).')
param foundryProjectEndpoint string

@description('Foundry model deployment name (FOUNDRY_MODEL_DEPLOYMENT).')
param foundryModelDeployment string

@description('Address receiving budget alerts.')
param alertEmail string

@description('Monthly budget amount in the billing currency.')
param monthlyBudget int = 100

@description('First day of the budget period (yyyy-MM-dd); fixed so re-provisioning never moves it.')
param budgetStartDate string = '2026-10-01'

@description('Container image; empty uses a public placeholder until the first azd deploy.')
param imageName string = ''

@description('Feed bus used by the app (TACTISTREAM_BUS).')
@allowed([
  'memory'
  'eventhubs'
])
param bus string = 'eventhubs'

@description('Agent runtime used by the app (TACTISTREAM_AGENTS).')
@allowed([
  'off'
  'scripted'
  'foundry'
])
param agents string = 'foundry'

@description('Suffix that keeps globally unique names stable for this resource group.')
var token = uniqueString(subscription().id, resourceGroup().id, location)

@description('Tags applied to every resource.')
var tags = {
  'azd-env-name': environmentName
  project: 'tactistream'
}

@description('Resource names, fixed before deployment so role assignments and what-if can use them.')
var names = {
  identity: 'id-tactistream-${token}'
  workspace: 'log-tactistream-${token}'
  appInsights: 'appi-tactistream-${token}'
  registry: 'crtactistream${token}'
  eventHubs: 'evhns-tactistream-${token}'
  storage: 'sttacti${token}'
  environment: 'cae-tactistream-${token}'
  app: 'tactistream'
  budget: 'budget-tactistream'
}

@description('Resource id of the managed identity, known before deployment.')
var identityId = resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', names.identity)

module identity 'modules/identity.bicep' = {
  params: {
    name: names.identity
    location: location
    tags: tags
  }
}

module monitoring 'modules/monitoring.bicep' = {
  params: {
    workspaceName: names.workspace
    appInsightsName: names.appInsights
    location: location
    tags: tags
  }
}

module registry 'modules/registry.bicep' = {
  params: {
    name: names.registry
    location: location
    tags: tags
  }
}

module eventHubs 'modules/eventhubs.bicep' = {
  params: {
    namespaceName: names.eventHubs
    location: location
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  params: {
    name: names.storage
    location: location
    tags: tags
  }
}

module roles 'modules/roles.bicep' = {
  params: {
    principalId: identity.outputs.principalId
    identityId: identityId
    registryName: names.registry
    eventHubsNamespaceName: names.eventHubs
    storageAccountName: names.storage
  }
  dependsOn: [
    registry
    eventHubs
    storage
  ]
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: names.appInsights
}

module containerApps 'modules/containerapps.bicep' = {
  params: {
    environmentName: names.environment
    appName: names.app
    location: location
    tags: tags
    logAnalyticsWorkspaceName: names.workspace
    identityId: identity.outputs.id
    identityClientId: identity.outputs.clientId
    registryLoginServer: registry.outputs.loginServer
    appInsightsConnectionString: appInsights.properties.ConnectionString
    imageName: imageName
    eventHubsNamespaceFqdn: eventHubs.outputs.namespaceFqdn
    eventHubName: eventHubs.outputs.hubName
    storageAccountUrl: storage.outputs.blobEndpoint
    foundryProjectEndpoint: foundryProjectEndpoint
    foundryModelDeployment: foundryModelDeployment
    bus: bus
    agents: agents
    deploymentEnvironment: 'production'
  }
  dependsOn: [
    monitoring
    roles
  ]
}

module foundryRole 'modules/foundry-role.bicep' = {
  scope: resourceGroup(foundryResourceGroup)
  params: {
    foundryAccountName: foundryAccountName
    foundryRoleDefinitionId: foundryRoleDefinitionId
    principalId: identity.outputs.principalId
    identityId: identityId
  }
}

module budget 'modules/budget.bicep' = {
  params: {
    name: names.budget
    monthlyBudget: monthlyBudget
    alertEmail: alertEmail
    startDate: budgetStartDate
  }
}

@description('Registry endpoint azd pushes the web image to.')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.outputs.loginServer

@description('Name of the container app (azd service web).')
output SERVICE_WEB_NAME string = containerApps.outputs.name

@description('Public URL of the app.')
output SERVICE_WEB_URI string = 'https://${containerApps.outputs.fqdn}'

@description('Event Hubs namespace host name.')
output EVENTHUBS_FULLY_QUALIFIED_NAMESPACE string = eventHubs.outputs.namespaceFqdn

@description('Blob endpoint of the storage account.')
output AZURE_STORAGE_ACCOUNT_URL string = storage.outputs.blobEndpoint

@description('Name of the Application Insights component.')
output APPINSIGHTS_NAME string = monitoring.outputs.appInsightsName

@description('Client id of the managed identity.')
output MANAGED_IDENTITY_CLIENT_ID string = identity.outputs.clientId
