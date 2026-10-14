@description('Name of the container registry (alphanumeric).')
param name string

@description('Azure region.')
param location string

@description('Resource tags.')
param tags {
  *: string
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

@description('Registry login server, e.g. <name>.azurecr.io.')
output loginServer string = registry.properties.loginServer

@description('Resource id of the registry.')
output id string = registry.id

@description('Name of the registry.')
output name string = registry.name
