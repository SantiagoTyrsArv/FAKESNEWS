// Private Postgres (VNet only). B1ms is covered by the 12-month free services.
param location string
param pgSubnetId string
param pgPrivateDnsZoneId string
@secure()
param adminPassword string

var adminLogin = 'fakesnews_admin'

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: 'psql-fakesnews'
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: adminLogin
    administratorLoginPassword: adminPassword
    storage: { storageSizeGB: 32, autoGrow: 'Disabled' }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    network: {
      delegatedSubnetResourceId: pgSubnetId
      privateDnsZoneArmResourceId: pgPrivateDnsZoneId
      publicNetworkAccess: 'Disabled'
    }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: 'fakesnews'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

output pgFqdn string = server.properties.fullyQualifiedDomainName
output pgAdminLogin string = adminLogin
output pgDatabase string = database.name
