// Consumption-only Container Apps environment inside the VNet, with the
// Azure Files shares registered as environment storage.
param location string
param acaSubnetId string
param logWorkspaceName string
param storageAccountName string
param whisperShareName string
param dumpShareName string

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logWorkspaceName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-fakesnews'
  location: location
  properties: {
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
    vnetConfiguration: {
      infrastructureSubnetId: acaSubnetId
      internal: false
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
  }
}

resource whisperStorage 'Microsoft.App/managedEnvironments/storages@2025-01-01' = {
  parent: environment
  name: 'whisper-cache'
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: whisperShareName
      accessMode: 'ReadWrite'
    }
  }
}

resource dumpStorage 'Microsoft.App/managedEnvironments/storages@2025-01-01' = {
  parent: environment
  name: 'pgdump'
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: dumpShareName
      accessMode: 'ReadWrite'
    }
  }
}

output environmentId string = environment.id
output environmentName string = environment.name
