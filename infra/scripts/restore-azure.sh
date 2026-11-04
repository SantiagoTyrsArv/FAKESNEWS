#!/usr/bin/env bash
# Restores pgdump/railway.dump into the private Azure Postgres from a one-off
# Container Apps job (Postgres has no public access). The restore runs in a
# single transaction and stops at the first error, so it either fully
# replaces the database contents or leaves them untouched.
#
#   infra/scripts/restore-azure.sh
set -euo pipefail

RG=${RG:-rg-fakesnews-prod}
JOB=caj-fakesnews-restore
ENV_NAME=cae-fakesnews
IMAGE=docker.io/library/postgres:18-alpine
KV_NAME=$(az keyvault list -g "$RG" --query "[0].name" -o tsv)
IDENTITY_ID=$(az identity show -g "$RG" -n id-fakesnews-apps --query id -o tsv)
ENV_ID=$(az containerapp env show -g "$RG" -n "$ENV_NAME" --query id -o tsv)

# Recreated every time, so it always runs the command below.
az containerapp job delete -g "$RG" -n "$JOB" --yes -o none --only-show-errors 2>/dev/null || true

YAML=$(mktemp --suffix=.yaml)
trap 'rm -f "$YAML"' EXIT
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
    replicaTimeout: 1200
    replicaRetryLimit: 0
    manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
    secrets:
      - name: pgconn
        keyVaultUrl: https://${KV_NAME}.vault.azure.net/secrets/keda-pg-connection
        identity: $IDENTITY_ID
  template:
    containers:
      - name: restore
        image: $IMAGE
        command: ["sh", "-c", 'pg_restore --clean --if-exists --no-owner --no-privileges --single-transaction --exit-on-error -d "\$PGCONN" /dump/railway.dump && echo RESTORE-OK']
        env:
          - { name: PGCONN, secretRef: pgconn }
        resources: { cpu: 0.5, memory: 1Gi }
        volumeMounts:
          - { volumeName: dump, mountPath: /dump }
    volumes:
      - { name: dump, storageType: AzureFile, storageName: pgdump }
YAML
YAML_ARG=$YAML
command -v cygpath >/dev/null && YAML_ARG=$(cygpath -w "$YAML")
az containerapp job create -g "$RG" -n "$JOB" --yaml "$YAML_ARG" -o none --only-show-errors

START=$(date +%s)
EXEC=$(az containerapp job start -g "$RG" -n "$JOB" --query name -o tsv --only-show-errors)
STATUS=Running
for _ in $(seq 1 120); do
  STATUS=$(az containerapp job execution show -g "$RG" -n "$JOB" --job-execution-name "$EXEC" \
    --query properties.status -o tsv --only-show-errors)
  [[ $STATUS == Succeeded || $STATUS == Failed ]] && break
  sleep 5
done
echo "[$EXEC: $STATUS in $(( $(date +%s) - START ))s]"
[[ $STATUS == Succeeded ]]
