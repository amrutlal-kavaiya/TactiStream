@description('Name of the Log Analytics workspace.')
param workspaceName string

@description('Name of the Application Insights component.')
param appInsightsName string

@description('Azure region.')
param location string

@description('Resource tags.')
param tags {
  *: string
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
  }
}

@description('Resource id of the Log Analytics workspace.')
output workspaceId string = workspace.id

@description('Customer (workspace) id of the Log Analytics workspace.')
output workspaceCustomerId string = workspace.properties.customerId

@description('Name of the Application Insights component; the connection string is read by main.bicep, never output.')
output appInsightsName string = appInsights.name

@description('Resource id of the Application Insights component.')
output appInsightsId string = appInsights.id
