// FakesNews API on Azure. Deployed by .github/workflows/infra.yml (and by hand
// the first time). Resources that need role assignments are in bootstrap.bicep.
param location string = resourceGroup().location

@description('Budget start, first day of a month. Fixed: a budget cannot change it later.')
param budgetStartDate string = '2026-11-01'
param budgetAmount int = 10
param budgetContactEmail string

@secure()
@description('Read from Key Vault (pg-admin-password) in main.bicepparam.')
param pgAdminPassword string

@description('Created by bootstrap.bicep.')
param keyVaultName string

@description('Tag of ghcr.io/santiagotyrsarv/fakesnews-api to run (the commit SHA after the first deploy).')
param imageTag string = 'bootstrap'

@description('Non-secret app settings, same values as on Railway, as container env entries ({ name, value }).')
param appSettings array = []

@description('Set to 1 if a scale-to-zero check in the migration plan fails.')
param apiMinReplicas int = 0
param workerMinReplicas int = 0

var image = 'ghcr.io/santiagotyrsarv/fakesnews-api:${imageTag}'

// Secrets the api and the worker get, read by reference from Key Vault.
// database-url-app connects as fakesnews_app, which can read and write rows
// but not change the schema.
var secretEnvMap = {
  DATABASE_URL: 'database-url-app'
  REDIS_URL: 'redis-url'
  JWT_SECRET_KEY: 'jwt-secret-key'
  TOTP_SECRET_ENCRYPTION_KEY: 'totp-secret-encryption-key'
  GEMINI_API_KEY: 'gemini-api-key'
  TAVILY_API_KEY: 'tavily-api-key'
  API_PROXY_SECRET: 'api-proxy-secret'
}
// Migrations create and alter tables, so they keep the admin login (database-url).
var migrateSecretEnvMap = union(secretEnvMap, { DATABASE_URL: 'database-url' })
// Known at compile time (unlike vault.properties.vaultUri), so it can feed loops.
var keyVaultUri = 'https://${keyVaultName}${az.environment().suffixes.keyvaultDns}/'
var appSecrets = [
  for item in items(secretEnvMap): {
    name: item.value
    keyVaultUrl: '${keyVaultUri}secrets/${item.value}'
    identity: appsIdentity.id
  }
]
var migrateSecrets = [
  for item in items(migrateSecretEnvMap): {
    name: item.value
    keyVaultUrl: '${keyVaultUri}secrets/${item.value}'
    identity: appsIdentity.id
  }
]
var secretEnv = [for item in items(secretEnvMap): { name: item.key, secretRef: item.value }]
var migrateSecretEnv = [for item in items(migrateSecretEnvMap): { name: item.key, secretRef: item.value }]
// Passed through untouched: a loop would make ARM evaluate values such as
// CORS_ORIGINS='["..."]' as template expressions.
var appEnv = concat(secretEnv, appSettings)
var migrateEnv = concat(migrateSecretEnv, appSettings)

resource appsIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'id-fakesnews-apps'
}

resource alertsIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'id-fakesnews-alerts'
}

module network 'modules/network.bicep' = {
  name: 'network'
  params: { location: location }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: { location: location }
}

module alerts 'modules/alerts.bicep' = {
  name: 'alerts'
  params: {
    location: location
    workspaceName: monitoring.outputs.workspaceName
    contactEmail: budgetContactEmail
    identityId: alertsIdentity.id
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: { location: location }
}

module budget 'modules/budget.bicep' = {
  name: 'budget'
  params: {
    amount: budgetAmount
    startDate: budgetStartDate
    contactEmail: budgetContactEmail
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    location: location
    pgSubnetId: network.outputs.pgSubnetId
    pgPrivateDnsZoneId: network.outputs.pgPrivateDnsZoneId
    adminPassword: pgAdminPassword
  }
}

module environment 'modules/containerapps-env.bicep' = {
  name: 'containerapps-env'
  params: {
    location: location
    acaSubnetId: network.outputs.acaSubnetId
    logWorkspaceName: monitoring.outputs.workspaceName
    storageAccountName: storage.outputs.storageAccountName
    whisperShareName: storage.outputs.whisperShareName
  }
}

module redis 'modules/redis.bicep' = {
  name: 'redis'
  params: {
    location: location
    environmentId: environment.outputs.environmentId
    identityId: appsIdentity.id
    keyVaultUri: keyVaultUri
  }
}

module migrate 'modules/migrate-job.bicep' = {
  name: 'migrate-job'
  params: {
    location: location
    environmentId: environment.outputs.environmentId
    identityId: appsIdentity.id
    image: image
    secrets: migrateSecrets
    env: migrateEnv
  }
}

module api 'modules/api.bicep' = {
  name: 'api'
  dependsOn: [redis, postgres]
  params: {
    location: location
    environmentId: environment.outputs.environmentId
    identityId: appsIdentity.id
    image: image
    secrets: appSecrets
    env: appEnv
    minReplicas: apiMinReplicas
  }
}

module worker 'modules/worker.bicep' = {
  name: 'worker'
  dependsOn: [redis, postgres]
  params: {
    location: location
    environmentId: environment.outputs.environmentId
    identityId: appsIdentity.id
    keyVaultUri: keyVaultUri
    image: image
    secrets: appSecrets
    env: appEnv
    minReplicas: workerMinReplicas
  }
}

output acaSubnetId string = network.outputs.acaSubnetId
output pgFqdn string = postgres.outputs.pgFqdn
output apiFqdn string = api.outputs.apiFqdn
output environmentName string = environment.outputs.environmentName
output storageAccountName string = storage.outputs.storageAccountName
