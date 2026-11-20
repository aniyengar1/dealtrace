#!/bin/bash
# Verifies the Supabase copy of the 10 DealTrace tables against local:
# row counts per table, plus 3 sanity queries (headline_stats medians,
# deal_metrics canonical count, the splunk row). Read-only on both
# sides. Never echoes connection strings.
#
#   ./scripts/verify_supabase.sh

set -uo pipefail
set +x

cd "$(dirname "$0")/.."

_redact() {
  sed -E 's#postgres(ql)?://[^[:space:]]*#postgres://[REDACTED]#g'
}

if [ ! -f .env ]; then
  echo "ERROR: .env not found (needed for local DATABASE_URL)" >&2
  exit 1
fi
if [ ! -f .env.supabase ]; then
  echo "ERROR: .env.supabase not found" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
# shellcheck disable=SC1091
source .env.supabase
set +a

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL not set in .env" >&2
  exit 1
fi
if [ -z "${SUPABASE_DATABASE_URL:-}" ]; then
  echo "ERROR: SUPABASE_DATABASE_URL not set in .env.supabase" >&2
  exit 1
fi

DEALTRACE_TABLES=(deals deal_candidates deal_metrics extraction_runs events proposals valuations paragraphs headline_stats schema_migrations)
ERR_LOG="$(mktemp -t dealtrace_verify_err).log"
trap 'rm -f "$ERR_LOG"' EXIT

run_local() { psql "$DATABASE_URL" -tAc "$1" 2>"$ERR_LOG" || { echo "ERROR: local query failed:" >&2; _redact < "$ERR_LOG" >&2; exit 1; }; }
run_remote() { psql "$SUPABASE_DATABASE_URL" -tAc "$1" 2>"$ERR_LOG" || { echo "ERROR: Supabase query failed:" >&2; _redact < "$ERR_LOG" >&2; exit 1; }; }

ALL_PASS=true

echo "==> Row counts (local vs Supabase):"
printf "%-20s %12s %12s %8s\n" "table" "local" "supabase" "status"
for t in "${DEALTRACE_TABLES[@]}"; do
  LOCAL_COUNT=$(run_local "SELECT count(*) FROM $t" | tr -d ' ')
  REMOTE_COUNT=$(run_remote "SELECT count(*) FROM $t" | tr -d ' ')
  if [ "$LOCAL_COUNT" = "$REMOTE_COUNT" ]; then
    STATUS="PASS"
  else
    STATUS="FAIL"
    ALL_PASS=false
  fi
  printf "%-20s %12s %12s %8s\n" "$t" "$LOCAL_COUNT" "$REMOTE_COUNT" "$STATUS"
done

echo ""
echo "==> Sanity check 1: headline_stats medians match"
printf "%-45s %14s %14s %8s\n" "stat" "local_median" "supabase_median" "status"
STAT_NAMES=$(run_local "SELECT name FROM headline_stats ORDER BY name")
while IFS= read -r stat_name; do
  [ -z "$stat_name" ] && continue
  LOCAL_MEDIAN=$(run_local "SELECT median FROM headline_stats WHERE name = '$stat_name'" | tr -d ' ')
  REMOTE_MEDIAN=$(run_remote "SELECT median FROM headline_stats WHERE name = '$stat_name'" | tr -d ' ')
  if [ "$LOCAL_MEDIAN" = "$REMOTE_MEDIAN" ]; then
    STATUS="PASS"
  else
    STATUS="FAIL"
    ALL_PASS=false
  fi
  printf "%-45s %14s %14s %8s\n" "$stat_name" "$LOCAL_MEDIAN" "$REMOTE_MEDIAN" "$STATUS"
done <<< "$STAT_NAMES"

echo ""
echo "==> Sanity check 2: deal_metrics canonical count = 964"
LOCAL_CANONICAL=$(run_local "SELECT count(*) FROM deal_metrics WHERE is_canonical" | tr -d ' ')
REMOTE_CANONICAL=$(run_remote "SELECT count(*) FROM deal_metrics WHERE is_canonical" | tr -d ' ')
if [ "$LOCAL_CANONICAL" = "964" ] && [ "$REMOTE_CANONICAL" = "964" ]; then
  STATUS="PASS"
else
  STATUS="FAIL"
  ALL_PASS=false
fi
printf "%-45s %14s %14s %8s\n" "canonical deal count (expect 964)" "$LOCAL_CANONICAL" "$REMOTE_CANONICAL" "$STATUS"

echo ""
echo "==> Sanity check 3: splunk row exists"
LOCAL_SPLUNK=$(run_local "SELECT count(*) FROM deals WHERE slug = 'splunk'" | tr -d ' ')
REMOTE_SPLUNK=$(run_remote "SELECT count(*) FROM deals WHERE slug = 'splunk'" | tr -d ' ')
if [ "$LOCAL_SPLUNK" = "1" ] && [ "$REMOTE_SPLUNK" = "1" ]; then
  STATUS="PASS"
else
  STATUS="FAIL"
  ALL_PASS=false
fi
printf "%-45s %14s %14s %8s\n" "splunk row exists (expect 1/1)" "$LOCAL_SPLUNK" "$REMOTE_SPLUNK" "$STATUS"

echo ""
if [ "$ALL_PASS" = true ]; then
  echo "==> PASS: all checks match"
  exit 0
else
  echo "==> FAIL: one or more checks mismatched"
  exit 1
fi
