#!/usr/bin/env bash
# Dumps the Railway Postgres (custom format) from inside its own container over
# `railway ssh`, so the database never needs a public TCP proxy, and uploads
# the dump to the pgdump file share for restore-azure.sh.
#
#   infra/scripts/dump-railway.sh
#
# Needs an SSH key registered with Railway (railway ssh keys add). The SSH user
# is the Postgres service's id, as printed by
# `railway ssh config -s Postgres --dry-run`.
set -euo pipefail

RG=${RG:-rg-fakesnews-prod}
PG_SSH_USER=${PG_SSH_USER:-88a6b477-b822-4ba4-9ac0-b386dc622cf9}
SSH_KEY=${SSH_KEY:-$HOME/.ssh/id_ed25519}
DUMP=$(mktemp --suffix=.dump)
trap 'rm -f "$DUMP"' EXIT

START=$(date +%s)
# No tty (-T): the custom-format dump is binary and streams through stdout.
ssh -T -o BatchMode=yes -i "$SSH_KEY" "$PG_SSH_USER@ssh.railway.com" \
  'pg_dump -U "$PGUSER" -d "$PGDATABASE" -Fc --no-owner --no-privileges' > "$DUMP"

# A custom-format archive starts with the magic bytes "PGDMP".
[[ $(head -c 5 "$DUMP") == PGDMP ]] || { echo "not a pg_dump archive" >&2; exit 1; }
echo "dump: $(wc -c < "$DUMP") bytes in $(( $(date +%s) - START ))s"

ACCOUNT=$(az storage account list -g "$RG" --query "[0].name" -o tsv)
UPLOAD=$DUMP
command -v cygpath >/dev/null && UPLOAD=$(cygpath -w "$DUMP")
az storage file upload --account-name "$ACCOUNT" --auth-mode key --share-name pgdump \
  --source "$UPLOAD" --path railway.dump -o none --only-show-errors
echo "uploaded to $ACCOUNT/pgdump/railway.dump in $(( $(date +%s) - START ))s total"
