@description('Object id of the managed identity service principal.')
param principalId string

@description('Resource id of the managed identity; keys the role assignment names so they are known before deployment.')
param identityId string

@description('Name of the container registry.')
param registryName string

@description('Name of the Event Hubs namespace.')
param eventHubsNamespaceName string

@description('Name of the storage account.')
param storageAccountName string

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: registryName
}

resource namespace 'Microsoft.EventHub/namespaces@2026-01-01' existing = {
  name: eventHubsNamespaceName
}

resource account 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: storageAccountName
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identityId, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: registry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
  }
}

resource eventHubsSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(namespace.id, identityId, '2b629674-e913-4c01-ae53-ef4638d8f975')
  scope: namespace
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '2b629674-e913-4c01-ae53-ef4638d8f975'
    )
  }
}

resource eventHubsReceiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(namespace.id, identityId, 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde')
  scope: namespace
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'a638d3c7-ab3a-418d-83e6-5f17a39d4fde'
    )
  }
}

resource blobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, identityId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: account
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
  }
}
