@description('Name of the Event Hubs namespace.')
param namespaceName string

@description('Azure region.')
param location string

@description('Resource tags.')
param tags {
  *: string
}

resource namespace 'Microsoft.EventHub/namespaces@2026-01-01' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    minimumTlsVersion: '1.2'
  }
}

resource hub 'Microsoft.EventHub/namespaces/eventhubs@2026-01-01' = {
  parent: namespace
  name: 'tactistream-feed'
  properties: {
    partitionCount: 2
    messageRetentionInDays: 7
  }
}

resource liveState 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2026-01-01' = {
  parent: hub
  name: 'live-state'
}

resource fabric 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2026-01-01' = {
  parent: hub
  name: 'fabric'
}

// Listen-only, hub-scoped key used solely by the Fabric Eventstream connection (research R4).
resource fabricListen 'Microsoft.EventHub/namespaces/eventhubs/authorizationRules@2026-01-01' = {
  parent: hub
  name: 'fabric-listen'
  properties: {
    rights: [
      'Listen'
    ]
  }
}

@description('Namespace host name, e.g. <name>.servicebus.windows.net.')
output namespaceFqdn string = '${namespace.name}.servicebus.windows.net'

@description('Resource id of the namespace.')
output namespaceId string = namespace.id

@description('Name of the event hub.')
output hubName string = hub.name
