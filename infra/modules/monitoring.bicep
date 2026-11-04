param location string

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-fakesnews'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    // Hard daily ingestion cap: a log storm cannot eat the credits.
    workspaceCapping: { dailyQuotaGb: json('0.15') }
  }
}

output workspaceName string = workspace.name
