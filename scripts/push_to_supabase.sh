#!/bin/bash
# Copies the 10 DealTrace tables (plus the 2 enum types they depend on)
# from local Postgres to Supabase. Read-only against local -- pg_dump
# only, never a write or schema change on the local side, since local
# Postgres must stay untouched while earnings locks are in progress on
# the same server tonight. Never touches the 14 earnings/Crosscheck
# tables (companies, earnings_*, guidance_*, hurdle_*) -- in particular
# earnings_live_predictions, the live prediction ledger, is never
# referenced here at all.
#
# Idempotent: drops and recreates these exact 10 tables on Supabase
# every run (via pg_dump --clean --if-exists), safe to re-run after a
# spot-check fix. The 2 enum types are created only if missing (enum
# definitions don't change between runs, so there's nothing to drop).
#
#   ./scripts/push_to_supabase.sh
#
# Requires .env (local DATABASE_URL) and .env.supabase
# (SUPABASE_DATABASE_URL) in the repo root. Never echoes either --
# `set +x` stays in effect throughout, and every error path redacts
# the connection string before printing anything.

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

# Dependency order doesn't matter for -t (pg_dump sorts it out), this
# order is just for readable row-count output later.
DEALTRACE_TABLES=(deals deal_candidates deal_metrics extraction_runs events proposals valuations paragraphs headline_stats schema_migrations)

TABLE_ARGS=()
for t in "${DEALTRACE_TABLES[@]}"; do
  TABLE_ARGS+=(-t "$t")
done

DUMP_FILE="$(mktemp -t dealtrace_push).sql"
ERR_LOG="$(mktemp -t dealtrace_push_err).log"
trap 'rm -f "$DUMP_FILE" "$ERR_LOG"' EXIT

echo "==> Dumping ${#DEALTRACE_TABLES[@]} DealTrace tables from local Postgres (read-only)..."
if ! pg_dump "$DATABASE_URL" --no-owner --no-privileges --clean --if-exists "${TABLE_ARGS[@]}" > "$DUMP_FILE" 2>"$ERR_LOG"; then
  echo "ERROR: pg_dump failed:" >&2
  _redact < "$ERR_LOG" >&2
  exit 1
fi

# pg_dump --clean emits `DROP POLICY IF EXISTS ... ON public.<table>` for
# RLS policies ahead of `DROP TABLE IF EXISTS`. The IF EXISTS only covers
# the policy, not the table, so on a database where the table has never
# existed (first push to a fresh Supabase project) this errors trying to
# resolve the table. These lines are redundant anyway -- DROP TABLE right
# after removes the policies along with it -- so strip them.
sed -i '' '/^DROP POLICY IF EXISTS .* ON public\./d' "$DUMP_FILE"

echo "==> Ensuring enum types exist on Supabase (date_precision, review_status -- see db/migrations/0001_enums.sql)..."
ENUM_SQL=$(cat <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'date_precision') THEN
        CREATE TYPE date_precision AS ENUM ('day', 'month', 'range', 'unknown');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'review_status') THEN
        CREATE TYPE review_status AS ENUM ('unreviewed', 'confirmed', 'rejected');
    END IF;
END $$;
SQL
)
if ! psql "$SUPABASE_DATABASE_URL" -v ON_ERROR_STOP=1 -c "$ENUM_SQL" >/dev/null 2>"$ERR_LOG"; then
  echo "ERROR: enum setup on Supabase failed:" >&2
  _redact < "$ERR_LOG" >&2
  exit 1
fi

echo "==> Checking required extensions/functions on Supabase..."
if ! psql "$SUPABASE_DATABASE_URL" -tAc "SELECT gen_random_uuid()" >/dev/null 2>"$ERR_LOG"; then
  echo "ERROR: gen_random_uuid() is not available on Supabase (used as a column default on several tables). It's core Postgres since v13 and normally needs no extension; if this fails, 'CREATE EXTENSION IF NOT EXISTS pgcrypto;' may be required." >&2
  _redact < "$ERR_LOG" >&2
  exit 1
fi
echo "    gen_random_uuid(): available"

DUMP_EXTENSIONS=$(grep -oE "CREATE EXTENSION IF NOT EXISTS [a-z_]+" "$DUMP_FILE" | awk '{print $NF}' | sort -u || true)
if [ -n "$DUMP_EXTENSIONS" ]; then
  for ext in $DUMP_EXTENSIONS; do
    EXISTS=$(psql "$SUPABASE_DATABASE_URL" -tAc "SELECT 1 FROM pg_extension WHERE extname='$ext'")
    if [ "$EXISTS" != "1" ]; then
      echo "ERROR: extension '$ext' is required by the dump but missing on Supabase" >&2
      exit 1
    fi
    echo "    extension '$ext': present"
  done
else
  echo "    dump contains no explicit CREATE EXTENSION statements"
fi

echo "==> Restoring into Supabase (drop + recreate the 10 DealTrace tables)..."
if ! psql "$SUPABASE_DATABASE_URL" -v ON_ERROR_STOP=1 -f "$DUMP_FILE" >/dev/null 2>"$ERR_LOG"; then
  echo "ERROR: restore into Supabase failed:" >&2
  _redact < "$ERR_LOG" >&2
  exit 1
fi

echo "==> Row counts (local vs Supabase):"
printf "%-20s %12s %12s %8s\n" "table" "local" "supabase" "status"
ALL_PASS=true
for t in "${DEALTRACE_TABLES[@]}"; do
  LOCAL_COUNT=$(psql "$DATABASE_URL" -tAc "SELECT count(*) FROM $t" 2>"$ERR_LOG") || { echo "ERROR: local count failed for $t:" >&2; _redact < "$ERR_LOG" >&2; exit 1; }
  REMOTE_COUNT=$(psql "$SUPABASE_DATABASE_URL" -tAc "SELECT count(*) FROM $t" 2>"$ERR_LOG") || { echo "ERROR: Supabase count failed for $t:" >&2; _redact < "$ERR_LOG" >&2; exit 1; }
  LOCAL_COUNT=$(echo "$LOCAL_COUNT" | tr -d ' ')
  REMOTE_COUNT=$(echo "$REMOTE_COUNT" | tr -d ' ')
  if [ "$LOCAL_COUNT" = "$REMOTE_COUNT" ]; then
    STATUS="PASS"
  else
    STATUS="FAIL"
    ALL_PASS=false
  fi
  printf "%-20s %12s %12s %8s\n" "$t" "$LOCAL_COUNT" "$REMOTE_COUNT" "$STATUS"
done

if [ "$ALL_PASS" = true ]; then
  echo "==> PASS: all row counts match"
  exit 0
else
  echo "==> FAIL: row count mismatch for one or more tables"
  exit 1
fi
