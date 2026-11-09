#!/usr/bin/env bash
# Proves the Postgres backups restore: a point-in-time restore of
# psql-fakesnews into a throwaway server, a row count of every table on both,
# and a comparison. The throwaway server and job are always deleted, also when
# something fails. Never writes to psql-fakesnews.
#
#   infra/scripts/restore-test.sh
#
# Takes 15-25 minutes and a few cents (a B1ms server for that long). Every 3
# months; record the result in docs/AZURE.md ("Observabilidad").
#
# The restored server keeps the admin login, so the job gets its connection
# string as a secret by value. It goes through a private temp file (--yaml),
# never a command-line argument, and the file is deleted right after use.
set -euo pipefail

RG=${RG:-rg-fakesnews-prod}
SOURCE=psql-fakesnews
TARGET=psql-fakesnews-restoretest
JOB=caj-fakesnews-restoretest
ENV_NAME=cae-fakesnews
IMAGE=docker.io/library/postgres:18-alpine
HERE=$(cd "$(dirname "$0")" && pwd)
YAML=""

cleanup() {
  local code=$?
  set +e
  [[ -n $YAML ]] && rm -f "$YAML"
  echo "Limpieza: borrando $JOB y $TARGET..." >&2
  az containerapp job delete -g "$RG" -n "$JOB" --yes -o none --only-show-errors 2>/dev/null
  if az postgres flexible-server show -g "$RG" -n "$TARGET" -o none 2>/dev/null; then
    az postgres flexible-server delete -g "$RG" -n "$TARGET" --yes -o none --only-show-errors
  fi
  echo "Limpieza hecha." >&2
  exit $code
}
trap cleanup EXIT

KV_NAME=$(az keyvault list -g "$RG" --query "[0].name" -o tsv)
IDENTITY_ID=$(az identity show -g "$RG" -n id-fakesnews-apps --query id -o tsv)
ENV_ID=$(az containerapp env show -g "$RG" -n "$ENV_NAME" --query id -o tsv)
LOCATION=$(az group show -n "$RG" --query location -o tsv)
SOURCE_HOST=$(az postgres flexible-server show -g "$RG" -n "$SOURCE" \
  --query fullyQualifiedDomainName -o tsv)
