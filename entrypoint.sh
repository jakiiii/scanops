#!/usr/bin/env bash
set -Eeuo pipefail

DB_HOST="${JTRO_DATABASE_HOST:-${JTRO_DEV_DATABASE_HOST:-}}"
DB_PORT="${JTRO_DATABASE_PORT:-${JTRO_DEV_DATABASE_PORT:-5432}}"
DB_USER="${JTRO_DATABASE_USER:-${JTRO_DEV_DATABASE_USER:-postgres}}"
DB_NAME="${JTRO_DATABASE_NAME:-${JTRO_DEV_DATABASE_NAME:-}}"

if [[ -n "${DB_HOST}" ]]; then
  DB_READY_ARGS=(-h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}")
  if [[ -n "${DB_NAME}" ]]; then
    DB_READY_ARGS+=(-d "${DB_NAME}")
  fi

  printf "Waiting for database at %s:%s...\n" "${DB_HOST}" "${DB_PORT}"
  until pg_isready "${DB_READY_ARGS[@]}" >/dev/null 2>&1; do
    printf "  - database not ready yet\n"
    sleep 1
  done
fi

printf "Running migrations...\n"
python manage.py migrate --noinput

printf "Collecting static files...\n"
python manage.py collectstatic --noinput --ignore "admin/js/*"

exec "$@"
