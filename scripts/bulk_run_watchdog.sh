#!/bin/bash
# Supervises src.bulk_run: restarts it on an unexpected exit or a stall
# (no new result file for STALL_MINUTES), but NEVER restarts after an
# intentional stop -- bulk_run.py itself writes data/output/bulk_logs/
# PAUSED.json for every one of its own stop conditions (spend cap,
# deadline, rolling-quality auto-pause, an unexpected error class), so
# this script only has to check for that one file's existence.
#
# Safe to resume: bulk_run.py's own per-candidate result files make a
# restart pick up exactly where it left off, at no extra cost for
# already-done candidates.
#
#   nohup setsid caffeinate -dis ./scripts/bulk_run_watchdog.sh \
#     > data/output/bulk_logs/watchdog_stdout.log 2>&1 &
#   disown

set -uo pipefail
cd "$(dirname "$0")/.."

STALL_MINUTES=15
BULK_RUN_ARGS=(--model gemini-3.6-flash --concurrency 4 --concurrency-high 6 --spend-cap-usd 250 --calibration-multiplier 1.0)
LOG_DIR="data/output/bulk_logs"
RESULT_DIR="data/output/bulk_runs"
PAUSE_FILE="$LOG_DIR/PAUSED.json"

log() {
  echo "[watchdog $(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

count_results() {
  ls "$RESULT_DIR"/*.json 2>/dev/null | wc -l | tr -d ' '
}

while true; do
  if [ -f "$PAUSE_FILE" ]; then
    log "PAUSED.json present -- not (re)starting. Reason: $(cat "$PAUSE_FILE")"
    exit 0
  fi

  log "launching: python3 -m src.bulk_run ${BULK_RUN_ARGS[*]}"
  python3 -m src.bulk_run "${BULK_RUN_ARGS[@]}" >> "$LOG_DIR/launch_stdout.log" 2>&1 &
  CHILD_PID=$!
  log "launched, pid=$CHILD_PID"

  last_count=$(count_results)
  last_progress_epoch=$(date +%s)

  while kill -0 "$CHILD_PID" 2>/dev/null; do
    sleep 60
    if [ -f "$PAUSE_FILE" ]; then
      log "PAUSED.json appeared while running -- will not restart after this process exits"
    fi
    cur_count=$(count_results)
    now_epoch=$(date +%s)
    if [ "$cur_count" -gt "$last_count" ]; then
      last_count=$cur_count
      last_progress_epoch=$now_epoch
    fi
    stalled_for=$((now_epoch - last_progress_epoch))
    if [ "$stalled_for" -gt $((STALL_MINUTES * 60)) ]; then
      log "no new result file in ${STALL_MINUTES}m (stuck at $cur_count) -- killing pid=$CHILD_PID and restarting"
      kill "$CHILD_PID" 2>/dev/null
      pkill -f "src.bulk_run" 2>/dev/null
      sleep 3
      break
    fi
  done

  wait "$CHILD_PID" 2>/dev/null
  exit_code=$?
  log "bulk_run.py exited (code=$exit_code)"

  if [ -f "$PAUSE_FILE" ]; then
    log "PAUSED.json present -- stopping watchdog. Reason: $(cat "$PAUSE_FILE")"
    exit 0
  fi

  log "unexpected exit or stall with no pause file -- restarting in 10s"
  sleep 10
done
