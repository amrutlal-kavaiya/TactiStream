@description('Name of the existing Foundry (AI Services) account in this resource group.')
param foundryAccountName string

@description('Role granted on the Foundry account; default Azure AI User (verify at deploy, research R1).')
param foundryRoleDefinitionId string = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

@description('Object id of the managed identity service principal.')
param principalId string

@description('Resource id of the managed identity; keys the role assignment name.')
param identityId string

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, identityId, foundryRoleDefinitionId)
  scope: foundry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryRoleDefinitionId)
  }
}
