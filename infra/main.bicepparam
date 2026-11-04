using 'main.bicep'

var subscriptionId = '49005ae0-4cff-40d3-a743-fd384d62fd85'
var resourceGroupName = 'rg-fakesnews-prod'
var kvName = 'kv-fakesnews-4q4yxz5r'

param budgetContactEmail = 'santif.arevalo@gmail.com'

param keyVaultName = kvName

param pgAdminPassword = az.getSecret(subscriptionId, resourceGroupName, kvName, 'pg-admin-password')

// Same values as the Railway services (2026-11-04). Secrets live in Key Vault.
param appSettings = [
  { name: 'ENVIRONMENT', value: 'production' }
  { name: 'ANTHROPIC_MODEL', value: 'claude-sonnet-5' }
  { name: 'COOKIE_PATH_PREFIX', value: '/api' }
  { name: 'CORS_ORIGINS', value: '["https://fakesnews.vercel.app"]' }
  { name: 'TRUSTED_PROXY_HOPS', value: '1' }
]

// A cold start measured 30 s (2026-11-04), over the 25 s budget behind the
// Vercel proxy, so the API keeps one replica warm. The worker scales to zero.
param apiMinReplicas = 1
