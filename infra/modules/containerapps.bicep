@description('Name of the Container Apps environment.')
param environmentName string

@description('Name of the container app.')
param appName string

@description('Azure region.')
param location string

@description('Resource tags.')
param tags {
  *: string
}

@description('Name of the Log Analytics workspace receiving container logs.')
param logAnalyticsWorkspaceName string

@description('Resource id of the user-assigned managed identity.')
param identityId string

@description('Client id of the user-assigned managed identity (AZURE_CLIENT_ID).')
param identityClientId string

@description('Container registry login server.')
param registryLoginServer string

@description('Application Insights connection string, stored as a container app secret.')
@secure()
param appInsightsConnectionString string

@description('Container image; empty uses a public placeholder until the first azd deploy.')
param imageName string

@description('Event Hubs namespace host name.')
param eventHubsNamespaceFqdn string

@description('Event hub name.')
param eventHubName string

@description('Blob endpoint of the storage account.')
param storageAccountUrl string

@description('Foundry project endpoint.')
param foundryProjectEndpoint string

@description('Foundry model deployment name.')
param foundryModelDeployment string

@description('Feed bus used by the app (TACTISTREAM_BUS).')
@allowed([
  'memory'
  'eventhubs'
])
param bus string

@description('Agent runtime used by the app (TACTISTREAM_AGENTS).')
@allowed([
  'off'
  'scripted'
  'foundry'
])
param agents string

@description('Deployment environment label (TACTISTREAM_ENVIRONMENT).')
param deploymentEnvironment string

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
  }
}

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: appName
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: registryLoginServer
          identity: identityId
        }
      ]
      secrets: [
        {
          name: 'appinsights-connection-string'
          value: appInsightsConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'tactistream'
          image: empty(imageName) ? 'mcr.microsoft.com/k8se/quickstart:latest' : imageName
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'TACTISTREAM_BUS', value: bus }
            { name: 'TACTISTREAM_AGENTS', value: agents }
            { name: 'EVENTHUBS_FULLY_QUALIFIED_NAMESPACE', value: eventHubsNamespaceFqdn }
            { name: 'EVENTHUBS_NAME', value: eventHubName }
            { name: 'EVENTHUBS_CONSUMER_GROUP', value: 'live-state' }
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'FOUNDRY_MODEL_DEPLOYMENT', value: foundryModelDeployment }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
            { name: 'AZURE_CLIENT_ID', value: identityClientId }
            { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storageAccountUrl }
            { name: 'TACTISTREAM_ARTIFACT_STORE', value: 'blob' }
            { name: 'TACTISTREAM_ANALYTICS_PUBLISH', value: 'on' }
            { name: 'TACTISTREAM_HISTORY', value: 'memory' }
            { name: 'TACTISTREAM_HISTORY_TIMEOUT_MS', value: '1500' }
            { name: 'TACTISTREAM_STATIC_DIR', value: '/app/frontend/dist' }
            { name: 'TACTISTREAM_CONTRACTS_DIR', value: '/app/contracts/schemas' }
            { name: 'TACTISTREAM_ENVIRONMENT', value: deploymentEnvironment }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              periodSeconds: 3
              failureThreshold: 20
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              periodSeconds: 10
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              periodSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

@description('Public host name of the container app.')
output fqdn string = app.properties.configuration.ingress.fqdn

@description('Name of the container app.')
output name string = app.name
