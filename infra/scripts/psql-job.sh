#!/usr/bin/env bash
# Runs SQL against the private Postgres from inside the Container Apps
# environment (Postgres has no public access) and prints psql's output.
#
#   infra/scripts/psql-job.sh "select count(*) from users"
#
# The job (caj-fakesnews-psql) is created on first use. It reads the libpq
# connection string from Key Vault (keda-pg-connection): database-url carries
# asyncpg's ?ssl=require, which libpq rejects.
set -euo pipefail

SQL=${1:?usage: psql-job.sh "<sql>"}
RG=${RG:-rg-fakesnews-prod}
JOB=caj-fakesnews-psql
ENV_NAME=cae-fakesnews
IMAGE=docker.io/library/postgres:16-alpine
KV_NAME=$(az keyvault list -g "$RG" --query "[0].name" -o tsv)
IDENTITY_ID=$(az identity show -g "$RG" -n id-fakesnews-apps --query id -o tsv)

if ! az containerapp job show -g "$RG" -n "$JOB" -o none 2>/dev/null; then
  ENV_ID=$(az containerapp env show -g "$RG" -n "$ENV_NAME" --query id -o tsv)
  YAML=$(mktemp --suffix=.yaml)
  cat > "$YAML" <<YAML
location: $(az group show -n "$RG" --query location -o tsv)
identity:
  type: UserAssigned
  userAssignedIdentities:
    "$IDENTITY_ID": {}
properties:
  environmentId: $ENV_ID
  workloadProfileName: Consumption
  configuration:
    triggerType: Manual
    replicaTimeout: 300
    replicaRetryLimit: 0
    manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
    secrets:
      - name: pgconn
        keyVaultUrl: https://${KV_NAME}.vault.azure.net/secrets/keda-pg-connection
        identity: $IDENTITY_ID
  template:
    containers:
      - name: psql
        image: $IMAGE
        command: ["sh", "-c", 'echo "\$SQL_B64" | base64 -d | psql "\$PGCONN" -X -At -v ON_ERROR_STOP=1 -f -']
        env:
          - { name: PGCONN, secretRef: pgconn }
          - { name: SQL_B64, value: "" }
        resources: { cpu: 0.25, memory: 0.5Gi }
YAML
  # On Git Bash, the Windows az CLI needs a Windows path.
  YAML_ARG=$YAML
  command -v cygpath >/dev/null && YAML_ARG=$(cygpath -w "$YAML")
  az containerapp job create -g "$RG" -n "$JOB" --yaml "$YAML_ARG" -o none --only-show-errors
  rm -f "$YAML"
fi

SQL_B64=$(printf '%s' "$SQL" | base64 -w0)
az containerapp job update -g "$RG" -n "$JOB" --set-env-vars "SQL_B64=$SQL_B64" -o none --only-show-errors
# Never run a previous statement: start only once the job holds this SQL.
STORED=$(az containerapp job show -g "$RG" -n "$JOB"   --query "properties.template.containers[0].env[?name=='SQL_B64'].value | [0]" -o tsv)
[[ $STORED == "$SQL_B64" ]] || { echo "job update did not apply the new SQL" >&2; exit 1; }
EXEC=$(az containerapp job start -g "$RG" -n "$JOB" --query name -o tsv)

STATUS=Running
for _ in $(seq 1 40); do
  STATUS=$(az containerapp job execution show -g "$RG" -n "$JOB" --job-execution-name "$EXEC" \
    --query properties.status -o tsv)
  [[ $STATUS == Succeeded || $STATUS == Failed ]] && break
  sleep 5
done

# Console logs reach Log Analytics with a delay of a minute or two.
WS=$(az monitor log-analytics workspace show -g "$RG" -n log-fakesnews --query customerId -o tsv)
QUERY="ContainerAppConsoleLogs_CL | where ContainerGroupName_s startswith '$EXEC' | order by TimeGenerated asc | project Log_s"
for _ in $(seq 1 24); do
  OUT=$(az monitor log-analytics query -w "$WS" --analytics-query "$QUERY" --query "[].Log_s" -o tsv 2>/dev/null || true)
  [[ -n $OUT ]] && break
  sleep 10
done
printf '%s\n' "$OUT"
echo "[$EXEC: $STATUS]" >&2
[[ $STATUS == Succeeded ]]