TARGET_HOST=${SOURCE_HOST/#$SOURCE./$TARGET.}

# libpq keyword string of the admin, pointed at the restored server. Kept in a
# variable only; YAML single quotes escape by doubling.
SRC_CONN=$(az keyvault secret show --vault-name "$KV_NAME" -n keda-pg-connection \
  --query value -o tsv | tr -d '\r\n')
DST_CONN=${SRC_CONN/host=$SOURCE_HOST/host=$TARGET_HOST}
[[ $DST_CONN != "$SRC_CONN" ]] || { echo "keda-pg-connection no tiene host=$SOURCE_HOST" >&2; exit 1; }
unset SRC_CONN
DST_YAML=${DST_CONN//\'/\'\'}
unset DST_CONN

SQL_B64=$(base64 -w0 < "$HERE/row-counts.sql")
YAML=$(mktemp --suffix=.yaml)
chmod 600 "$YAML"
cat > "$YAML" <<YAML
location: $LOCATION
identity:
  type: UserAssigned
  userAssignedIdentities:
    "$IDENTITY_ID": {}
properties:
  environmentId: $ENV_ID
  workloadProfileName: Consumption
  configuration:
    triggerType: Manual
    replicaTimeout: 600
    replicaRetryLimit: 0
    manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
    secrets:
      - name: src
        keyVaultUrl: https://${KV_NAME}.vault.azure.net/secrets/keda-pg-connection
        identity: $IDENTITY_ID
      - name: dst
        value: '$DST_YAML'
  template:
    containers:
      - name: rowcounts
        image: $IMAGE
        # Every line is tagged: Log Analytics does not keep the order of lines
        # that share a timestamp.
        command: ["sh", "-c", 'echo "\$SQL_B64" | base64 -d > /tmp/rc.sql && psql "\$SRC" -X -At -v ON_ERROR_STOP=1 -f /tmp/rc.sql | sed "s/^/src|/" && psql "\$DST" -X -At -v ON_ERROR_STOP=1 -f /tmp/rc.sql | sed "s/^/dst|/"']
        env:
          - { name: SRC, secretRef: src }
          - { name: DST, secretRef: dst }
          - { name: SQL_B64, value: "$SQL_B64" }
        resources: { cpu: 0.25, memory: 0.5Gi }
YAML
unset DST_YAML
YAML_ARG=$YAML
command -v cygpath >/dev/null && YAML_ARG=$(cygpath -w "$YAML")
az containerapp job create -g "$RG" -n "$JOB" --yaml "$YAML_ARG" -o none --only-show-errors
rm -f "$YAML"
YAML=""

# Lets the cleanup be tested without waiting for a restore.
[[ ${RESTORE_TEST_FAIL_AFTER_JOB:-} == 1 ]] && { echo "Fallo provocado (RESTORE_TEST_FAIL_AFTER_JOB)." >&2; exit 1; }

RESTORE_TIME=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
echo "Restaurando $SOURCE a $RESTORE_TIME en $TARGET..." >&2
STARTED=$(date +%s)
az postgres flexible-server restore -g "$RG" --name "$TARGET" --source-server "$SOURCE" \
  --restore-time "$RESTORE_TIME" -o none --only-show-errors
MINUTES=$(( ($(date +%s) - STARTED + 59) / 60 ))
echo "Restaurado en $MINUTES min." >&2

EXEC=$(az containerapp job start -g "$RG" -n "$JOB" --query name -o tsv)
STATUS=Running
for _ in $(seq 1 60); do
  STATUS=$(az containerapp job execution show -g "$RG" -n "$JOB" --job-execution-name "$EXEC" \
    --query properties.status -o tsv)
  [[ $STATUS == Succeeded || $STATUS == Failed ]] && break
  sleep 10
done
[[ $STATUS == Succeeded ]] || { echo "RESTORE-TEST FAIL: el job de conteo terminó en $STATUS" >&2; exit 1; }

WS=$(az monitor log-analytics workspace show -g "$RG" -n log-fakesnews --query customerId -o tsv)
QUERY="ContainerAppConsoleLogs_CL | where ContainerGroupName_s startswith '$EXEC' | project Log_s"
OUT=""
for _ in $(seq 1 30); do
  OUT=$(az monitor log-analytics query -w "$WS" --analytics-query "$QUERY" --query "[].Log_s" -o tsv 2>/dev/null || true)
  grep -q '^src|alembic_version=' <<< "$OUT" && grep -q '^dst|alembic_version=' <<< "$OUT" && break
  sleep 10
done

compare() {
  local out=$1 ok=0 line name n m
  declare -A src dst
  while IFS='|' read -r side name n; do
    [[ $side == src ]] && src[$name]=$n
    [[ $side == dst ]] && dst[$name]=$n
  # "alembic_version=<rev>" becomes its own key: alembic_version is also a
  # table, with a row count of its own.
  done < <(grep -E '^(src|dst)\|' <<< "$out" | sed 's/^\(src\|dst\)|alembic_version=\(.*\)$/\1|alembic_revision|\2/')
  [[ ${#src[@]} -gt 1 ]] || { echo "Sin salida de producción"; return 1; }
  for name in "${!src[@]}"; do
    n=${src[$name]}
    m=${dst[$name]-}
    if [[ -z $m ]]; then
      echo "falta en la restauración: $name"; ok=1
    elif [[ $name == alembic_revision ]]; then
      [[ $m == "$n" ]] || { echo "revisión de alembic distinta: $n frente a $m"; ok=1; }
    elif (( m > n )) || (( n > 0 && m == 0 )); then
      echo "$name: producción $n, restaurado $m"; ok=1
    fi
  done
  for name in "${!dst[@]}"; do
    [[ -n ${src[$name]-} ]] || { echo "sobra en la restauración: $name"; ok=1; }
  done
  return $ok
}

grep -E '^(src|dst)\|' <<< "$OUT" | sort
if REPORT=$(compare "$OUT"); then
  echo "RESTORE-TEST OK ($(date -u +%Y-%m-%d), restauración en $MINUTES min)"
else
  printf '%s\n' "$REPORT"
  echo "RESTORE-TEST FAIL"
  exit 1
fi
