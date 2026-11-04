// Public FastAPI app. Scales to zero; the web reaches it through the Vercel
// /api proxy (API_PROXY_TARGET).
param location string
param environmentId string
param identityId string
param image string
param secrets array
param env array
param minReplicas int = 0

resource api 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-fakesnews-api'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'api'
          image: image
          env: concat(env, [{ name: 'PORT', value: '8000' }])
          resources: { cpu: json('0.5'), memory: '1Gi' }
          probes: [
            {
              type: 'Startup'
              httpGet: { path: '/health', port: 8000 }
              periodSeconds: 2
              failureThreshold: 30
            }
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000 }
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health/ready', port: 8000 }
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 2
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '20' } } }]
      }
    }
  }
}

output apiFqdn string = api.properties.configuration.ingress.fqdn
