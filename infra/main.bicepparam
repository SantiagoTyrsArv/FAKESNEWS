using 'main.bicep'

var subscriptionId = '49005ae0-4cff-40d3-a743-fd384d62fd85'
var resourceGroupName = 'rg-fakesnews-prod'
var keyVaultName = 'kv-fakesnews-4q4yxz5r'

param budgetContactEmail = 'santif.arevalo@gmail.com'

param pgAdminPassword = az.getSecret(subscriptionId, resourceGroupName, keyVaultName, 'pg-admin-password')
