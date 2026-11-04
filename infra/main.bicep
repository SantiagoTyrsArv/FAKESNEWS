// FakesNews API on Azure. Deployed by .github/workflows/infra.yml (and by hand
// the first time). Resources that need role assignments are in bootstrap.bicep.
param location string = resourceGroup().location

@description('Budget start, first day of a month. Fixed: a budget cannot change it later.')
param budgetStartDate string = '2026-11-01'
param budgetAmount int = 10
param budgetContactEmail string

module network 'modules/network.bicep' = {
  name: 'network'
  params: { location: location }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: { location: location }
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

output acaSubnetId string = network.outputs.acaSubnetId
output storageAccountName string = storage.outputs.storageAccountName
