// One-time, owner-run deployment: everything that needs role assignments.
// The GitHub deploy identity only has Contributor, which cannot create role
// assignments, so these resources live outside main.bicep.
//
//   az deployment group create -g rg-fakesnews-prod -f infra/bootstrap.bicep \
//     -p adminObjectId=$(az ad signed-in-user show --query id -o tsv)
param location string = resourceGroup().location
param adminObjectId string
// This repository's OIDC tokens use GitHub's immutable-ID subject format
// (owner@ownerId/repo@repoId), so a renamed or recreated repo cannot match.
param githubRepo string = 'SantiagoTyrsArv@197986351/FAKESNEWS@1393968255'
param githubBranch string = 'main'

module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    githubRepo: githubRepo
    githubBranch: githubBranch
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    location: location
    appsIdentityPrincipalId: identity.outputs.appsIdentityPrincipalId
    adminObjectId: adminObjectId
  }
}

output keyVaultName string = keyVault.outputs.keyVaultName
output appsIdentityClientId string = identity.outputs.appsIdentityClientId
output deployIdentityClientId string = identity.outputs.deployIdentityClientId
