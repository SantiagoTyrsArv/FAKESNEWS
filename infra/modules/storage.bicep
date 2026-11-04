// File shares mounted by container apps and jobs:
// - whisper-cache: the worker's ~/.cache, so a cold start does not download
//   the Whisper model again.
// - pgdump: hand-off point for the Railway dump during the migration.
param location string

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'stfakesnews${take(uniqueString(resourceGroup().id), 8)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  identity: { type: 'SystemAssigned' }
  properties: {
    encryption: {
      keySource: 'Microsoft.Storage'
      services: {
        file: { enabled: true, keyType: 'Account' }
        blob: { enabled: true, keyType: 'Account' }
      }
    }
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    // Container Apps mounts Azure Files over SMB with the account key.
    allowSharedKeyAccess: true
    supportsHttpsTrafficOnly: true
  }
}

resource files 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: account
  name: 'default'
}

resource whisperShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: files
  name: 'whisper-cache'
  properties: { shareQuota: 5 }
}

resource dumpShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: files
  name: 'pgdump'
  properties: { shareQuota: 5 }
}

output storageAccountName string = account.name
output whisperShareName string = whisperShare.name
output dumpShareName string = dumpShare.name
