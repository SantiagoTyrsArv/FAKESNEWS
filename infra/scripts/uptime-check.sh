#!/usr/bin/env bash
# Checks that the site and the API answer, as a visitor would. Used by
# .github/workflows/uptime.yml; runs the same locally:
#
#   infra/scripts/uptime-check.sh [base_url]
#
# The API scales to zero and a cold start takes ~30 s, so each request gets
# 90 s and one retry a minute later before it counts as down.
set -uo pipefail

BASE=${1:-https://fakesnews.vercel.app}
BASE=${BASE%/}
RETRY_WAIT=${RETRY_WAIT:-60}

# check <path> <text the body must contain, or empty>
check() {
  local url="$BASE$1" want=$2 body code attempt
  for attempt in 1 2; do
    body=$(mktemp)
    code=$(curl -sSL -o "$body" -w '%{http_code}' --max-time 90 "$url" 2>/dev/null) || code=000
    if [ "$code" = 200 ] && { [ -z "$want" ] || grep -q "$want" "$body"; }; then
      rm -f "$body"
      echo "OK   $url"
      return 0
    fi
    rm -f "$body"
    echo "FAIL $url (HTTP $code, intento $attempt)"
    [ "$attempt" = 1 ] && sleep "$RETRY_WAIT"
  done
  return 1
}

status=0
check / "" || status=1
check /api/health/ready '"ready"' || status=1
exit $status
