// Two user-assigned identities:
// - apps:   used by the container apps and jobs to read Key Vault secrets.
// - deploy: used by GitHub Actions (OIDC, no stored secret) to deploy main.bicep
//           and roll out new images. The university tenant does not allow app
//           registrations, so a managed identity with a federated credential is
//           the only passwordless option.
param location string
param githubRepo string
param githubBranch string

var contributorRoleId = 'b24988ac-6180-42a0-ab88-20f7382dd24c'

resource appsIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-fakesnews-apps'
  location: location
}

resource deployIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-fakesnews-deploy'
  location: location
}

resource githubCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deployIdentity
  name: 'github-main'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepo}:ref:refs/heads/${githubBranch}'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource deployContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, deployIdentity.id, contributorRoleId)
  properties: {
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributorRoleId)
  }
}

output appsIdentityId string = appsIdentity.id
output appsIdentityPrincipalId string = appsIdentity.properties.principalId
output appsIdentityClientId string = appsIdentity.properties.clientId
output deployIdentityClientId string = deployIdentity.properties.clientId
