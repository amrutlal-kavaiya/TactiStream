@description('Name of the user-assigned managed identity.')
param name string

@description('Azure region.')
param location string

@description('Resource tags.')
param tags {
  *: string
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: name
  location: location
  tags: tags
}

@description('Resource id of the identity.')
output id string = identity.id

@description('Object id of the identity service principal.')
output principalId string = identity.properties.principalId

@description('Client id of the identity (AZURE_CLIENT_ID).')
output clientId string = identity.properties.clientId
