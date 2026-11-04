// Redis as a small always-on container. It only holds short-lived state (the
// arq queue, used mfa jti values, rate-limit counters), so no persistence.
param location string
param environmentId string
param identityId string
param keyVaultUri string

resource redis 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-fakesnews-redis'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      // Internal TCP ingress, reachable only inside the environment, and Redis
      // requires a password. Client certificates apply to HTTP ingress only.
      ingress: {
        external: false
        transport: 'tcp'
        targetPort: 6379
        exposedPort: 6379
      }
      secrets: [
        { name: 'redis-password', keyVaultUrl: '${keyVaultUri}secrets/redis-password', identity: identityId }
      ]
    }
    template: {
      containers: [
        {
          name: 'redis'
          image: 'docker.io/library/redis:7-alpine@sha256:8da19c7399dca900c6822a1cf30f9d2285585e2c4b457ff4095b0f4500054d3f'
          command: ['sh', '-c']
          args: ['exec redis-server --requirepass "$REDIS_PASSWORD" --save "" --appendonly no']
          env: [{ name: 'REDIS_PASSWORD', secretRef: 'redis-password' }]
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
}
