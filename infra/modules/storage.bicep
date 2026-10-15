@description('Name of the storage account (3-24 lowercase alphanumeric).')
param name string

@description('Azure region.')
param location string

@description('Resource tags.')
param tags {
  *: string
}

resource account 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: name
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: account
  name: 'default'
}

resource datasets 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobService
  name: 'datasets'
  properties: {
    publicAccess: 'None'
  }
}

resource artifacts 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobService
  name: 'artifacts'
  properties: {
    publicAccess: 'None'
  }
}

resource checkpoints 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
  parent: blobService
  name: 'checkpoints'
  properties: {
    publicAccess: 'None'
  }
}

@description('Blob endpoint, e.g. https://<name>.blob.core.windows.net/.')
output blobEndpoint string = account.properties.primaryEndpoints.blob

@description('Resource id of the storage account.')
output id string = account.id
