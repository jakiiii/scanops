#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/app"
BACKUP_SCRIPT="${PROJECT_ROOT}/scripts/backup_db.py"
INTERVAL_SECONDS="${JTRO_BACKUP_INTERVAL_SECONDS:-1296000}"
RETRY_DELAY_SECONDS="${JTRO_BACKUP_RETRY_DELAY_SECONDS:-60}"

printf "IncidentMatrix backup scheduler started. Interval: %s seconds.\n" "${INTERVAL_SECONDS}"

while true; do
  if python "${BACKUP_SCRIPT}"; then
    printf "Backup completed. Sleeping for %s seconds.\n" "${INTERVAL_SECONDS}"
    sleep "${INTERVAL_SECONDS}"
  else
    printf "Backup failed. Retrying in %s seconds.\n" "${RETRY_DELAY_SECONDS}" >&2
    sleep "${RETRY_DELAY_SECONDS}"
  fi
done
