# ScanOps Database Backup Guide

## Overview

ScanOps now includes an automated database backup system with a single backup script that detects the active database engine at runtime and writes backups into:

```text
/home/jaki/Dev/scanops/dbbackup
```

The same script works for:

- direct Linux execution
- Docker / Docker Compose execution

## Supported Engines

The backup script detects the configured Django database engine and uses the appropriate method:

- PostgreSQL
  - uses `pg_dump`
- MySQL
  - uses `mysqldump` or `mariadb-dump`
- SQLite
  - creates a safe snapshot via SQLite backup API, then exports SQL

## Backup Script

Script path:

```text
scripts/backup_db.py
```

Manual host run:

```bash
source /home/jaki/Dev/scanops/.venv/bin/activate
python /home/jaki/Dev/scanops/scripts/backup_db.py
```

Manual Docker run against the running backup container:

```bash
docker compose exec backup python /app/scripts/backup_db.py
```

## Output Location

Backups are written to:

```text
dbbackup/
```

The script creates the directory automatically if it does not exist.

## Filename Format

Default filename pattern:

```text
db_<database_name>_<year>_<month_abbr>_<day>.sql
```

Example:

```text
db_scanops_2026_apr_05.sql
```

If a backup already exists for the same day, the script appends a time suffix to avoid overwriting it.

## Linux Scheduling

Linux scheduling is implemented with a user-level systemd timer.

Files:

- `deploy/systemd/scanops-db-backup.service.template`
- `deploy/systemd/scanops-db-backup.timer`
- `scripts/install_backup_timer.sh`

Install and enable the timer:

```bash
cd /home/jaki/Dev/scanops
./scripts/install_backup_timer.sh
```

Dry-run the generated unit files:

```bash
./scripts/install_backup_timer.sh --dry-run
```

Schedule behavior:

- first run: 10 minutes after boot
- repeat interval: every 15 days after the last successful run
- `Persistent=true` ensures missed runs execute after the machine comes back up

Check timer status:

```bash
systemctl --user status scanops-db-backup.timer
systemctl --user list-timers scanops-db-backup.timer
```

## Docker Scheduling

Docker scheduling is implemented with a dedicated Compose service:

```text
backup
```

This service:

- uses the same project image
- runs the same `scripts/backup_db.py`
- writes backups into the project `dbbackup/` folder
- runs as root inside the backup container so it can always write into the project `dbbackup/` bind mount
- repeats every 15 days

Start the stack:

```bash
docker compose up -d --build
```

Inspect backup logs:

```bash
docker compose logs -f backup
```

The backup interval is controlled with:

```text
JTRO_BACKUP_INTERVAL_SECONDS=1296000
```

`1296000` seconds = 15 days.

## Restore Instructions

### PostgreSQL

```bash
psql -U <user> -h <host> -d <database> < dbbackup/db_scanops_2026_apr_05.sql
```

Docker PostgreSQL restore:

```bash
cat dbbackup/db_scanops_2026_apr_05.sql | docker compose exec -T db psql -U scanops -d scanops
```

### MySQL

```bash
mysql -u <user> -p <database> < dbbackup/db_scanops_2026_apr_05.sql
```

### SQLite

```bash
sqlite3 db.sqlite3 < dbbackup/db_scanops_2026_apr_05.sql
```

## Notes

- Backups run without stopping the application.
- PostgreSQL and MySQL backups rely on native dump tools.
- Docker images now include both `pg_dump` and MySQL client tools so the backup service works across supported SQL engines.
- The Docker backup service writes into the host project folder through a bind mount, so it runs as root inside that dedicated container for reliable file creation across host UID/GID differences.
- Generated backup files are ignored by git.
