#!/usr/bin/env bash
set -e

# Ensure script uses LF line endings and is executable
# Wait for Postgres to be available (if using postgres)
if [ -n "$JTRO_DATABASE_HOST" ]; then
  printf "Waiting for database at %s:%s...\n" "$JTRO_DATABASE_HOST" "${JTRO_DATABASE_PORT:-5432}"
  until pg_isready -h "$JTRO_DATABASE_HOST" -p "${JTRO_DATABASE_PORT:-5432}" -U "${JTRO_DATABASE_USER:-postgres}" >/dev/null 2>&1; do
    printf "  - database not ready yet\n"
    sleep 1
  done
fi

# Run migrations and collectstatic
printf "Running migrations...\n"
python manage.py migrate --noinput

printf "Collecting static files...\n"
# ignore admin/js duplicates to avoid duplicate-file warnings during collectstatic
python manage.py collectstatic --noinput --ignore "admin/js/*"

# Execute the passed command
exec "$@"
