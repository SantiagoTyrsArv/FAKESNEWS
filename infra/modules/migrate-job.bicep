// Runs `alembic upgrade head` with the new image before every rollout (the
// equivalent of Railway's preDeployCommand). Started by api-deploy.yml.
param location string
param environmentId string
param identityId string
param image string
param secrets array
param env array

resource migrate 'Microsoft.App/jobs@2025-01-01' = {
  name: 'caj-fakesnews-migrate'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'migrate'
          image: image
          command: ['uv', 'run', '--frozen', 'alembic', 'upgrade', 'head']
          env: env
          resources: { cpu: json('0.5'), memory: '1Gi' }
        }
      ]
    }
  }
}
