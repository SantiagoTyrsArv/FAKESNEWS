// arq worker. Scales to zero and is woken by KEDA when Postgres has
// unfinished submissions. The query only counts recent rows, so a stuck case
// (a submission left in a non-terminal status) cannot keep it running.
param location string
param environmentId string
param identityId string
param keyVaultUri string
param image string
param secrets array
param env array
param minReplicas int = 0

var pendingQuery = 'SELECT count(*) FROM submissions WHERE status NOT IN (\'done\',\'failed\') AND created_at > now() - interval \'20 minutes\''

resource worker 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-fakesnews-worker'
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
      secrets: concat(secrets, [
        { name: 'keda-pg-connection', keyVaultUrl: '${keyVaultUri}secrets/keda-pg-connection', identity: identityId }
      ])
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: image
          command: ['uv', 'run', '--frozen', 'arq', 'app.workers.arq_settings.WorkerSettings']
          env: env
          resources: { cpu: json('1.0'), memory: '2Gi' }
          volumeMounts: [{ volumeName: 'whisper-cache', mountPath: '/home/app/.cache' }]
        }
      ]
      volumes: [
        {
          name: 'whisper-cache'
          storageType: 'AzureFile'
          storageName: 'whisper-cache'
          mountOptions: 'uid=10001,gid=10001,dir_mode=0750,file_mode=0640'
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: 1
        cooldownPeriod: 300
        pollingInterval: 15
        rules: minReplicas > 0 ? [] : [
          {
            name: 'pending-submissions'
            custom: {
              type: 'postgresql'
              metadata: {
                targetQueryValue: '1'
                activationTargetQueryValue: '0'
                query: pendingQuery
              }
              auth: [{ secretRef: 'keda-pg-connection', triggerParameter: 'connection' }]
            }
          }
        ]
      }
    }
  }
}
