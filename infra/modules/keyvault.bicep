// Key Vault with RBAC. Secret values never pass through Bicep or GitHub: they
// are written once with `az keyvault secret set` and the container apps read
// them by reference through the apps identity.
param location string
param appsIdentityPrincipalId string
@description('Object id of the person who writes the secrets (az ad signed-in-user show --query id -o tsv).')
param adminObjectId string

var secretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var secretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-fakesnews-${take(uniqueString(resourceGroup().id), 8)}'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    // Lets main.bicepparam read pg-admin-password with az.getSecret().
    enabledForTemplateDeployment: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    // Irreversible: once on, it cannot be turned off. Deleted secrets and the
    // vault itself can be recovered for 7 days and nobody can purge them sooner.
    enablePurgeProtection: true
    // Public endpoint on purpose: access is RBAC-only (no access policies),
    // and Container Apps Key Vault references need a private endpoint
    // (~7 USD/month) once the firewall is closed.
    publicNetworkAccess: 'Enabled'
  }
}

resource appsCanRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, appsIdentityPrincipalId, secretsUserRoleId)
  scope: vault
  properties: {
    principalId: appsIdentityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUserRoleId)
  }
}

resource adminCanWrite 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, adminObjectId, secretsOfficerRoleId)
  scope: vault
  properties: {
    principalId: adminObjectId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsOfficerRoleId)
  }
}

output keyVaultName string = vault.name
output keyVaultUri string = vault.properties.vaultUri
